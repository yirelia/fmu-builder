# FMU Builder 架构文档

> 版本: 0.1.0 | 更新日期: 2026-03-23 | 状态: MVP 完成

---

## 1. 项目概述

FMU Builder 是一个 Python CLI 工具，将用户提供的 C 源代码封装为符合 FMI 2.0 Co-Simulation 标准的 FMU 文件（.fmu）。

**核心价值**: 用户只需编写一个 YAML 配置文件描述 C 函数接口，工具自动完成 FMI 包装代码生成、编译和打包，无需了解 FMI 规范细节。

**目标用户**: 仿真软件公司的内部工程师和外部客户。

---

## 2. 系统架构

### 2.1 整体数据流

```
用户输入                      工具处理                           输出
─────────                    ────────                          ────

fmu_config.yaml ──┐
                  ├──→ [config.py]      解析验证 YAML
                  │         │
                  │         ▼
                  │    [codegen.py]     生成 adapter.c (Jinja2)
                  │         │
                  │         ▼
                  │    [xmlgen.py]      生成 modelDescription.xml
                  │         │
user_model.c ─────┤         ▼
user_model.h ─────┤    [compiler.py]    调用 MSVC 编译
                  │         │
                  │         ▼
                  └──→ [packager.py]    打包为 .fmu (ZIP)
                            │
                            ▼
                       MyModel.fmu
                       ├── modelDescription.xml
                       └── binaries/win64/MyModel.dll
```

### 2.2 CLI 调用链

```
fmu-builder build config.yaml -o output/
        │
        ▼
    cli.py:build()
        │
        ├─ 1. FmuConfig.from_yaml()          ← config.py   解析+验证 YAML
        ├─ 2. generate_adapter()             ← codegen.py  生成 adapter.c
        ├─ 3. generate_model_description()   ← xmlgen.py   生成 XML
        ├─ 4. compile_fmu()                  ← compiler.py  MSVC 编译 (Windows)
        └─ 5. package_fmu()                  ← packager.py  ZIP 打包为 .fmu
```

### 2.3 模块依赖关系

```
         config.py (Pydantic 数据模型)
        ╱    |     ╲
       ╱     |      ╲
codegen.py xmlgen.py compiler.py
       ╲     |      ╱
        ╲    |     ╱
      packager.py (独立，无依赖 config)
             |
          cli.py (顶层编排)
```

---

## 3. 三层 C 代码架构

这是本项目最核心的设计决策：用 **固定包装器 + 生成适配层** 的方式避免为每个 FMU 生成完整的 FMI 实现。

```
┌─────────────────────────────────────────────────────┐
│  第1层: fmi2_wrapper.c (固定，不生成)                   │
│                                                     │
│  实现全部 27 个 FMI 2.0 C-API 函数                     │
│  ┌───────────────────────────────────────┐          │
│  │ ComponentState 结构体                   │          │
│  │  reals[] → [inputs | outputs | params] │          │
│  │  user_state → 用户 init 返回的指针        │          │
│  │  callbacks, guid, instance_name        │          │
│  └───────────────────────────────────────┘          │
│                                                     │
│  关键函数映射:                                        │
│  fmi2Instantiate  → 分配 ComponentState + 参数默认值   │
│  fmi2DoStep       → 调用 adapter 层的 model_step()    │
│  fmi2GetReal/Set  → 读写 reals[] 数组                 │
│  fmi2Terminate    → 调用 adapter 层的 model_terminate()│
│  fmi2Reset        → 重置状态 + 恢复参数默认值            │
├─────────────────────────────────────────────────────┤
│  第2层: adapter.c (Jinja2 模板生成)                    │
│                                                     │
│  model_initialize() → 调用用户 init_function          │
│  model_step()       → 解包数组，调用用户 step_function  │
│  model_terminate()  → 调用用户 terminate_function     │
│                                                     │
│  支持三种调用风格 (由 YAML 配置决定):                     │
│  A (individual_return):                             │
│     outputs[0] = calc(inputs[0], inputs[1], params[0])│
│  B (individual_void):                               │
│     calc(inputs[0], inputs[1], &outputs[0])          │
│  C (array):                                         │
│     compute(inputs, outputs, params)                │
├─────────────────────────────────────────────────────┤
│  第3层: user_model.c / .h (用户提供)                   │
│                                                     │
│  任意函数签名，adapter.c 负责桥接                       │
│  用户完全不需要了解 FMI 规范                             │
└─────────────────────────────────────────────────────┘
```

### 3.1 adapter 接口 (fmi2_adapter.h)

adapter.c 必须实现以下接口，由 fmi2_wrapper.c 调用：

```c
/* 元数据常量 */
extern const char* MODEL_GUID;
extern const char* MODEL_NAME;
extern const int NUM_INPUTS;
extern const int NUM_OUTPUTS;
extern const int NUM_PARAMS;
extern double PARAM_DEFAULTS[];

/* 生命周期函数 */
void* model_initialize(const double* params);
void  model_step(double dt, const double* inputs, double* outputs,
                 const double* params, void* state);
void  model_terminate(void* state);
```

### 3.2 valueReference 内存布局

FMI 变量通过 valueReference (VR) 索引。所有变量共享一个 `reals[]` 数组：

```
reals[] 数组:
┌──────────────┬───────────────┬──────────────┐
│   inputs     │   outputs     │   params     │
│ VR 0 .. n-1  │ VR n .. n+m-1 │ VR n+m .. end│
└──────────────┴───────────────┴──────────────┘

示例 (SimpleGain: 1 input, 1 output, 1 param):
  reals[0] = x      (VR=0, causality=input)
  reals[1] = y      (VR=1, causality=output)
  reals[2] = K      (VR=2, causality=parameter, start=1.0)
```

`fmi2GetReal/fmi2SetReal` 直接用 VR 作为数组下标读写 `reals[]`。

---

## 4. 模块详细设计

### 4.1 config.py — YAML 配置解析

**职责**: 将 YAML 文件解析为强类型 Python 对象，同时验证语义正确性。

**Pydantic 数据模型层次**:

```
FmuConfig
├── fmu: FmuMeta          (name, guid, description)
├── source: Source        (type="c_source", files=[...])
└── interface: Interface
    ├── inputs: [Variable]
    ├── outputs: [Variable]
    ├── parameters: [Variable]
    ├── step_function: StepFunction
    │   ├── name: str
    │   ├── args: [FunctionArg]      (map, pointer, array)
    │   └── return_val: str | None   (alias: "return")
    ├── init_function: str | None
    └── terminate_function: str | None
```

**验证逻辑**:
- `Variable.type` 只允许 "Real" (MVP)
- `Source.type` 只允许 "c_source" (MVP)
- `FunctionArg.map` 格式: `input.<name>` / `output.<name>` / `param.<name>` 或批量 `inputs`/`outputs`/`params`
- `Interface.validate_mappings()`: 交叉验证所有 arg 映射引用的变量确实存在
- `FmuMeta.resolve_guid()`: guid="auto" 时自动生成 UUID

### 4.2 codegen.py — adapter.c 代码生成

**职责**: 根据配置生成 adapter.c，桥接 fmi2_wrapper.c 和用户 C 函数。

**核心函数**:

- `_build_step_call(cfg)` → `(style, call_args, return_output)`
  - 分析 `FunctionArg` 列表，确定调用风格
  - 有 `array=True` 的参数 → `"array"` 风格
  - 有 `return_val` → `"individual_return"` 风格
  - 其他 → `"individual_void"` 风格
  - 生成 C 参数表达式 (如 `inputs[0], inputs[1], params[0]`)

- `generate_adapter(cfg, output_path)` → 渲染 Jinja2 模板写入文件

**Jinja2 自定义分隔符** (避免 C `{}` 冲突):

| 用途 | 标准 Jinja2 | 本项目 |
|------|-----------|--------|
| 代码块 | `{% %}` | `<% %>` |
| 变量 | `{{ }}` | `<< >>` |
| 注释 | `{# #}` | `<# #>` |

### 4.3 xmlgen.py — modelDescription.xml 生成

**职责**: 生成符合 FMI 2.0 规范的 modelDescription.xml。

**核心函数**:

- `_build_variables(cfg)` → `(variables, output_indices)`
  - 按 inputs → outputs → params 顺序分配 VR (从 0 递增)
  - 为每个变量设置正确的 `causality`、`variability`、`initial` 属性
  - 计算 output 变量的 1-based 索引 (用于 ModelStructure/Outputs)

**变量属性映射**:

| 类别 | causality | variability | initial | start |
|------|-----------|-------------|---------|-------|
| input | input | continuous | — | default 或无 |
| output | output | continuous | calculated | — |
| parameter | parameter | fixed | exact | default 或 0.0 |

### 4.4 compiler.py — MSVC 编译

**职责**: 检测 MSVC (VS 2010/2012) 并编译为 DLL。

**MSVC 检测策略**:

```
优先级:
1. 环境变量 %VS110COMNTOOLS% (VS 2012)
2. 环境变量 %VS100COMNTOOLS% (VS 2010)
3. Windows 注册表 HKLM\Software\Microsoft\VisualStudio\{11.0,10.0}
```

**编译命令**:

```
vcvarsall.bat amd64 && cl.exe /LD /MT /O2 /nologo /I<headers> <sources> /Fe:<output>.dll
```

| 标志 | 作用 |
|------|------|
| `/LD` | 生成 DLL |
| `/MT` | 静态链接 CRT (无运行时依赖) |
| `/O2` | 速度优化 |

**编译输入**: fmi2_wrapper.c + adapter.c + 用户 .c 文件
**编译输出**: `<ModelName>.dll`

**平台限制**: MVP 仅支持 Windows。macOS/Linux 调用时抛出 `CompilerError`。

### 4.5 packager.py — FMU 打包

**职责**: 将 DLL 和 XML 打包为标准 FMU (ZIP) 文件。

**FMU ZIP 结构**:

```
MyModel.fmu (ZIP)
├── modelDescription.xml
└── binaries/
    └── win64/
        └── MyModel.dll
```

### 4.6 cli.py — CLI 入口

**职责**: Typer CLI，编排完整构建流程。

**命令**: `fmu-builder build <config.yaml> [-o <output_dir>]`

**错误处理**:
- YAML 解析失败 → 显示 Pydantic 验证错误
- 源文件不存在 → 提示具体缺失的文件路径
- 编译失败 → 显示 MSVC 编译器输出

---

## 5. 文件结构

```
fmu-builder/
├── fmu_builder/
│   ├── __init__.py
│   ├── cli.py                  # Typer CLI 入口
│   ├── config.py               # Pydantic YAML 解析验证
│   ├── codegen.py              # Jinja2 生成 adapter.c
│   ├── xmlgen.py               # Jinja2 生成 modelDescription.xml
│   ├── compiler.py             # MSVC 编译器调用
│   ├── packager.py             # FMU ZIP 打包
│   ├── templates/
│   │   ├── adapter.c.j2        # adapter.c Jinja2 模板
│   │   └── modelDescription.xml.j2
│   └── static/
│       ├── fmi2_wrapper.c      # 固定的 FMI 包装器 (C89)
│       ├── fmi2_adapter.h      # adapter 接口定义
│       └── fmi2/               # FMI 2.0 官方头文件
│           ├── fmi2Functions.h
│           ├── fmi2FunctionTypes.h
│           └── fmi2TypesPlatform.h
├── examples/
│   └── simple_gain/            # 最简示例 (y = K * x)
│       ├── fmu_config.yaml
│       ├── gain.c
│       └── gain.h
├── tests/
│   ├── test_config.py          # 19 tests: YAML 验证
│   ├── test_codegen.py         # 12 tests: adapter.c 生成
│   ├── test_xmlgen.py          # 13 tests: XML 生成
│   └── test_e2e.py             # 6 tests: 端到端 (2 Windows-only)
├── docs/
│   └── architecture.md         # 本文档
├── pyproject.toml
├── CLAUDE.md
└── README.md
```

---

## 6. YAML 配置格式

### 6.1 完整示例

```yaml
version: 1

fmu:
  name: SimpleGain               # FMU 名称 (= DLL 名 + modelIdentifier)
  guid: auto                     # "auto" 自动生成 UUID，或手动指定
  description: "y = K * x"       # 可选描述

source:
  type: c_source                 # MVP 仅支持 c_source
  files:
    - gain.c                     # 相对于 yaml 文件的路径
    - gain.h

interface:
  inputs:
    - name: x
      description: "Input signal"

  outputs:
    - name: y
      description: "Output signal"

  parameters:
    - name: K
      description: "Gain factor"
      default: 1.0               # 可选，默认 0.0

  step_function:
    name: gain                   # 用户 C 函数名
    args:                        # 按参数顺序描述映射
      - map: input.x             # 第1个参数 ← inputs 中的 x
      - map: param.K             # 第2个参数 ← params 中的 K
    return: output.y             # 返回值 → outputs 中的 y

  # 可选生命周期函数
  init_function: null            # void* my_init(const double* params)
  terminate_function: null       # void my_cleanup(void* state)
```

### 6.2 三种函数风格

**风格 A: 单独参数 + 返回值**

```yaml
# C 函数: double calculate(double x, double y, double Kp)
step_function:
  name: calculate
  args:
    - map: input.x
    - map: input.y
    - map: param.Kp
  return: output.result
```

生成的 adapter.c:
```c
outputs[0] = calculate(inputs[0], inputs[1], params[0]);
```

**风格 B: 单独参数 + 指针输出**

```yaml
# C 函数: void calc_pid(double sp, double fb, double Kp, double* out)
step_function:
  name: calc_pid
  args:
    - map: input.setpoint
    - map: input.feedback
    - map: param.Kp
    - map: output.control
      pointer: true
  return: null
```

生成的 adapter.c:
```c
calc_pid(inputs[0], inputs[1], params[0], &outputs[0]);
```

**风格 C: 数组参数**

```yaml
# C 函数: void model_compute(const double* in, double* out, const double* p)
step_function:
  name: model_compute
  args:
    - map: inputs
      array: true
    - map: outputs
      array: true
    - map: params
      array: true
  return: null
```

生成的 adapter.c:
```c
model_compute(inputs, outputs, params);
```

---

## 7. 测试策略

### 7.1 测试金字塔

```
            ┌───────────────────────┐
            │  test_e2e.py          │  YAML → build → .fmu → FMPy 仿真
            │  (Windows + MSVC)     │  验证 FMU 可加载并计算正确
            ├───────────────────────┤
            │  test_e2e.py          │  YAML → adapter.c + XML + ZIP 结构
            │  (跨平台)             │  不编译，验证生成内容正确
            ├───────────────────────┤
            │  test_codegen.py      │  3种调用风格 × 边界情况 (12 tests)
            │  test_xmlgen.py       │  XML 结构 + VR 映射 (13 tests)
            ├───────────────────────┤
            │  test_config.py       │  有效 YAML (9) + 无效 YAML (10)
            └───────────────────────┘
                 总计: 50 tests (48 passed, 2 skipped on macOS)
```

### 7.2 运行测试

```bash
# 全部测试 (macOS/Linux 跳过编译测试)
pytest tests/ -v

# 单个模块
pytest tests/test_config.py -v
pytest tests/test_codegen.py -v
pytest tests/test_xmlgen.py -v
pytest tests/test_e2e.py -v

# 完整端到端 (仅 Windows + MSVC)
pytest tests/test_e2e.py -v -k "CompileAndRun"
```

### 7.3 已知测试缺口

| 缺口 | 风险 | 优先级 |
|------|------|--------|
| 多实例测试 | 并行运行两个 FMU 实例可能数据串扰 | 高 (v0.2) |
| 用户函数签名不匹配 | 编译错误信息可能不直观 | 中 |
| 大量变量 (>100) | 性能未验证 | 低 |

---

## 8. 技术约束

### 8.1 C89 兼容性

所有 C 代码 (固定包装器 + 模板生成) 必须兼容 VS 2010/2012 (C89):

| 规则 | 说明 |
|------|------|
| ❌ 块中间声明变量 | 所有声明必须在作用域开头 |
| ❌ `//` 单行注释 | 只用 `/* */` |
| ❌ `for(int i=0;...)` | 循环变量在外部声明 |
| ❌ `<stdint.h>` | 用 FMI 头文件的类型 |
| ❌ `<stdbool.h>` | 用 `fmi2Boolean` (int) |
| ✅ FMI 类型 | `fmi2Real`, `fmi2Integer`, `fmi2Boolean` |

### 8.2 MVP 限制

| 限制 | 说明 | 计划解除版本 |
|------|------|------------|
| 仅 Real 类型 | Integer/Boolean/String 返回 fmi2Error | v0.2 |
| 仅 C 源码输入 | 不支持 DLL 输入模式 | v1.1 |
| 仅 MSVC | 不支持 GCC/MinGW/Clang | v0.3 |
| 仅 Win64 | 不支持 Win32/Linux/macOS 目标 | v0.3 |
| 无状态序列化 | fmi2GetFMUstate 未实现 | 暂无计划 |
| 仅 Co-Simulation | 不支持 Model Exchange | 暂无计划 |

---

## 9. 依赖

### 9.1 运行时依赖

| 包 | 版本 | 用途 |
|---|------|------|
| typer | >=0.9.0 | CLI 框架 |
| pyyaml | >=6.0 | YAML 解析 |
| pydantic | >=2.0 | 数据验证 |
| jinja2 | >=3.1 | 模板引擎 |

### 9.2 开发依赖

| 包 | 版本 | 用途 |
|---|------|------|
| pytest | >=7.0 | 测试框架 |
| fmpy | >=0.3 | FMU 仿真验证 (端到端测试) |

### 9.3 系统依赖

| 依赖 | 环境 | 用途 |
|------|------|------|
| MSVC (VS 2010/2012) | Windows | C 编译 |
| Python >=3.10 | 跨平台 | 运行工具 |

---

## 10. 开发工作流

```
Mac (开发 + 单元测试)              Windows (完整验证)
─────────────────                ──────────────────
编辑 Python 代码                  git pull
pytest tests/ -v                 conda activate fmu_builder
  → 48 passed, 2 skipped          pytest tests/ -v
  (跳过编译测试)                     → 50 passed
                                 fmu-builder build examples/...
                                 FMPy 验证生成的 .fmu
```

---

## 11. 版本路线图

| 版本 | 目标 | 状态 |
|------|------|------|
| v0.1.0 | MVP: C 源码 → FMU (MSVC, Real only) | ✅ 完成 |
| v0.2.0 | Integer/Boolean 类型支持 + 多实例测试 | 计划中 |
| v0.3.0 | GCC/MinGW 编译器 + Linux 目标 | 计划中 |
| v1.0.0 | 生产就绪: 错误处理打磨 + 文档 | 计划中 |
| v1.1.0 | DLL 输入模式 (LoadLibrary) | 计划中 |

---

## 12. 故障模式分析

| 故障场景 | 影响 | 有测试 | 有错误处理 | 用户感知 |
|---------|------|--------|-----------|---------|
| YAML 缺少必填字段 | 构建失败 | ✅ | ✅ Pydantic | 清晰错误信息 |
| 用户 C 代码编译错误 | 构建失败 | ✅ (Win) | ✅ 显示编译器输出 | 编译错误 |
| MSVC 未安装 | 构建失败 | ⚠️ | ✅ 检测并报错 | 安装指引 |
| 在 macOS/Linux 运行 build | 构建失败 | ✅ | ✅ CompilerError | 平台提示 |
| GUID 不匹配 | FMU 加载失败 | ✅ | ✅ 统一生成 | FMPy 报错 |
| 用户函数签名不匹配 | 编译错误 | ⚠️ | ⚠️ 编译器报错 | 编译错误 |
| 多实例冲突 | 运行时错乱 | ❌ | ✅ 无全局状态 | 静默错误 ⚠️ |

---

*文档生成日期: 2026-03-23*

"""Generate adapter.c from FMU configuration using Jinja2 templates."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, PackageLoader

from fmu_builder.config import FmuConfig

# Custom delimiters to avoid conflict with C curly braces
_env = Environment(
    loader=PackageLoader("fmu_builder", "templates"),
    block_start_string="<%",
    block_end_string="%>",
    variable_start_string="<<",
    variable_end_string=">>",
    comment_start_string="<#",
    comment_end_string="#>",
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)


def _build_step_call(cfg: FmuConfig) -> tuple[str, str, str | None]:
    """Build the step function call expression.

    Returns (style, call_args, return_output).
    style: "individual_return", "individual_void", or "array"
    call_args: the C argument list string
    return_output: e.g. "outputs[0]" if return maps to an output, else None
    """
    sf = cfg.interface.step_function
    args = sf.args

    # Check if any arg uses array mode
    has_array = any(a.array for a in args)
    if has_array:
        # Array style: pass inputs/outputs/params directly
        parts = []
        for a in args:
            if a.map == "inputs":
                parts.append("inputs")
            elif a.map == "outputs":
                parts.append("outputs")
            elif a.map == "params":
                parts.append("params")
        return "array", ", ".join(parts), None

    # Individual arg style
    input_names = [v.name for v in cfg.interface.inputs]
    output_names = [v.name for v in cfg.interface.outputs]
    param_names = [v.name for v in cfg.interface.parameters]

    parts = []
    for a in args:
        category, name = a.map.split(".", 1)
        if category == "input":
            idx = input_names.index(name)
            parts.append(f"inputs[{idx}]")
        elif category == "output":
            idx = output_names.index(name)
            if a.pointer:
                parts.append(f"&outputs[{idx}]")
            else:
                parts.append(f"outputs[{idx}]")
        elif category == "param":
            idx = param_names.index(name)
            parts.append(f"params[{idx}]")

    call_args = ", ".join(parts)

    # Determine return mapping
    return_output = None
    if sf.return_val:
        _, out_name = sf.return_val.split(".", 1)
        out_idx = output_names.index(out_name)
        return_output = f"outputs[{out_idx}]"
        return "individual_return", call_args, return_output

    return "individual_void", call_args, None


def generate_adapter(cfg: FmuConfig, output_path: Path) -> None:
    """Generate adapter.c file from configuration."""
    template = _env.get_template("adapter.c.j2")

    # Extract header files from source files
    user_headers = [f for f in cfg.source.files if f.endswith(".h")]

    # Build step function call
    step_call_style, step_call_args, return_output = _build_step_call(cfg)

    # Parameter defaults
    param_defaults = []
    for p in cfg.interface.parameters:
        param_defaults.append(p.default if p.default is not None else 0.0)

    rendered = template.render(
        guid=cfg.fmu.guid,
        model_name=cfg.fmu.name,
        num_inputs=len(cfg.interface.inputs),
        num_outputs=len(cfg.interface.outputs),
        num_params=len(cfg.interface.parameters),
        param_defaults=param_defaults,
        user_headers=user_headers,
        init_function=cfg.interface.init_function,
        terminate_function=cfg.interface.terminate_function,
        step_function_name=cfg.interface.step_function.name,
        step_call_style=step_call_style,
        step_call_args=step_call_args,
        return_output=return_output,
    )

    output_path.write_text(rendered, encoding="utf-8")

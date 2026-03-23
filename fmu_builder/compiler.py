"""Compile C source files into a DLL using MSVC (VS 2010/2012)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from fmu_builder.config import FmuConfig

# VS environment variable names in priority order (VS 2012 first, then VS 2010)
_VS_ENV_VARS = ["VS110COMNTOOLS", "VS100COMNTOOLS"]

# Registry paths for fallback detection
_VS_REG_KEYS = [
    (r"SOFTWARE\Microsoft\VisualStudio\11.0", "InstallDir"),  # VS 2012
    (r"SOFTWARE\Microsoft\VisualStudio\10.0", "InstallDir"),  # VS 2010
]


class CompilerError(Exception):
    """Raised when compilation fails."""


def _find_vcvarsall() -> Path:
    """Locate vcvarsall.bat for VS 2010 or VS 2012.

    Search order:
    1. Environment variables (%VS110COMNTOOLS%, %VS100COMNTOOLS%)
    2. Windows registry (fallback)

    Returns the path to vcvarsall.bat.
    Raises CompilerError if not found.
    """
    # Strategy 1: Environment variables
    for env_var in _VS_ENV_VARS:
        tools_path = os.environ.get(env_var)
        if tools_path:
            # VS*COMNTOOLS points to Common7\Tools\
            # vcvarsall.bat is at VC\vcvarsall.bat (two levels up, then VC)
            vcvarsall = Path(tools_path) / ".." / ".." / "VC" / "vcvarsall.bat"
            vcvarsall = vcvarsall.resolve()
            if vcvarsall.exists():
                return vcvarsall

    # Strategy 2: Registry lookup (Windows only)
    if sys.platform == "win32":
        try:
            import winreg
            for reg_key, value_name in _VS_REG_KEYS:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_key)
                    install_dir, _ = winreg.QueryValueEx(key, value_name)
                    winreg.CloseKey(key)
                    # InstallDir points to Common7\IDE\
                    vcvarsall = Path(install_dir) / ".." / ".." / "VC" / "vcvarsall.bat"
                    vcvarsall = vcvarsall.resolve()
                    if vcvarsall.exists():
                        return vcvarsall
                except OSError:
                    continue
        except ImportError:
            pass

    raise CompilerError(
        "Could not find MSVC (Visual Studio 2010 or 2012).\n"
        "Please ensure one of the following:\n"
        "  - VS110COMNTOOLS or VS100COMNTOOLS environment variable is set\n"
        "  - Visual Studio 2010 or 2012 is installed\n"
        "Then run this tool from a Developer Command Prompt, or set the "
        "environment variable manually."
    )


def compile_fmu(
    cfg: FmuConfig,
    user_source_files: list[Path],
    adapter_path: Path,
    build_dir: Path,
    arch: str = "amd64",
) -> Path:
    """Compile all C sources into a DLL.

    Args:
        cfg: FMU configuration.
        user_source_files: Paths to user's .c and .h files.
        adapter_path: Path to the generated adapter.c.
        build_dir: Working directory for compilation output.
        arch: Target architecture ("amd64" or "x86").

    Returns:
        Path to the compiled DLL.

    Raises:
        CompilerError: If compilation fails.
    """
    if sys.platform != "win32":
        raise CompilerError(
            "Compilation requires Windows with MSVC.\n"
            "Cross-compilation from macOS/Linux is not supported in MVP."
        )

    vcvarsall = _find_vcvarsall()

    # Locate static files (fmi2_wrapper.c, fmi2 headers)
    static_dir = Path(__file__).parent / "static"
    wrapper_c = static_dir / "fmi2_wrapper.c"
    fmi2_include_dir = static_dir  # contains fmi2/ subdirectory and fmi2_adapter.h

    # Collect .c files to compile (skip .h files)
    c_files = [str(f) for f in user_source_files if f.suffix == ".c"]
    c_files.append(str(wrapper_c))
    c_files.append(str(adapter_path))

    # Output DLL path
    dll_name = f"{cfg.fmu.name}.dll"
    dll_path = build_dir / dll_name

    # Collect include directories
    # - static dir (for fmi2_adapter.h and fmi2/ headers)
    # - user source directory (for user .h files)
    include_dirs = {str(fmi2_include_dir)}
    for f in user_source_files:
        include_dirs.add(str(f.parent))

    include_flags = " ".join(f'/I"{d}"' for d in include_dirs)
    source_list = " ".join(f'"{f}"' for f in c_files)

    # Build the compilation command
    # /LD  — produce DLL
    # /MT  — static CRT (no runtime dependency)
    # /O2  — optimize for speed
    # /nologo — suppress banner
    cmd = (
        f'"{vcvarsall}" {arch} && '
        f'cl.exe /LD /MT /O2 /nologo '
        f'{include_flags} '
        f'{source_list} '
        f'/Fe:"{dll_path}" '
        f'/Fo:"{build_dir}\\\\" '  # object files go to build dir
        f'/link /DEF:NUL'  # no .def file needed
    )

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=True,
            text=True,
            cwd=str(build_dir),
        )
    except subprocess.CalledProcessError as e:
        error_output = e.stderr or e.stdout or "Unknown error"
        raise CompilerError(
            f"Compilation failed:\n{error_output}"
        ) from e

    if not dll_path.exists():
        raise CompilerError(
            f"Compilation appeared to succeed but DLL not found at {dll_path}"
        )

    return dll_path

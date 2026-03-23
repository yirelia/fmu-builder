"""Package compiled DLL and modelDescription.xml into an FMU (ZIP) file."""

from __future__ import annotations

import zipfile
from pathlib import Path


def package_fmu(
    output_path: Path,
    model_desc_path: Path,
    dll_path: Path,
    model_identifier: str,
    platform: str = "win64",
) -> None:
    """Create an FMU file (ZIP archive) with the standard FMI 2.0 structure.

    FMU structure:
        modelDescription.xml
        binaries/<platform>/<model_identifier>.dll

    Args:
        output_path: Path for the output .fmu file.
        model_desc_path: Path to the generated modelDescription.xml.
        dll_path: Path to the compiled DLL.
        model_identifier: Model identifier (used as DLL filename in the archive).
        platform: Target platform subfolder (default: "win64").
    """
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(model_desc_path, "modelDescription.xml")
        zf.write(dll_path, f"binaries/{platform}/{model_identifier}.dll")

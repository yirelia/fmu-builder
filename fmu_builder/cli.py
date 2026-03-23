"""FMU Builder CLI entry point."""

from pathlib import Path

import typer

from fmu_builder.config import FmuConfig

app = typer.Typer(
    name="fmu-builder",
    help="Build FMI 2.0 Co-Simulation FMUs from C source code.",
)


@app.command()
def build(
    config_path: Path = typer.Argument(..., help="Path to fmu_config.yaml"),
    output_dir: Path = typer.Option(".", "--output", "-o", help="Output directory for .fmu file"),
) -> None:
    """Build an FMU from a YAML configuration and C source files."""
    typer.echo(f"Loading config: {config_path}")

    try:
        cfg = FmuConfig.from_yaml(config_path)
    except Exception as e:
        typer.echo(f"Error loading config: {e}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"FMU name: {cfg.fmu.name}")
    typer.echo(f"GUID: {cfg.fmu.guid}")

    # Resolve source file paths relative to config file
    config_dir = config_path.parent
    source_files = [config_dir / f for f in cfg.source.files]

    for sf in source_files:
        if not sf.exists():
            typer.echo(f"Error: Source file not found: {sf}", err=True)
            raise typer.Exit(code=1)

    # Resolve library paths relative to config file
    lib_files: list[Path] = []
    extra_dlls: list[Path] = []
    for lib in cfg.source.libraries:
        dll = config_dir / lib.dll
        if not dll.exists():
            typer.echo(f"Error: Library DLL not found: {dll}", err=True)
            raise typer.Exit(code=1)
        extra_dlls.append(dll)
        if lib.lib:
            lib_path = config_dir / lib.lib
            if not lib_path.exists():
                typer.echo(f"Error: Import library not found: {lib_path}", err=True)
                raise typer.Exit(code=1)
            lib_files.append(lib_path)

    # Phase 2+: codegen, xmlgen, compile, package
    from fmu_builder.codegen import generate_adapter
    from fmu_builder.xmlgen import generate_model_description
    from fmu_builder.compiler import compile_fmu
    from fmu_builder.packager import package_fmu

    import tempfile

    with tempfile.TemporaryDirectory() as build_dir:
        build_path = Path(build_dir)

        # Generate adapter.c
        typer.echo("Generating adapter.c ...")
        adapter_path = build_path / "adapter.c"
        generate_adapter(cfg, adapter_path)

        # Generate modelDescription.xml
        typer.echo("Generating modelDescription.xml ...")
        xml_path = build_path / "modelDescription.xml"
        generate_model_description(cfg, xml_path)

        # Compile
        typer.echo("Compiling ...")
        dll_path = compile_fmu(
            cfg, source_files, adapter_path, build_path,
            lib_files=lib_files if lib_files else None,
        )

        # Package
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        fmu_path = output_dir / f"{cfg.fmu.name}.fmu"
        typer.echo(f"Packaging {fmu_path} ...")
        package_fmu(
            fmu_path, xml_path, dll_path, cfg.fmu.name,
            extra_dlls=extra_dlls if extra_dlls else None,
        )

    typer.echo(f"Done! FMU created: {fmu_path}")


if __name__ == "__main__":
    app()

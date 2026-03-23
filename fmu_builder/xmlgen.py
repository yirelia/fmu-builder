"""Generate modelDescription.xml from FMU configuration using Jinja2 templates."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, PackageLoader

from fmu_builder.config import FmuConfig

# Reuse the same custom-delimiter Jinja2 environment as codegen
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


def _build_variables(cfg: FmuConfig) -> tuple[list[dict], list[int]]:
    """Build the variable list and output indices for the XML template.

    Returns (variables, output_indices).
    variables: list of dicts with name, vr, causality, variability, initial, description, start.
    output_indices: 1-based indices of output variables in the ModelStructure.
    """
    variables = []
    vr = 0

    # Inputs: causality=input, variability=continuous, no initial
    for v in cfg.interface.inputs:
        variables.append({
            "name": v.name,
            "vr": vr,
            "causality": "input",
            "variability": "continuous",
            "initial": None,
            "description": v.description or v.name,
            "start": v.default,
        })
        vr += 1

    # Outputs: causality=output, variability=continuous, initial=calculated
    output_indices = []
    for v in cfg.interface.outputs:
        variables.append({
            "name": v.name,
            "vr": vr,
            "causality": "output",
            "variability": "continuous",
            "initial": "calculated",
            "description": v.description or v.name,
            "start": None,
        })
        # ModelStructure uses 1-based index into ModelVariables list
        output_indices.append(len(variables))
        vr += 1

    # Parameters: causality=parameter, variability=fixed, initial=exact
    for v in cfg.interface.parameters:
        variables.append({
            "name": v.name,
            "vr": vr,
            "causality": "parameter",
            "variability": "fixed",
            "initial": "exact",
            "description": v.description or v.name,
            "start": v.default if v.default is not None else 0.0,
        })
        vr += 1

    return variables, output_indices


def generate_model_description(cfg: FmuConfig, output_path: Path) -> None:
    """Generate modelDescription.xml file from configuration."""
    template = _env.get_template("modelDescription.xml.j2")

    variables, output_indices = _build_variables(cfg)

    rendered = template.render(
        model_name=cfg.fmu.name,
        guid=cfg.fmu.guid,
        description=cfg.fmu.description or cfg.fmu.name,
        model_identifier=cfg.fmu.name,
        variables=variables,
        output_indices=output_indices,
    )

    output_path.write_text(rendered, encoding="utf-8")

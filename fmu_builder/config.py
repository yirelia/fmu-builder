"""YAML configuration parsing and validation for FMU Builder."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class Variable(BaseModel):
    """A single FMU variable (input, output, or parameter)."""

    name: str
    type: str = "Real"
    description: str = ""
    default: Optional[float] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"Real"}  # MVP only supports Real
        if v not in allowed:
            raise ValueError(f"Unsupported variable type '{v}'. MVP only supports: {allowed}")
        return v


class FunctionArg(BaseModel):
    """Describes one argument of the user's C function."""

    map: str  # e.g. "input.x", "output.y", "param.K", "inputs", "outputs", "params"
    pointer: bool = False  # True if this is a pointer output parameter
    array: bool = False  # True if this passes all inputs/outputs/params as an array

    @field_validator("map")
    @classmethod
    def validate_map(cls, v: str) -> str:
        # Must be "input.xxx", "output.xxx", "param.xxx", or bulk "inputs"/"outputs"/"params"
        bulk_names = {"inputs", "outputs", "params"}
        if v in bulk_names:
            return v
        parts = v.split(".", 1)
        if len(parts) != 2 or parts[0] not in {"input", "output", "param"}:
            raise ValueError(
                f"Invalid map '{v}'. Use 'input.<name>', 'output.<name>', "
                f"'param.<name>', or bulk 'inputs'/'outputs'/'params'."
            )
        return v


class StepFunction(BaseModel):
    """Describes the user's step function and how to call it."""

    name: str
    args: list[FunctionArg]
    return_val: Optional[str] = Field(None, alias="return")
    """Maps return value to an output, e.g. 'output.result'. None if void."""


class Interface(BaseModel):
    """Describes the FMU interface: variables and function mappings."""

    step_function: StepFunction
    inputs: list[Variable] = []
    outputs: list[Variable] = []
    parameters: list[Variable] = []
    init_function: Optional[str] = None
    terminate_function: Optional[str] = None

    @model_validator(mode="after")
    def validate_mappings(self) -> "Interface":
        """Verify that all step_function arg mappings reference existing variables."""
        input_names = {v.name for v in self.inputs}
        output_names = {v.name for v in self.outputs}
        param_names = {v.name for v in self.parameters}

        for arg in self.step_function.args:
            if arg.array:
                if arg.map not in {"inputs", "outputs", "params"}:
                    raise ValueError(
                        f"Array arg must map to 'inputs', 'outputs', or 'params', got '{arg.map}'"
                    )
                continue

            parts = arg.map.split(".", 1)
            if len(parts) == 2:
                category, name = parts
                if category == "input" and name not in input_names:
                    raise ValueError(f"step_function arg maps to unknown input '{name}'")
                elif category == "output" and name not in output_names:
                    raise ValueError(f"step_function arg maps to unknown output '{name}'")
                elif category == "param" and name not in param_names:
                    raise ValueError(f"step_function arg maps to unknown parameter '{name}'")

        # Validate return mapping
        if self.step_function.return_val:
            parts = self.step_function.return_val.split(".", 1)
            if len(parts) != 2 or parts[0] != "output":
                raise ValueError(
                    f"return must map to 'output.<name>', got '{self.step_function.return_val}'"
                )
            if parts[1] not in output_names:
                raise ValueError(
                    f"return maps to unknown output '{parts[1]}'"
                )

        return self


class Source(BaseModel):
    """Describes the source files to compile."""

    type: str = "c_source"
    files: list[str]

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v != "c_source":
            raise ValueError("MVP only supports type 'c_source'")
        return v


class FmuMeta(BaseModel):
    """FMU metadata."""

    name: str
    guid: str = "auto"
    description: str = ""

    @model_validator(mode="after")
    def resolve_guid(self) -> "FmuMeta":
        if self.guid == "auto":
            self.guid = str(uuid.uuid4())
        return self


class FmuConfig(BaseModel):
    """Top-level FMU configuration."""

    version: int = 1
    fmu: FmuMeta
    source: Source
    interface: Interface

    @classmethod
    def from_yaml(cls, path: str | Path) -> "FmuConfig":
        """Load and validate configuration from a YAML file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            raise ValueError(f"Config file is empty: {path}")

        return cls(**data)

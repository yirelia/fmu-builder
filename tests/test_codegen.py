"""Tests for adapter.c code generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from fmu_builder.codegen import generate_adapter
from fmu_builder.config import FmuConfig


def _make_config(**overrides) -> FmuConfig:
    """Helper to build a minimal FmuConfig with overrides."""
    base = {
        "fmu": {"name": "TestModel", "guid": "test-guid-1234"},
        "source": {"files": ["model.c", "model.h"]},
        "interface": {
            "inputs": [{"name": "x"}, {"name": "y"}],
            "outputs": [{"name": "result"}],
            "parameters": [{"name": "Kp", "default": 1.0}],
            "step_function": {
                "name": "calculate",
                "args": [
                    {"map": "input.x"},
                    {"map": "input.y"},
                    {"map": "param.Kp"},
                ],
                "return": "output.result",
            },
        },
    }
    base.update(overrides)
    return FmuConfig(**base)


class TestGenerateAdapterStyleA:
    """Style A: individual args + return value."""

    def test_basic_generation(self, tmp_path: Path):
        cfg = _make_config()
        out = tmp_path / "adapter.c"
        generate_adapter(cfg, out)
        content = out.read_text()

        assert 'MODEL_GUID = "test-guid-1234"' in content
        assert 'MODEL_NAME = "TestModel"' in content
        assert "NUM_INPUTS = 2" in content
        assert "NUM_OUTPUTS = 1" in content
        assert "NUM_PARAMS = 1" in content

    def test_includes_user_headers(self, tmp_path: Path):
        cfg = _make_config()
        out = tmp_path / "adapter.c"
        generate_adapter(cfg, out)
        content = out.read_text()

        assert '#include "model.h"' in content
        # .c files should NOT be included
        assert '#include "model.c"' not in content

    def test_param_defaults(self, tmp_path: Path):
        cfg = _make_config()
        out = tmp_path / "adapter.c"
        generate_adapter(cfg, out)
        content = out.read_text()

        assert "PARAM_DEFAULTS[] = {1.0}" in content

    def test_step_call_return_style(self, tmp_path: Path):
        cfg = _make_config()
        out = tmp_path / "adapter.c"
        generate_adapter(cfg, out)
        content = out.read_text()

        # Should assign return value to output
        assert "outputs[0] = calculate(inputs[0], inputs[1], params[0])" in content

    def test_no_init_function(self, tmp_path: Path):
        cfg = _make_config()
        out = tmp_path / "adapter.c"
        generate_adapter(cfg, out)
        content = out.read_text()

        assert "return NULL;" in content
        assert "(void)params;" in content

    def test_with_init_function(self, tmp_path: Path):
        cfg = _make_config()
        cfg.interface.init_function = "my_init"
        out = tmp_path / "adapter.c"
        generate_adapter(cfg, out)
        content = out.read_text()

        assert "return my_init(params);" in content

    def test_with_terminate_function(self, tmp_path: Path):
        cfg = _make_config()
        cfg.interface.terminate_function = "my_cleanup"
        out = tmp_path / "adapter.c"
        generate_adapter(cfg, out)
        content = out.read_text()

        assert "my_cleanup(state);" in content


class TestGenerateAdapterStyleB:
    """Style B: individual args + pointer output (void return)."""

    def test_pointer_output(self, tmp_path: Path):
        cfg = FmuConfig(**{
            "fmu": {"name": "PidModel", "guid": "pid-guid"},
            "source": {"files": ["pid.c", "pid.h"]},
            "interface": {
                "inputs": [{"name": "setpoint"}, {"name": "feedback"}],
                "outputs": [{"name": "control"}],
                "parameters": [{"name": "Kp", "default": 2.0}],
                "step_function": {
                    "name": "calc_pid",
                    "args": [
                        {"map": "input.setpoint"},
                        {"map": "input.feedback"},
                        {"map": "param.Kp"},
                        {"map": "output.control", "pointer": True},
                    ],
                    "return": None,
                },
            },
        })
        out = tmp_path / "adapter.c"
        generate_adapter(cfg, out)
        content = out.read_text()

        # Pointer output should use &
        assert "calc_pid(inputs[0], inputs[1], params[0], &outputs[0])" in content
        # Should NOT have return assignment
        assert "outputs[0] = calc_pid" not in content


class TestGenerateAdapterStyleC:
    """Style C: array args."""

    def test_array_style(self, tmp_path: Path):
        cfg = FmuConfig(**{
            "fmu": {"name": "ArrayModel", "guid": "array-guid"},
            "source": {"files": ["compute.c", "compute.h"]},
            "interface": {
                "inputs": [{"name": "a"}, {"name": "b"}],
                "outputs": [{"name": "c"}],
                "parameters": [],
                "step_function": {
                    "name": "model_compute",
                    "args": [
                        {"map": "inputs", "array": True},
                        {"map": "outputs", "array": True},
                    ],
                    "return": None,
                },
            },
        })
        out = tmp_path / "adapter.c"
        generate_adapter(cfg, out)
        content = out.read_text()

        assert "model_compute(inputs, outputs)" in content


class TestGenerateAdapterEdgeCases:
    """Edge cases."""

    def test_no_params(self, tmp_path: Path):
        cfg = FmuConfig(**{
            "fmu": {"name": "NoParams", "guid": "np-guid"},
            "source": {"files": ["model.c"]},
            "interface": {
                "inputs": [{"name": "x"}],
                "outputs": [{"name": "y"}],
                "parameters": [],
                "step_function": {
                    "name": "compute",
                    "args": [{"map": "input.x"}],
                    "return": "output.y",
                },
            },
        })
        out = tmp_path / "adapter.c"
        generate_adapter(cfg, out)
        content = out.read_text()

        assert "NUM_PARAMS = 0" in content
        assert "PARAM_DEFAULTS[] = {0.0}" in content

    def test_multiple_param_defaults(self, tmp_path: Path):
        cfg = FmuConfig(**{
            "fmu": {"name": "MultiParam", "guid": "mp-guid"},
            "source": {"files": ["model.c"]},
            "interface": {
                "inputs": [{"name": "x"}],
                "outputs": [{"name": "y"}],
                "parameters": [
                    {"name": "a", "default": 1.5},
                    {"name": "b", "default": 2.5},
                    {"name": "c"},  # no default → 0.0
                ],
                "step_function": {
                    "name": "f",
                    "args": [{"map": "input.x"}],
                    "return": "output.y",
                },
            },
        })
        out = tmp_path / "adapter.c"
        generate_adapter(cfg, out)
        content = out.read_text()

        assert "NUM_PARAMS = 3" in content
        assert "PARAM_DEFAULTS[] = {1.5, 2.5, 0.0}" in content

    def test_no_user_headers(self, tmp_path: Path):
        """When no .h files in source, no user #include lines."""
        cfg = FmuConfig(**{
            "fmu": {"name": "NoHeader", "guid": "nh-guid"},
            "source": {"files": ["model.c"]},
            "interface": {
                "inputs": [{"name": "x"}],
                "outputs": [{"name": "y"}],
                "parameters": [],
                "step_function": {
                    "name": "f",
                    "args": [{"map": "input.x"}],
                    "return": "output.y",
                },
            },
        })
        out = tmp_path / "adapter.c"
        generate_adapter(cfg, out)
        content = out.read_text()

        # Only fmi2_adapter.h should be included
        assert '#include "fmi2_adapter.h"' in content
        lines = [l for l in content.splitlines() if l.startswith('#include') and 'fmi2_adapter' not in l]
        assert len(lines) == 0

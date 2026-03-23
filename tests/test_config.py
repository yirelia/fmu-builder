"""Tests for YAML configuration parsing and validation."""

import tempfile
from pathlib import Path

import pytest
import yaml

from fmu_builder.config import FmuConfig


def _write_yaml(data: dict, path: Path) -> Path:
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
    return path


def _make_valid_config() -> dict:
    return {
        "version": 1,
        "fmu": {
            "name": "TestModel",
            "guid": "auto",
            "description": "A test model",
        },
        "source": {
            "type": "c_source",
            "files": ["model.c", "model.h"],
        },
        "interface": {
            "step_function": {
                "name": "calculate",
                "args": [
                    {"map": "input.x"},
                    {"map": "input.y"},
                    {"map": "param.K"},
                ],
                "return": "output.result",
            },
            "inputs": [
                {"name": "x", "type": "Real", "description": "Input X"},
                {"name": "y", "type": "Real", "description": "Input Y"},
            ],
            "outputs": [
                {"name": "result", "type": "Real", "description": "Output result"},
            ],
            "parameters": [
                {"name": "K", "type": "Real", "default": 1.0, "description": "Gain"},
            ],
        },
    }


class TestFmuConfigValid:
    def test_load_valid_config(self, tmp_path):
        data = _make_valid_config()
        cfg_path = _write_yaml(data, tmp_path / "fmu_config.yaml")
        cfg = FmuConfig.from_yaml(cfg_path)

        assert cfg.fmu.name == "TestModel"
        assert cfg.fmu.guid != "auto"  # should be resolved to UUID
        assert len(cfg.fmu.guid) == 36  # UUID format
        assert cfg.source.type == "c_source"
        assert len(cfg.source.files) == 2
        assert cfg.interface.step_function.name == "calculate"
        assert len(cfg.interface.inputs) == 2
        assert len(cfg.interface.outputs) == 1
        assert len(cfg.interface.parameters) == 1

    def test_auto_guid_generates_uuid(self, tmp_path):
        data = _make_valid_config()
        cfg_path = _write_yaml(data, tmp_path / "fmu_config.yaml")
        cfg1 = FmuConfig.from_yaml(cfg_path)
        cfg2 = FmuConfig.from_yaml(cfg_path)

        assert cfg1.fmu.guid != cfg2.fmu.guid  # each load generates new UUID

    def test_explicit_guid(self, tmp_path):
        data = _make_valid_config()
        data["fmu"]["guid"] = "my-fixed-guid-1234"
        cfg_path = _write_yaml(data, tmp_path / "fmu_config.yaml")
        cfg = FmuConfig.from_yaml(cfg_path)

        assert cfg.fmu.guid == "my-fixed-guid-1234"

    def test_pointer_output_arg(self, tmp_path):
        data = _make_valid_config()
        data["interface"]["step_function"] = {
            "name": "calc",
            "args": [
                {"map": "input.x"},
                {"map": "input.y"},
                {"map": "param.K"},
                {"map": "output.result", "pointer": True},
            ],
            "return": None,
        }
        cfg_path = _write_yaml(data, tmp_path / "fmu_config.yaml")
        cfg = FmuConfig.from_yaml(cfg_path)

        assert cfg.interface.step_function.args[3].pointer is True
        assert cfg.interface.step_function.return_val is None

    def test_array_style_args(self, tmp_path):
        data = _make_valid_config()
        data["interface"]["step_function"] = {
            "name": "compute",
            "args": [
                {"map": "inputs", "array": True},
                {"map": "outputs", "array": True},
                {"map": "params", "array": True},
            ],
            "return": None,
        }
        cfg_path = _write_yaml(data, tmp_path / "fmu_config.yaml")
        cfg = FmuConfig.from_yaml(cfg_path)

        assert cfg.interface.step_function.args[0].array is True

    def test_no_init_terminate(self, tmp_path):
        data = _make_valid_config()
        cfg_path = _write_yaml(data, tmp_path / "fmu_config.yaml")
        cfg = FmuConfig.from_yaml(cfg_path)

        assert cfg.interface.init_function is None
        assert cfg.interface.terminate_function is None

    def test_with_init_terminate(self, tmp_path):
        data = _make_valid_config()
        data["interface"]["init_function"] = "model_init"
        data["interface"]["terminate_function"] = "model_cleanup"
        cfg_path = _write_yaml(data, tmp_path / "fmu_config.yaml")
        cfg = FmuConfig.from_yaml(cfg_path)

        assert cfg.interface.init_function == "model_init"
        assert cfg.interface.terminate_function == "model_cleanup"

    def test_param_default_value(self, tmp_path):
        data = _make_valid_config()
        cfg_path = _write_yaml(data, tmp_path / "fmu_config.yaml")
        cfg = FmuConfig.from_yaml(cfg_path)

        assert cfg.interface.parameters[0].default == 1.0

    def test_empty_inputs(self, tmp_path):
        data = _make_valid_config()
        data["interface"]["inputs"] = []
        data["interface"]["step_function"]["args"] = [
            {"map": "param.K"},
        ]
        data["interface"]["step_function"]["return"] = "output.result"
        cfg_path = _write_yaml(data, tmp_path / "fmu_config.yaml")
        cfg = FmuConfig.from_yaml(cfg_path)

        assert len(cfg.interface.inputs) == 0


class TestFmuConfigInvalid:
    def test_missing_fmu_name(self, tmp_path):
        data = _make_valid_config()
        del data["fmu"]["name"]
        cfg_path = _write_yaml(data, tmp_path / "fmu_config.yaml")

        with pytest.raises(Exception):
            FmuConfig.from_yaml(cfg_path)

    def test_missing_step_function(self, tmp_path):
        data = _make_valid_config()
        del data["interface"]["step_function"]
        cfg_path = _write_yaml(data, tmp_path / "fmu_config.yaml")

        with pytest.raises(Exception):
            FmuConfig.from_yaml(cfg_path)

    def test_unsupported_variable_type(self, tmp_path):
        data = _make_valid_config()
        data["interface"]["inputs"][0]["type"] = "Integer"
        cfg_path = _write_yaml(data, tmp_path / "fmu_config.yaml")

        with pytest.raises(Exception, match="Unsupported variable type"):
            FmuConfig.from_yaml(cfg_path)

    def test_unsupported_source_type(self, tmp_path):
        data = _make_valid_config()
        data["source"]["type"] = "dll"
        cfg_path = _write_yaml(data, tmp_path / "fmu_config.yaml")

        with pytest.raises(Exception, match="MVP only supports"):
            FmuConfig.from_yaml(cfg_path)

    def test_invalid_arg_map(self, tmp_path):
        data = _make_valid_config()
        data["interface"]["step_function"]["args"][0]["map"] = "unknown.x"
        cfg_path = _write_yaml(data, tmp_path / "fmu_config.yaml")

        with pytest.raises(Exception, match="Invalid map"):
            FmuConfig.from_yaml(cfg_path)

    def test_arg_maps_to_nonexistent_input(self, tmp_path):
        data = _make_valid_config()
        data["interface"]["step_function"]["args"][0]["map"] = "input.nonexistent"
        cfg_path = _write_yaml(data, tmp_path / "fmu_config.yaml")

        with pytest.raises(Exception, match="unknown input"):
            FmuConfig.from_yaml(cfg_path)

    def test_return_maps_to_nonexistent_output(self, tmp_path):
        data = _make_valid_config()
        data["interface"]["step_function"]["return"] = "output.nonexistent"
        cfg_path = _write_yaml(data, tmp_path / "fmu_config.yaml")

        with pytest.raises(Exception, match="unknown output"):
            FmuConfig.from_yaml(cfg_path)

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            FmuConfig.from_yaml("/nonexistent/path/config.yaml")

    def test_empty_file(self, tmp_path):
        cfg_path = tmp_path / "empty.yaml"
        cfg_path.write_text("")

        with pytest.raises(ValueError, match="empty"):
            FmuConfig.from_yaml(cfg_path)

    def test_array_arg_invalid_map(self, tmp_path):
        data = _make_valid_config()
        data["interface"]["step_function"] = {
            "name": "compute",
            "args": [
                {"map": "input.x", "array": True},  # should be "inputs" not "input.x"
            ],
            "return": None,
        }
        cfg_path = _write_yaml(data, tmp_path / "fmu_config.yaml")

        with pytest.raises(Exception, match="Array arg must map"):
            FmuConfig.from_yaml(cfg_path)

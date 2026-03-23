"""Tests for modelDescription.xml generation."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from fmu_builder.config import FmuConfig
from fmu_builder.xmlgen import generate_model_description


def _make_config(**overrides) -> FmuConfig:
    """Helper to build a minimal FmuConfig with overrides."""
    base = {
        "fmu": {"name": "TestModel", "guid": "test-guid-1234", "description": "A test model"},
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


def _parse_xml(path: Path) -> ET.Element:
    return ET.parse(path).getroot()


class TestModelDescriptionBasic:
    """Basic XML structure and metadata."""

    def test_root_attributes(self, tmp_path: Path):
        cfg = _make_config()
        out = tmp_path / "modelDescription.xml"
        generate_model_description(cfg, out)
        root = _parse_xml(out)

        assert root.tag == "fmiModelDescription"
        assert root.attrib["fmiVersion"] == "2.0"
        assert root.attrib["modelName"] == "TestModel"
        assert root.attrib["guid"] == "test-guid-1234"
        assert root.attrib["description"] == "A test model"
        assert root.attrib["generationTool"] == "fmu-builder"

    def test_cosimulation_element(self, tmp_path: Path):
        cfg = _make_config()
        out = tmp_path / "modelDescription.xml"
        generate_model_description(cfg, out)
        root = _parse_xml(out)

        cs = root.find("CoSimulation")
        assert cs is not None
        assert cs.attrib["modelIdentifier"] == "TestModel"


class TestModelVariables:
    """ModelVariables section."""

    def test_variable_count(self, tmp_path: Path):
        cfg = _make_config()
        out = tmp_path / "modelDescription.xml"
        generate_model_description(cfg, out)
        root = _parse_xml(out)

        mv = root.find("ModelVariables")
        scalars = mv.findall("ScalarVariable")
        # 2 inputs + 1 output + 1 param = 4
        assert len(scalars) == 4

    def test_input_variables(self, tmp_path: Path):
        cfg = _make_config()
        out = tmp_path / "modelDescription.xml"
        generate_model_description(cfg, out)
        root = _parse_xml(out)

        mv = root.find("ModelVariables")
        scalars = mv.findall("ScalarVariable")

        # First two should be inputs
        x = scalars[0]
        assert x.attrib["name"] == "x"
        assert x.attrib["valueReference"] == "0"
        assert x.attrib["causality"] == "input"
        assert x.attrib["variability"] == "continuous"
        assert "initial" not in x.attrib

        y = scalars[1]
        assert y.attrib["name"] == "y"
        assert y.attrib["valueReference"] == "1"

    def test_output_variable(self, tmp_path: Path):
        cfg = _make_config()
        out = tmp_path / "modelDescription.xml"
        generate_model_description(cfg, out)
        root = _parse_xml(out)

        mv = root.find("ModelVariables")
        scalars = mv.findall("ScalarVariable")

        result = scalars[2]
        assert result.attrib["name"] == "result"
        assert result.attrib["valueReference"] == "2"
        assert result.attrib["causality"] == "output"
        assert result.attrib["variability"] == "continuous"
        assert result.attrib["initial"] == "calculated"

    def test_parameter_variable(self, tmp_path: Path):
        cfg = _make_config()
        out = tmp_path / "modelDescription.xml"
        generate_model_description(cfg, out)
        root = _parse_xml(out)

        mv = root.find("ModelVariables")
        scalars = mv.findall("ScalarVariable")

        kp = scalars[3]
        assert kp.attrib["name"] == "Kp"
        assert kp.attrib["valueReference"] == "3"
        assert kp.attrib["causality"] == "parameter"
        assert kp.attrib["variability"] == "fixed"
        assert kp.attrib["initial"] == "exact"

        # Parameter should have a start value
        real_elem = kp.find("Real")
        assert real_elem is not None
        assert real_elem.attrib["start"] == "1.0"

    def test_output_no_start_value(self, tmp_path: Path):
        cfg = _make_config()
        out = tmp_path / "modelDescription.xml"
        generate_model_description(cfg, out)
        root = _parse_xml(out)

        mv = root.find("ModelVariables")
        scalars = mv.findall("ScalarVariable")

        result = scalars[2]  # output
        real_elem = result.find("Real")
        assert real_elem is not None
        assert "start" not in real_elem.attrib


class TestModelStructure:
    """ModelStructure/Outputs section."""

    def test_output_indices(self, tmp_path: Path):
        cfg = _make_config()
        out = tmp_path / "modelDescription.xml"
        generate_model_description(cfg, out)
        root = _parse_xml(out)

        ms = root.find("ModelStructure")
        outputs = ms.find("Outputs")
        unknowns = outputs.findall("Unknown")

        # Output "result" is 3rd variable (1-based index = 3)
        assert len(unknowns) == 1
        assert unknowns[0].attrib["index"] == "3"

    def test_multiple_outputs(self, tmp_path: Path):
        cfg = FmuConfig(**{
            "fmu": {"name": "MultiOut", "guid": "mo-guid"},
            "source": {"files": ["m.c"]},
            "interface": {
                "inputs": [{"name": "a"}],
                "outputs": [{"name": "b"}, {"name": "c"}],
                "parameters": [],
                "step_function": {
                    "name": "f",
                    "args": [
                        {"map": "inputs", "array": True},
                        {"map": "outputs", "array": True},
                    ],
                    "return": None,
                },
            },
        })
        out = tmp_path / "modelDescription.xml"
        generate_model_description(cfg, out)
        root = _parse_xml(out)

        ms = root.find("ModelStructure")
        unknowns = ms.find("Outputs").findall("Unknown")

        # 1 input + 2 outputs: outputs are at 1-based indices 2 and 3
        assert len(unknowns) == 2
        assert unknowns[0].attrib["index"] == "2"
        assert unknowns[1].attrib["index"] == "3"


class TestValueReferenceMapping:
    """Verify VR assignment: inputs 0..n-1, outputs n..n+m-1, params n+m..n+m+p-1."""

    def test_vr_ordering(self, tmp_path: Path):
        cfg = FmuConfig(**{
            "fmu": {"name": "VrTest", "guid": "vr-guid"},
            "source": {"files": ["m.c"]},
            "interface": {
                "inputs": [{"name": "i0"}, {"name": "i1"}, {"name": "i2"}],
                "outputs": [{"name": "o0"}, {"name": "o1"}],
                "parameters": [{"name": "p0"}, {"name": "p1"}],
                "step_function": {
                    "name": "f",
                    "args": [
                        {"map": "inputs", "array": True},
                        {"map": "outputs", "array": True},
                        {"map": "params", "array": True},
                    ],
                    "return": None,
                },
            },
        })
        out = tmp_path / "modelDescription.xml"
        generate_model_description(cfg, out)
        root = _parse_xml(out)

        mv = root.find("ModelVariables")
        scalars = mv.findall("ScalarVariable")

        vrs = [int(s.attrib["valueReference"]) for s in scalars]
        assert vrs == [0, 1, 2, 3, 4, 5, 6]

        # inputs: 0,1,2  outputs: 3,4  params: 5,6
        assert scalars[0].attrib["causality"] == "input"
        assert scalars[3].attrib["causality"] == "output"
        assert scalars[5].attrib["causality"] == "parameter"


class TestXmlEdgeCases:
    """Edge cases for XML generation."""

    def test_no_parameters(self, tmp_path: Path):
        cfg = FmuConfig(**{
            "fmu": {"name": "NoPar", "guid": "np-guid"},
            "source": {"files": ["m.c"]},
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
        out = tmp_path / "modelDescription.xml"
        generate_model_description(cfg, out)
        root = _parse_xml(out)

        mv = root.find("ModelVariables")
        scalars = mv.findall("ScalarVariable")
        assert len(scalars) == 2  # 1 input + 1 output

    def test_param_default_zero(self, tmp_path: Path):
        """Parameter with no default should get start=0.0."""
        cfg = FmuConfig(**{
            "fmu": {"name": "DefZero", "guid": "dz-guid"},
            "source": {"files": ["m.c"]},
            "interface": {
                "inputs": [{"name": "x"}],
                "outputs": [{"name": "y"}],
                "parameters": [{"name": "K"}],  # no default
                "step_function": {
                    "name": "f",
                    "args": [{"map": "input.x"}],
                    "return": "output.y",
                },
            },
        })
        out = tmp_path / "modelDescription.xml"
        generate_model_description(cfg, out)
        root = _parse_xml(out)

        mv = root.find("ModelVariables")
        scalars = mv.findall("ScalarVariable")
        param = scalars[2]
        real_elem = param.find("Real")
        assert real_elem.attrib["start"] == "0.0"

    def test_xml_is_valid(self, tmp_path: Path):
        """Generated XML should be parseable."""
        cfg = _make_config()
        out = tmp_path / "modelDescription.xml"
        generate_model_description(cfg, out)

        # Should not raise
        tree = ET.parse(out)
        root = tree.getroot()
        assert root.tag == "fmiModelDescription"

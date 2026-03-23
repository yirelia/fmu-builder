"""End-to-end tests: YAML config → generate adapter.c + XML → verify outputs.

Compilation and FMPy simulation tests are Windows-only (require MSVC).
Cross-platform tests verify the full generation pipeline without compilation.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from fmu_builder.codegen import generate_adapter
from fmu_builder.config import FmuConfig
from fmu_builder.packager import package_fmu
from fmu_builder.xmlgen import generate_model_description

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
SIMPLE_GAIN_DIR = EXAMPLES_DIR / "simple_gain"


class TestSimpleGainGeneration:
    """Cross-platform: verify code generation from the simple_gain example."""

    @pytest.fixture()
    def cfg(self) -> FmuConfig:
        return FmuConfig.from_yaml(SIMPLE_GAIN_DIR / "fmu_config.yaml")

    def test_load_config(self, cfg: FmuConfig):
        assert cfg.fmu.name == "SimpleGain"
        assert len(cfg.interface.inputs) == 1
        assert len(cfg.interface.outputs) == 1
        assert len(cfg.interface.parameters) == 1
        assert cfg.interface.parameters[0].default == 1.0

    def test_generate_adapter(self, cfg: FmuConfig, tmp_path: Path):
        adapter_path = tmp_path / "adapter.c"
        generate_adapter(cfg, adapter_path)
        content = adapter_path.read_text()

        assert 'MODEL_NAME = "SimpleGain"' in content
        assert "NUM_INPUTS = 1" in content
        assert "NUM_OUTPUTS = 1" in content
        assert "NUM_PARAMS = 1" in content
        assert "outputs[0] = gain(inputs[0], params[0])" in content

    def test_generate_xml(self, cfg: FmuConfig, tmp_path: Path):
        xml_path = tmp_path / "modelDescription.xml"
        generate_model_description(cfg, xml_path)
        root = ET.parse(xml_path).getroot()

        assert root.attrib["modelName"] == "SimpleGain"
        assert root.attrib["fmiVersion"] == "2.0"

        mv = root.find("ModelVariables")
        scalars = mv.findall("ScalarVariable")
        assert len(scalars) == 3  # 1 input + 1 output + 1 param

        # Check VR ordering
        assert scalars[0].attrib["name"] == "x"
        assert scalars[0].attrib["valueReference"] == "0"
        assert scalars[0].attrib["causality"] == "input"

        assert scalars[1].attrib["name"] == "y"
        assert scalars[1].attrib["valueReference"] == "1"
        assert scalars[1].attrib["causality"] == "output"

        assert scalars[2].attrib["name"] == "K"
        assert scalars[2].attrib["valueReference"] == "2"
        assert scalars[2].attrib["causality"] == "parameter"
        assert scalars[2].find("Real").attrib["start"] == "1.0"

        # ModelStructure output index (1-based: y is 2nd variable)
        outputs = root.find("ModelStructure").find("Outputs")
        unknowns = outputs.findall("Unknown")
        assert len(unknowns) == 1
        assert unknowns[0].attrib["index"] == "2"

    def test_package_fmu_structure(self, cfg: FmuConfig, tmp_path: Path):
        """Verify FMU ZIP structure (using a dummy DLL)."""
        # Generate real XML
        xml_path = tmp_path / "modelDescription.xml"
        generate_model_description(cfg, xml_path)

        # Create a dummy DLL for packaging test
        dll_path = tmp_path / "SimpleGain.dll"
        dll_path.write_bytes(b"DUMMY_DLL_CONTENT")

        fmu_path = tmp_path / "SimpleGain.fmu"
        package_fmu(fmu_path, xml_path, dll_path, "SimpleGain")

        assert fmu_path.exists()

        with zipfile.ZipFile(fmu_path, "r") as zf:
            names = zf.namelist()
            assert "modelDescription.xml" in names
            assert "binaries/win64/SimpleGain.dll" in names

            # Verify XML inside FMU is valid
            with zf.open("modelDescription.xml") as f:
                root = ET.parse(f).getroot()
                assert root.attrib["modelName"] == "SimpleGain"


@pytest.mark.skipif(sys.platform != "win32", reason="Requires Windows + MSVC")
class TestSimpleGainCompileAndRun:
    """Windows-only: compile and run the simple_gain example."""

    def test_full_build(self, tmp_path: Path):
        """Full pipeline: config → adapter.c → XML → compile → package."""
        from fmu_builder.compiler import compile_fmu

        cfg = FmuConfig.from_yaml(SIMPLE_GAIN_DIR / "fmu_config.yaml")
        source_files = [SIMPLE_GAIN_DIR / f for f in cfg.source.files]

        # Generate adapter.c
        adapter_path = tmp_path / "adapter.c"
        generate_adapter(cfg, adapter_path)

        # Generate XML
        xml_path = tmp_path / "modelDescription.xml"
        generate_model_description(cfg, xml_path)

        # Compile
        dll_path = compile_fmu(cfg, source_files, adapter_path, tmp_path)
        assert dll_path.exists()

        # Package
        fmu_path = tmp_path / "SimpleGain.fmu"
        package_fmu(fmu_path, xml_path, dll_path, cfg.fmu.name)
        assert fmu_path.exists()

    def test_fmpy_simulation(self, tmp_path: Path):
        """Verify FMU works with FMPy."""
        from fmu_builder.compiler import compile_fmu

        cfg = FmuConfig.from_yaml(SIMPLE_GAIN_DIR / "fmu_config.yaml")
        source_files = [SIMPLE_GAIN_DIR / f for f in cfg.source.files]

        adapter_path = tmp_path / "adapter.c"
        generate_adapter(cfg, adapter_path)

        xml_path = tmp_path / "modelDescription.xml"
        generate_model_description(cfg, xml_path)

        dll_path = compile_fmu(cfg, source_files, adapter_path, tmp_path)

        fmu_path = tmp_path / "SimpleGain.fmu"
        package_fmu(fmu_path, xml_path, dll_path, cfg.fmu.name)

        # Simulate with FMPy
        from fmpy import simulate_fmu

        result = simulate_fmu(
            str(fmu_path),
            stop_time=1.0,
            step_size=0.1,
            start_values={"x": 2.0, "K": 3.0},
            output=["y"],
        )

        # y = K * x = 3.0 * 2.0 = 6.0
        y_values = result["y"]
        assert abs(y_values[-1] - 6.0) < 1e-10

"""Tests for the CoreForge bridge module."""

from __future__ import annotations

import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from neutron_os.extensions.builtins.model_corral.coreforge_bridge import (
    CoreForgeMaterialSource,
    CoreForgeProvenance,
    extract_provenance,
    get_coreforge_version,
    is_coreforge_available,
)
from neutron_os.extensions.builtins.model_corral.materials_db import (
    MaterialDef,
    MaterialRegistry,
)


# ---------------------------------------------------------------------------
# 1. is_coreforge_available() returns False when CoreForge is not installed
# ---------------------------------------------------------------------------


def test_is_coreforge_available_returns_false_when_not_installed():
    with patch("importlib.import_module", side_effect=ImportError("no coreforge")):
        assert is_coreforge_available() is False


# ---------------------------------------------------------------------------
# 2. get_coreforge_version() returns "" when CoreForge is not installed
# ---------------------------------------------------------------------------


def test_get_coreforge_version_returns_empty_when_not_installed():
    with patch("importlib.import_module", side_effect=ImportError):
        assert get_coreforge_version() == ""


# ---------------------------------------------------------------------------
# 3. CoreForgeMaterialSource.load() returns empty list when not installed
# ---------------------------------------------------------------------------


def test_load_returns_empty_list_when_not_installed():
    with patch("importlib.import_module", side_effect=ImportError):
        source = CoreForgeMaterialSource()
        assert source.load() == []


# ---------------------------------------------------------------------------
# 4. CoreForgeMaterialSource.name returns "coreforge"
# ---------------------------------------------------------------------------


def test_source_name():
    assert CoreForgeMaterialSource().name == "coreforge"


# ---------------------------------------------------------------------------
# 5. CoreForgeMaterialSource.priority returns 200
# ---------------------------------------------------------------------------


def test_source_priority():
    assert CoreForgeMaterialSource().priority == 200


# ---------------------------------------------------------------------------
# 6. extract_provenance() creates CoreForgeProvenance with correct fields
# ---------------------------------------------------------------------------


def test_extract_provenance_creates_provenance(tmp_path: Path):
    config = tmp_path / "reactor.py"
    config.write_text("config = True")

    with patch("importlib.import_module") as mock_import:
        mock_cf = types.ModuleType("coreforge")
        mock_cf.__version__ = "0.4.1"
        mock_import.return_value = mock_cf

        prov = extract_provenance(
            config_path=config,
            builder_class="PinCellBuilder",
            builder_specs={"pitch": 1.26},
        )

    assert prov.coreforge_version == "0.4.1"
    assert prov.config_file == str(config)
    assert prov.builder_class == "PinCellBuilder"
    assert prov.builder_specs == {"pitch": 1.26}
    assert len(prov.geometry_hash) == 16  # sha256 truncated to 16 hex chars


# ---------------------------------------------------------------------------
# 7. extract_provenance() hashes config file content
# ---------------------------------------------------------------------------


def test_extract_provenance_hashes_config_content(tmp_path: Path):
    config = tmp_path / "test.py"
    config.write_text("a = 1")

    with patch("importlib.import_module", side_effect=ImportError):
        prov1 = extract_provenance(config_path=config)

    config.write_text("a = 2")

    with patch("importlib.import_module", side_effect=ImportError):
        prov2 = extract_provenance(config_path=config)

    assert prov1.geometry_hash != prov2.geometry_hash
    assert len(prov1.geometry_hash) == 16


def test_extract_provenance_no_config():
    with patch("importlib.import_module", side_effect=ImportError):
        prov = extract_provenance()

    assert prov.geometry_hash == ""
    assert prov.config_file == ""


# ---------------------------------------------------------------------------
# 8. CoreForgeProvenance.to_dict() serialization
# ---------------------------------------------------------------------------


def test_provenance_to_dict():
    prov = CoreForgeProvenance(
        coreforge_version="0.4.1",
        config_file="/tmp/reactor.py",
        builder_class="PinCellBuilder",
        builder_specs={"pitch": 1.26},
        geometry_hash="abcdef0123456789",
    )
    d = prov.to_dict()
    assert d == {
        "coreforge_version": "0.4.1",
        "config_file": "/tmp/reactor.py",
        "builder_class": "PinCellBuilder",
        "builder_specs": {"pitch": 1.26},
        "geometry_hash": "abcdef0123456789",
    }


# ---------------------------------------------------------------------------
# 9. _convert_material() with a mock CoreForge material (object-style isotopes)
# ---------------------------------------------------------------------------


def _make_mock_cf_material(
    name: str = "UO2",
    density: float = 10.97,
    isotopes: list | None = None,
    **kwargs,
) -> SimpleNamespace:
    if isotopes is None:
        isotopes = [
            SimpleNamespace(zaid="92235.80c", fraction=0.05, name="U-235"),
            SimpleNamespace(zaid="92238.80c", fraction=0.95, name="U-238"),
        ]
    return SimpleNamespace(name=name, density=density, isotopes=isotopes, **kwargs)


def test_convert_material_object_isotopes():
    cf_mat = _make_mock_cf_material()
    with patch("importlib.import_module", side_effect=ImportError):
        result = CoreForgeMaterialSource._convert_material(cf_mat)

    assert result is not None
    assert isinstance(result, MaterialDef)
    assert result.name == "UO2"
    assert result.density == 10.97
    assert len(result.isotopes) == 2
    assert result.isotopes[0].zaid == "92235.80c"
    assert result.isotopes[0].fraction == 0.05
    assert result.isotopes[1].zaid == "92238.80c"


# ---------------------------------------------------------------------------
# 10. _convert_material() with tuple-style isotopes
# ---------------------------------------------------------------------------


def test_convert_material_tuple_isotopes():
    cf_mat = SimpleNamespace(
        name="Zircaloy",
        density=6.56,
        isotopes=[("40090.80c", 0.5145), ("40091.80c", 0.1122)],
    )
    with patch("importlib.import_module", side_effect=ImportError):
        result = CoreForgeMaterialSource._convert_material(cf_mat)

    assert result is not None
    assert len(result.isotopes) == 2
    assert result.isotopes[0].zaid == "40090.80c"
    assert result.isotopes[0].fraction == pytest.approx(0.5145)
    assert result.isotopes[1].zaid == "40091.80c"


# ---------------------------------------------------------------------------
# 11. _convert_material() returns None for objects missing name or density
# ---------------------------------------------------------------------------


def test_convert_material_missing_name():
    cf_mat = SimpleNamespace(density=10.0, isotopes=[])
    assert CoreForgeMaterialSource._convert_material(cf_mat) is None


def test_convert_material_missing_density():
    cf_mat = SimpleNamespace(name="UO2", isotopes=[])
    assert CoreForgeMaterialSource._convert_material(cf_mat) is None


# ---------------------------------------------------------------------------
# 12. CoreForgeMaterialSource integrates with MaterialRegistry
# ---------------------------------------------------------------------------


def test_coreforge_source_integrates_with_registry():
    mock_cf = types.ModuleType("coreforge")
    mock_cf.__version__ = "0.5.0"

    mock_registry = SimpleNamespace(
        list_all=lambda: [
            _make_mock_cf_material("UO2", 10.97),
            _make_mock_cf_material("Zircaloy", 6.56),
        ]
    )
    mock_cf.materials = mock_registry

    def fake_import(name):
        if name == "coreforge":
            return mock_cf
        raise ImportError(name)

    with patch("importlib.import_module", side_effect=fake_import):
        registry = MaterialRegistry()
        registry.register_source(CoreForgeMaterialSource())

        materials = registry.list_all()

    assert len(materials) == 2
    names = {m.name for m in materials}
    assert "UO2" in names
    assert "Zircaloy" in names

    uo2 = registry.get("UO2")
    assert uo2 is not None
    assert uo2.source == "CoreForge v0.5.0"

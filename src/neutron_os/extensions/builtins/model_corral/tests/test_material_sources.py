"""Tests for the MaterialSource protocol pattern and registry."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from neutron_os.extensions.builtins.model_corral.materials_db import (
    BuiltinMaterialSource,
    MaterialDef,
    MaterialRegistry,
    MaterialSource,
    YamlMaterialSource,
    composition_hash,
    get_material,
    get_registry,
    list_materials,
    material_names,
    search_materials,
    Isotope,
)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class _CustomSource:
    """Minimal MaterialSource implementation for testing."""

    def __init__(self, mats: list[MaterialDef], priority: int = 10, name: str = "custom"):
        self._mats = mats
        self._priority = priority
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    def load(self) -> list[MaterialDef]:
        return list(self._mats)


def test_protocol_isinstance():
    """BuiltinMaterialSource and YamlMaterialSource satisfy MaterialSource."""
    assert isinstance(BuiltinMaterialSource(), MaterialSource)
    assert isinstance(YamlMaterialSource(Path("/nonexistent")), MaterialSource)
    assert isinstance(_CustomSource([]), MaterialSource)


# ---------------------------------------------------------------------------
# BuiltinMaterialSource
# ---------------------------------------------------------------------------


def test_builtin_source_loads_all():
    src = BuiltinMaterialSource()
    mats = src.load()
    assert len(mats) == 11
    names = {m.name for m in mats}
    assert "UZrH-20" in names
    assert "SS304" in names
    assert "B4C" in names


def test_builtin_source_metadata():
    src = BuiltinMaterialSource()
    assert src.name == "builtin"
    assert src.priority == 0


# ---------------------------------------------------------------------------
# YamlMaterialSource
# ---------------------------------------------------------------------------


def _write_yaml_materials(directory: Path, materials: list[dict]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    p = directory / "test_mats.yaml"
    p.write_text(yaml.dump(materials), encoding="utf-8")
    return p


@pytest.fixture()
def yaml_dir(tmp_path: Path) -> Path:
    mats = [
        {
            "name": "TestMat",
            "description": "A test material",
            "density": 1.23,
            "category": "fuel",
            "fraction_type": "atom",
            "isotopes": [
                {"zaid": "92235.80c", "fraction": 0.05, "name": "U-235"},
            ],
        },
    ]
    _write_yaml_materials(tmp_path, mats)
    return tmp_path


def test_yaml_source_loads(yaml_dir: Path):
    src = YamlMaterialSource(yaml_dir, priority=50)
    mats = src.load()
    assert len(mats) == 1
    assert mats[0].name == "TestMat"
    assert mats[0].density == 1.23
    assert len(mats[0].isotopes) == 1


def test_yaml_source_missing_dir():
    src = YamlMaterialSource(Path("/no/such/dir"))
    assert src.load() == []


def test_yaml_source_defaults(tmp_path: Path):
    """Fields with defaults should be populated when absent from YAML."""
    _write_yaml_materials(tmp_path, [{"name": "Minimal", "density": 1.0}])
    src = YamlMaterialSource(tmp_path)
    mat = src.load()[0]
    assert mat.fraction_type == "atom"
    assert mat.temperature_k == 293.6
    assert mat.isotopes == ()


# ---------------------------------------------------------------------------
# MaterialRegistry
# ---------------------------------------------------------------------------


def test_registry_merges_by_priority():
    low_mat = MaterialDef(name="Foo", description="low", density=1.0)
    high_mat = MaterialDef(name="Foo", description="high", density=2.0)

    reg = MaterialRegistry()
    reg.register_source(_CustomSource([low_mat], priority=0, name="low"))
    reg.register_source(_CustomSource([high_mat], priority=100, name="high"))

    result = reg.get("Foo")
    assert result is not None
    assert result.density == 2.0
    assert result.description == "high"


def test_registry_source_of():
    mat = MaterialDef(name="Bar", description="", density=1.0)
    reg = MaterialRegistry()
    reg.register_source(_CustomSource([mat], priority=10, name="src-a"))
    assert reg.source_of("Bar") == "src-a"
    assert reg.source_of("nonexistent") == ""


def test_registry_reload(tmp_path: Path):
    """Reload picks up newly added YAML files."""
    reg = MaterialRegistry()
    yaml_src = YamlMaterialSource(tmp_path, priority=50)
    reg.register_source(yaml_src)

    assert reg.names() == []

    # Add a file after initial load
    _write_yaml_materials(tmp_path, [{"name": "Late", "density": 3.0}])
    reg.reload()
    assert "Late" in reg.names()


def test_registry_list_all_and_search():
    m1 = MaterialDef(name="Alpha", description="first", density=1.0, category="fuel")
    m2 = MaterialDef(name="Beta", description="second", density=2.0, category="structural")
    reg = MaterialRegistry()
    reg.register_source(_CustomSource([m1, m2], priority=5))

    assert len(reg.list_all()) == 2
    assert len(reg.list_all("fuel")) == 1
    assert reg.search("first")[0].name == "Alpha"
    assert reg.search("structural")[0].name == "Beta"


# ---------------------------------------------------------------------------
# composition_hash
# ---------------------------------------------------------------------------


def test_composition_hash_deterministic():
    mat = MaterialDef(
        name="H",
        description="",
        density=1.0,
        isotopes=(Isotope("1001.80c", 1.0, "H-1"),),
    )
    assert composition_hash(mat) == composition_hash(mat)


def test_composition_hash_differs():
    m1 = MaterialDef(name="A", description="", density=1.0)
    m2 = MaterialDef(name="B", description="", density=1.0)
    assert composition_hash(m1) != composition_hash(m2)


def test_composition_hash_isotope_order_invariant():
    """Hash should be the same regardless of isotope ordering."""
    iso_a = Isotope("1001.80c", 0.5, "H-1")
    iso_b = Isotope("8016.80c", 0.5, "O-16")
    m1 = MaterialDef(name="X", description="", density=1.0, isotopes=(iso_a, iso_b))
    m2 = MaterialDef(name="X", description="", density=1.0, isotopes=(iso_b, iso_a))
    assert composition_hash(m1) == composition_hash(m2)


# ---------------------------------------------------------------------------
# Public API backward compatibility
# ---------------------------------------------------------------------------


def test_get_material_backward_compat():
    mat = get_material("UZrH-20")
    assert mat is not None
    assert mat.density == 6.0


def test_list_materials_backward_compat():
    fuels = list_materials("fuel")
    assert len(fuels) >= 3  # UZrH-20, UO2-3.1, UO2-4.95, MSRE-salt


def test_search_materials_backward_compat():
    results = search_materials("boron")
    assert any(m.name == "B4C" for m in results)


def test_material_names_backward_compat():
    names = material_names()
    assert "UZrH-20" in names
    assert names == sorted(names)


def test_get_registry():
    reg = get_registry()
    assert isinstance(reg, MaterialRegistry)
    assert reg.get("UZrH-20") is not None


# ---------------------------------------------------------------------------
# User YAML overrides builtin
# ---------------------------------------------------------------------------


def test_yaml_overrides_builtin(tmp_path: Path):
    """A user YAML source with higher priority overrides builtin materials."""
    override = [
        {
            "name": "UZrH-20",
            "description": "Custom override",
            "density": 99.0,
            "category": "fuel",
        },
    ]
    _write_yaml_materials(tmp_path, override)

    reg = MaterialRegistry()
    reg.register_source(BuiltinMaterialSource())
    reg.register_source(YamlMaterialSource(tmp_path, priority=100, source_name="user"))

    mat = reg.get("UZrH-20")
    assert mat is not None
    assert mat.density == 99.0
    assert mat.description == "Custom override"
    assert reg.source_of("UZrH-20") == "user"

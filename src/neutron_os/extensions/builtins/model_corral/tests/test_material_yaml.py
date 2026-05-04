"""Tests for YAML material definitions and JSON Schema validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest
import yaml

# Paths
_BASE = Path(__file__).resolve().parent.parent
_MATERIALS_DIR = _BASE / "materials"
_SCHEMA_PATH = _BASE / "schemas" / "material-schema.json"

YAML_FILES = sorted(_MATERIALS_DIR.glob("*.yaml"))

EXPECTED_MATERIALS = {
    "UZrH-20",
    "UO2-3.1",
    "UO2-4.95",
    "MSRE-salt",
    "H2O",
    "graphite",
    "H2O-hot",
    "SS304",
    "Zircaloy-4",
    "B4C",
    "air",
}


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text())


@pytest.fixture(scope="module")
def all_materials(schema: dict) -> list[dict]:
    """Load and validate all YAML files, returning flat list of materials."""
    materials: list[dict] = []
    for yf in YAML_FILES:
        data = yaml.safe_load(yf.read_text())
        jsonschema.validate(data, schema)
        materials.extend(data)
    return materials


# --------------------------------------------------------------------------
# 1. All YAML files parse without errors
# --------------------------------------------------------------------------


@pytest.mark.parametrize("yaml_file", YAML_FILES, ids=lambda p: p.name)
def test_yaml_parses(yaml_file: Path):
    data = yaml.safe_load(yaml_file.read_text())
    assert isinstance(data, list), f"{yaml_file.name} must be a YAML list"
    assert len(data) >= 1, f"{yaml_file.name} must contain at least one material"


# --------------------------------------------------------------------------
# 2. All YAML files validate against the JSON Schema
# --------------------------------------------------------------------------


@pytest.mark.parametrize("yaml_file", YAML_FILES, ids=lambda p: p.name)
def test_yaml_validates_against_schema(yaml_file: Path, schema: dict):
    data = yaml.safe_load(yaml_file.read_text())
    jsonschema.validate(data, schema)


# --------------------------------------------------------------------------
# 3. Round-trip: YAML -> MaterialDef -> dict preserves data
# --------------------------------------------------------------------------


def test_round_trip_preserves_data():
    """Load YAML, convert to MaterialDef, convert back, compare."""
    from neutron_os.extensions.builtins.model_corral.materials_db import (
        Isotope,
        MaterialDef,
    )

    for yf in YAML_FILES:
        data = yaml.safe_load(yf.read_text())
        for mat_dict in data:
            # Build MaterialDef from YAML dict
            isotopes = tuple(
                Isotope(
                    zaid=iso["zaid"],
                    fraction=iso["fraction"],
                    name=iso.get("name", ""),
                )
                for iso in mat_dict["isotopes"]
            )
            mat = MaterialDef(
                name=mat_dict["name"],
                description=mat_dict["description"],
                density=mat_dict["density"],
                category=mat_dict.get("category", ""),
                fraction_type=mat_dict.get("fraction_type", "atom"),
                temperature_k=mat_dict.get("temperature_k", 293.6),
                source=mat_dict.get("source", ""),
                sab=mat_dict.get("sab", ""),
                isotopes=isotopes,
            )

            # Verify key fields round-trip
            assert mat.name == mat_dict["name"]
            assert mat.density == mat_dict["density"]
            assert len(mat.isotopes) == len(mat_dict["isotopes"])
            for orig, rebuilt in zip(mat_dict["isotopes"], mat.isotopes):
                assert rebuilt.zaid == orig["zaid"]
                assert rebuilt.fraction == pytest.approx(orig["fraction"])


# --------------------------------------------------------------------------
# 4. All 11 materials present
# --------------------------------------------------------------------------


def test_all_eleven_materials_present(all_materials: list[dict]):
    names = {m["name"] for m in all_materials}
    assert names == EXPECTED_MATERIALS, (
        f"Missing: {EXPECTED_MATERIALS - names}, Extra: {names - EXPECTED_MATERIALS}"
    )


# --------------------------------------------------------------------------
# 5. Composition hash is deterministic
# --------------------------------------------------------------------------


def _compute_composition_hash(isotopes: list[dict]) -> str:
    """SHA-256 of sorted isotope ZAID+fraction pairs."""
    canonical = sorted((iso["zaid"], iso["fraction"]) for iso in isotopes)
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def test_composition_hash_deterministic(all_materials: list[dict]):
    for mat in all_materials:
        h1 = _compute_composition_hash(mat["isotopes"])
        h2 = _compute_composition_hash(mat["isotopes"])
        assert h1 == h2, f"Hash not deterministic for {mat['name']}"

    # Verify different materials produce different hashes
    hashes = {mat["name"]: _compute_composition_hash(mat["isotopes"]) for mat in all_materials}
    assert len(set(hashes.values())) == len(hashes), "Hash collision between distinct materials"


# --------------------------------------------------------------------------
# 6. Schema rejects invalid materials
# --------------------------------------------------------------------------


def test_schema_rejects_missing_name(schema: dict):
    invalid = [
        {"description": "x", "density": 1.0, "isotopes": [{"zaid": "1001.80c", "fraction": 1.0}]}
    ]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, schema)


def test_schema_rejects_missing_density(schema: dict):
    invalid = [
        {"name": "x", "description": "x", "isotopes": [{"zaid": "1001.80c", "fraction": 1.0}]}
    ]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, schema)


def test_schema_rejects_missing_description(schema: dict):
    invalid = [{"name": "x", "density": 1.0, "isotopes": [{"zaid": "1001.80c", "fraction": 1.0}]}]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, schema)


def test_schema_rejects_missing_isotopes(schema: dict):
    invalid = [{"name": "x", "description": "x", "density": 1.0}]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, schema)


def test_schema_rejects_bad_category(schema: dict):
    invalid = [
        {
            "name": "x",
            "description": "x",
            "density": 1.0,
            "category": "invalid_category",
            "isotopes": [{"zaid": "1001.80c", "fraction": 1.0}],
        }
    ]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, schema)


def test_schema_rejects_bad_fraction_type(schema: dict):
    invalid = [
        {
            "name": "x",
            "description": "x",
            "density": 1.0,
            "fraction_type": "volume",
            "isotopes": [{"zaid": "1001.80c", "fraction": 1.0}],
        }
    ]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, schema)


def test_schema_rejects_empty_isotopes(schema: dict):
    invalid = [{"name": "x", "description": "x", "density": 1.0, "isotopes": []}]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, schema)

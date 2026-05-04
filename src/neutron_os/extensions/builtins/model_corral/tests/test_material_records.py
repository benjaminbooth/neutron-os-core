"""Tests for MaterialRecord model and ModelVersion.coreforge_provenance."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from neutron_os.extensions.builtins.model_corral.db_models import (
    Base,
    MaterialRecord,
    ModelRegistry,
    ModelVersion,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_material(**overrides) -> MaterialRecord:
    defaults = {
        "name": "UO2",
        "density": 10.97,
        "category": "fuel",
        "fraction_type": "atom",
        "temperature_k": 293.6,
        "data_library": "ENDF/B-VIII.0",
        "composition_hash": "abc123" * 10,
        "isotope_data": [
            {"zaid": "92235", "fraction": 0.05, "name": "U-235"},
            {"zaid": "92238", "fraction": 0.95, "name": "U-238"},
        ],
        "material_source": "builtin",
    }
    defaults.update(overrides)
    return MaterialRecord(**defaults)


class TestMaterialRecord:
    def test_create_and_persist(self, session: Session):
        mat = _make_material(
            description="Uranium dioxide fuel",
            source_reference="PNNL-15870",
            license="CC-BY-4.0",
            pid="10.1234/example",
            facility_pack="triga-ut",
            sab="lwtr.20t",
            data_library_version="1.0",
        )
        session.add(mat)
        session.commit()

        row = session.query(MaterialRecord).one()
        assert row.name == "UO2"
        assert row.density == 10.97
        assert row.category == "fuel"
        assert row.fraction_type == "atom"
        assert row.temperature_k == 293.6
        assert row.description == "Uranium dioxide fuel"
        assert row.source_reference == "PNNL-15870"
        assert row.data_library == "ENDF/B-VIII.0"
        assert row.data_library_version == "1.0"
        assert row.sab == "lwtr.20t"
        assert row.license == "CC-BY-4.0"
        assert row.pid == "10.1234/example"
        assert row.material_source == "builtin"
        assert row.facility_pack == "triga-ut"
        assert row.created_at is not None
        assert row.updated_at is not None

    def test_unique_constraint_name_library(self, session: Session):
        session.add(_make_material())
        session.commit()

        session.add(_make_material(composition_hash="different"))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_same_name_different_library_ok(self, session: Session):
        session.add(_make_material(data_library="ENDF/B-VII.1"))
        session.add(_make_material(data_library="ENDF/B-VIII.0"))
        session.commit()
        assert session.query(MaterialRecord).count() == 2

    def test_query_by_category(self, session: Session):
        session.add(_make_material(name="UO2", category="fuel"))
        session.add(_make_material(name="Zircaloy", category="clad", data_library="ENDF/B-VII.1"))
        session.commit()

        fuels = session.query(MaterialRecord).filter_by(category="fuel").all()
        assert len(fuels) == 1
        assert fuels[0].name == "UO2"

    def test_query_by_data_library(self, session: Session):
        session.add(_make_material(name="mat1", data_library="ENDF/B-VIII.0"))
        session.add(_make_material(name="mat2", data_library="ENDF/B-VII.1"))
        session.commit()

        rows = session.query(MaterialRecord).filter_by(data_library="ENDF/B-VIII.0").all()
        assert len(rows) == 1
        assert rows[0].name == "mat1"

    def test_composition_hash_stored(self, session: Session):
        h = "deadbeef" * 8
        session.add(_make_material(composition_hash=h))
        session.commit()
        assert session.query(MaterialRecord).one().composition_hash == h

    def test_fair_metadata_persists(self, session: Session):
        session.add(_make_material(license="MIT", pid="10.5555/test"))
        session.commit()
        row = session.query(MaterialRecord).one()
        assert row.license == "MIT"
        assert row.pid == "10.5555/test"

    def test_material_source_types(self, session: Session):
        for i, src in enumerate(["builtin", "yaml", "coreforge", "federation"]):
            session.add(_make_material(name=f"mat{i}", data_library=f"lib{i}", material_source=src))
        session.commit()
        sources = {r.material_source for r in session.query(MaterialRecord).all()}
        assert sources == {"builtin", "yaml", "coreforge", "federation"}

    def test_update_material(self, session: Session):
        session.add(_make_material(composition_hash="old_hash"))
        session.commit()

        row = session.query(MaterialRecord).one()
        row.composition_hash = "new_hash"
        row.density = 11.0
        session.commit()

        updated = session.query(MaterialRecord).one()
        assert updated.composition_hash == "new_hash"
        assert updated.density == 11.0

    def test_isotope_data_json_roundtrip(self, session: Session):
        isotopes = [
            {"zaid": "92235", "fraction": 0.05, "name": "U-235"},
            {"zaid": "8016", "fraction": 2.0, "name": "O-16"},
        ]
        session.add(_make_material(isotope_data=isotopes))
        session.commit()

        row = session.query(MaterialRecord).one()
        data = row.isotope_data
        # SQLite JSON may return string; handle both
        if isinstance(data, str):
            data = json.loads(data)
        assert len(data) == 2
        assert data[0]["zaid"] == "92235"
        assert data[1]["name"] == "O-16"


class TestModelVersionCoreforgeProvenance:
    def test_coreforge_provenance_roundtrip(self, session: Session):
        reg = ModelRegistry(
            model_id="test-model",
            name="Test",
            reactor_type="TRIGA",
            facility="UT",
            physics_code="MCNP",
            created_by="test",
        )
        session.add(reg)
        session.flush()

        prov = {"builder": "pin_cell", "geometry_hash": "abc123", "config": {"pitch": 1.26}}
        ver = ModelVersion(
            model_id="test-model",
            version="1.0.0",
            coreforge_provenance=prov,
        )
        session.add(ver)
        session.commit()

        row = session.query(ModelVersion).one()
        data = row.coreforge_provenance
        if isinstance(data, str):
            data = json.loads(data)
        assert data["builder"] == "pin_cell"
        assert data["config"]["pitch"] == 1.26

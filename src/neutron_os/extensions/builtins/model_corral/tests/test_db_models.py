"""Tests for Model Corral database models.

Uses SQLite in-memory for structural tests (table existence, FKs, constraints).
Real PostgreSQL migration tests are integration-only.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session


@pytest.fixture
def engine():
    from neutron_os.extensions.builtins.model_corral.db_models import Base

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


class TestTableStructure:
    def test_all_tables_created(self, engine):
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        expected = {"model_registry", "model_versions", "model_lineage", "model_validations"}
        assert expected.issubset(tables)

    def test_model_registry_columns(self, engine):
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("model_registry")}
        required = {
            "model_id",
            "name",
            "reactor_type",
            "facility",
            "physics_code",
            "status",
            "access_tier",
            "description",
            "created_by",
            "created_at",
            "updated_at",
        }
        assert required.issubset(cols)

    def test_model_versions_columns(self, engine):
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("model_versions")}
        required = {
            "id",
            "model_id",
            "version",
            "storage_path",
            "checksum",
            "created_at",
            "created_by",
        }
        assert required.issubset(cols)

    def test_model_versions_fk_to_registry(self, engine):
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("model_versions")
        fk_tables = {fk["referred_table"] for fk in fks}
        assert "model_registry" in fk_tables

    def test_model_lineage_fk_both_directions(self, engine):
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("model_lineage")
        fk_cols = {fk["constrained_columns"][0] for fk in fks}
        assert "model_id" in fk_cols
        assert "parent_model_id" in fk_cols

    def test_model_validations_fk(self, engine):
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("model_validations")
        fk_tables = {fk["referred_table"] for fk in fks}
        assert "model_registry" in fk_tables


class TestCRUD:
    def test_insert_model(self, engine):
        from neutron_os.extensions.builtins.model_corral.db_models import ModelRegistry

        with Session(engine) as session:
            model = ModelRegistry(
                model_id="test-model",
                name="Test Model",
                reactor_type="TRIGA",
                facility="NETL",
                physics_code="MCNP",
                status="draft",
                access_tier="facility",
                created_by="test@example.com",
            )
            session.add(model)
            session.commit()

            result = session.get(ModelRegistry, "test-model")
            assert result is not None
            assert result.name == "Test Model"

    def test_insert_version(self, engine):
        from neutron_os.extensions.builtins.model_corral.db_models import (
            ModelRegistry,
            ModelVersion,
        )

        with Session(engine) as session:
            model = ModelRegistry(
                model_id="ver-test",
                name="Version Test",
                reactor_type="PWR",
                facility="generic",
                physics_code="VERA",
                status="draft",
                access_tier="public",
                created_by="test@example.com",
            )
            session.add(model)
            session.flush()

            version = ModelVersion(
                model_id="ver-test",
                version="1.0.0",
                storage_path="models/pwr/generic/vera/ver-test/v1.0.0",
                created_by="test@example.com",
            )
            session.add(version)
            session.commit()

            versions = session.query(ModelVersion).filter_by(model_id="ver-test").all()
            assert len(versions) == 1
            assert versions[0].version == "1.0.0"

    def test_insert_lineage(self, engine):
        from neutron_os.extensions.builtins.model_corral.db_models import (
            ModelLineage,
            ModelRegistry,
        )

        with Session(engine) as session:
            parent = ModelRegistry(
                model_id="parent-model",
                name="Parent",
                reactor_type="TRIGA",
                facility="NETL",
                physics_code="MPACT",
                status="production",
                access_tier="facility",
                created_by="a@b.com",
            )
            child = ModelRegistry(
                model_id="child-model",
                name="Child",
                reactor_type="TRIGA",
                facility="NETL",
                physics_code="MPACT",
                status="draft",
                access_tier="facility",
                created_by="a@b.com",
            )
            session.add_all([parent, child])
            session.flush()

            lineage = ModelLineage(
                model_id="child-model",
                parent_model_id="parent-model",
                relationship_type="derived",
            )
            session.add(lineage)
            session.commit()

            result = session.query(ModelLineage).filter_by(model_id="child-model").first()
            assert result.parent_model_id == "parent-model"

"""Tests for ModelCorralService — the core business logic layer.

Uses SQLite in-memory DB + LocalStorageProvider for full integration
without external dependencies. TDD: written before implementation.
"""

from __future__ import annotations

import pytest
import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from axiom.infra.storage import LocalStorageProvider


@pytest.fixture
def db_engine():
    from neutron_os.extensions.builtins.model_corral.db_models import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def storage(tmp_path):
    return LocalStorageProvider({"base_dir": str(tmp_path / "object-store")})


@pytest.fixture
def service(db_engine, storage):
    from neutron_os.extensions.builtins.model_corral.service import ModelCorralService

    return ModelCorralService(engine=db_engine, storage=storage)


@pytest.fixture
def valid_model_dir(tmp_path):
    """Create a valid model directory for testing."""
    d = tmp_path / "triga-test-mcnp-v1"
    d.mkdir()
    manifest = {
        "model_id": "triga-test-mcnp-v1",
        "name": "Test TRIGA MCNP",
        "version": "1.0.0",
        "status": "draft",
        "reactor_type": "TRIGA",
        "facility": "NETL",
        "physics_code": "MCNP",
        "physics_domain": ["neutronics"],
        "created_by": "test@utexas.edu",
        "created_at": "2026-04-01T00:00:00Z",
        "access_tier": "facility",
        "input_files": [{"path": "input.i", "type": "main_input"}],
        "description": "Test model",
        "tags": ["test"],
    }
    (d / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))
    (d / "input.i").write_text("c MCNP test input\n")
    (d / "README.md").write_text("# Test model\n")
    return d


@pytest.fixture
def rom_model_dir(tmp_path, valid_model_dir):
    """Create a ROM model directory that references the hifi model."""
    d = tmp_path / "triga-test-rom2-v1"
    d.mkdir()
    manifest = {
        "model_id": "triga-test-rom2-v1",
        "name": "Test TRIGA ROM-2",
        "version": "1.0.0",
        "status": "draft",
        "reactor_type": "TRIGA",
        "facility": "NETL",
        "physics_code": "MCNP",
        "physics_domain": ["neutronics"],
        "created_by": "cole@utexas.edu",
        "created_at": "2026-04-01T00:00:00Z",
        "access_tier": "facility",
        "parent_model": "triga-test-mcnp-v1",
        "rom_tier": "ROM-2",
        "model_type": "surrogate",
        "training": {
            "source_model": "triga-test-mcnp-v1",
            "framework": "pytorch",
        },
        "tags": ["rom", "test"],
    }
    (d / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))
    (d / "README.md").write_text("# ROM test\n")
    return d


# ---------------------------------------------------------------------------
# Add (M1.5)
# ---------------------------------------------------------------------------


class TestModelAdd:
    def test_add_valid_model(self, service, valid_model_dir):
        result = service.add(valid_model_dir)
        assert result.success is True
        assert result.model_id == "triga-test-mcnp-v1"

    def test_add_stores_files_in_storage(self, service, valid_model_dir, storage):
        service.add(valid_model_dir)
        entries = storage.list_artifacts("models/")
        names = {e.name for e in entries}
        assert "input.i" in names
        assert "model.yaml" in names

    def test_add_creates_db_record(self, service, valid_model_dir, db_engine):
        from neutron_os.extensions.builtins.model_corral.db_models import ModelRegistry

        service.add(valid_model_dir)
        with Session(db_engine) as session:
            model = session.get(ModelRegistry, "triga-test-mcnp-v1")
            assert model is not None
            assert model.reactor_type == "TRIGA"
            assert model.physics_code == "MCNP"

    def test_add_creates_version_record(self, service, valid_model_dir, db_engine):
        from neutron_os.extensions.builtins.model_corral.db_models import ModelVersion

        service.add(valid_model_dir)
        with Session(db_engine) as session:
            versions = session.query(ModelVersion).filter_by(model_id="triga-test-mcnp-v1").all()
            assert len(versions) == 1
            assert versions[0].version == "1.0.0"

    def test_add_invalid_model_fails(self, service, tmp_path):
        empty = tmp_path / "bad-model"
        empty.mkdir()
        result = service.add(empty)
        assert result.success is False

    def test_add_duplicate_version_fails(self, service, valid_model_dir):
        service.add(valid_model_dir)
        result = service.add(valid_model_dir)
        assert result.success is False
        assert "already exists" in result.error.lower()

    def test_add_with_parent_creates_lineage(
        self, service, valid_model_dir, rom_model_dir, db_engine
    ):
        from neutron_os.extensions.builtins.model_corral.db_models import ModelLineage

        service.add(valid_model_dir)
        service.add(rom_model_dir)
        with Session(db_engine) as session:
            lineage = session.query(ModelLineage).filter_by(model_id="triga-test-rom2-v1").all()
            assert len(lineage) == 1
            assert lineage[0].parent_model_id == "triga-test-mcnp-v1"

    def test_add_computes_checksum(self, service, valid_model_dir, db_engine):
        from neutron_os.extensions.builtins.model_corral.db_models import ModelVersion

        service.add(valid_model_dir)
        with Session(db_engine) as session:
            v = session.query(ModelVersion).filter_by(model_id="triga-test-mcnp-v1").first()
            assert v.checksum is not None
            assert len(v.checksum) == 64  # SHA-256 hex


# ---------------------------------------------------------------------------
# Search / List / Show (M1.6)
# ---------------------------------------------------------------------------


class TestModelSearch:
    def test_list_all(self, service, valid_model_dir):
        service.add(valid_model_dir)
        models = service.list_models()
        assert len(models) == 1
        assert models[0]["model_id"] == "triga-test-mcnp-v1"

    def test_list_filter_reactor(self, service, valid_model_dir):
        service.add(valid_model_dir)
        models = service.list_models(reactor_type="TRIGA")
        assert len(models) == 1
        models = service.list_models(reactor_type="PWR")
        assert len(models) == 0

    def test_list_filter_physics_code(self, service, valid_model_dir):
        service.add(valid_model_dir)
        models = service.list_models(physics_code="MCNP")
        assert len(models) == 1
        models = service.list_models(physics_code="VERA")
        assert len(models) == 0

    def test_list_filter_status(self, service, valid_model_dir):
        service.add(valid_model_dir)
        models = service.list_models(status="draft")
        assert len(models) == 1
        models = service.list_models(status="production")
        assert len(models) == 0

    def test_show_model(self, service, valid_model_dir):
        service.add(valid_model_dir)
        info = service.show("triga-test-mcnp-v1")
        assert info is not None
        assert info["model_id"] == "triga-test-mcnp-v1"
        assert info["reactor_type"] == "TRIGA"
        assert "versions" in info

    def test_show_nonexistent_returns_none(self, service):
        assert service.show("nonexistent") is None

    def test_search_by_keyword(self, service, valid_model_dir):
        service.add(valid_model_dir)
        results = service.search("TRIGA")
        assert len(results) >= 1

    def test_search_by_tag(self, service, valid_model_dir):
        service.add(valid_model_dir)
        results = service.search("test")
        assert len(results) >= 1

    def test_search_no_results(self, service, valid_model_dir):
        service.add(valid_model_dir)
        results = service.search("nonexistent-query-xyz")
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Pull (M1.7)
# ---------------------------------------------------------------------------


class TestModelPull:
    def test_pull_downloads_files(self, service, valid_model_dir, tmp_path):
        service.add(valid_model_dir)
        dest = tmp_path / "pulled"
        result = service.pull("triga-test-mcnp-v1", dest)
        assert result.success is True
        assert (dest / "model.yaml").exists()
        assert (dest / "input.i").exists()

    def test_pull_roundtrip_content(self, service, valid_model_dir, tmp_path):
        service.add(valid_model_dir)
        dest = tmp_path / "pulled"
        service.pull("triga-test-mcnp-v1", dest)
        original = (valid_model_dir / "input.i").read_text()
        pulled = (dest / "input.i").read_text()
        assert original == pulled

    def test_pull_nonexistent_fails(self, service, tmp_path):
        result = service.pull("nonexistent", tmp_path / "nope")
        assert result.success is False

    def test_pull_specific_version(self, service, valid_model_dir, tmp_path):
        service.add(valid_model_dir)
        dest = tmp_path / "pulled"
        result = service.pull("triga-test-mcnp-v1", dest, version="1.0.0")
        assert result.success is True


# ---------------------------------------------------------------------------
# Lineage (M1.8)
# ---------------------------------------------------------------------------


class TestModelLineage:
    def test_lineage_chain(self, service, valid_model_dir, rom_model_dir):
        service.add(valid_model_dir)
        service.add(rom_model_dir)
        chain = service.lineage("triga-test-rom2-v1")
        assert len(chain) >= 1
        parent_ids = [entry["parent_model_id"] for entry in chain]
        assert "triga-test-mcnp-v1" in parent_ids

    def test_lineage_no_parents(self, service, valid_model_dir):
        service.add(valid_model_dir)
        chain = service.lineage("triga-test-mcnp-v1")
        assert chain == []

    def test_lineage_nonexistent_returns_empty(self, service):
        chain = service.lineage("nonexistent")
        assert chain == []


# ---------------------------------------------------------------------------
# Clone/Fork Workflow (US-MC-002: fork existing model, document modifications)
# ---------------------------------------------------------------------------


class TestCloneForkWorkflow:
    """Simulate the common case where a researcher pulls an existing model,
    modifies it, and submits the modified version as a new model referencing
    the original via parent_model.
    """

    def test_full_clone_modify_submit_flow(self, service, valid_model_dir, tmp_path):
        # Step 1: Original model submitted
        service.add(valid_model_dir)

        # Step 2: Researcher pulls it
        pulled = tmp_path / "pulled-model"
        result = service.pull("triga-test-mcnp-v1", pulled)
        assert result.success

        # Step 3: Researcher creates a fork — new model_id, references parent
        fork_dir = tmp_path / "triga-test-mcnp-modified"
        fork_dir.mkdir()

        # Copy pulled files
        for f in pulled.iterdir():
            if f.is_file():
                (fork_dir / f.name).write_bytes(f.read_bytes())

        # Modify the manifest for the fork
        manifest = yaml.safe_load((fork_dir / "model.yaml").read_text())
        manifest["model_id"] = "triga-test-mcnp-modified"
        manifest["name"] = "Modified TRIGA MCNP"
        manifest["version"] = "1.0.0"
        manifest["parent_model"] = "triga-test-mcnp-v1"
        manifest["description"] = "Fork with updated materials"
        (fork_dir / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))

        # Modify an input file
        (fork_dir / "input.i").write_text("c Modified MCNP input\nc Updated materials\n")

        # Step 4: Submit the fork
        result = service.add(fork_dir)
        assert result.success
        assert result.model_id == "triga-test-mcnp-modified"

        # Step 5: Verify lineage is recorded
        chain = service.lineage("triga-test-mcnp-modified")
        assert len(chain) == 1
        assert chain[0]["parent_model_id"] == "triga-test-mcnp-v1"
        assert chain[0]["relationship_type"] == "derived"

        # Step 6: Both models independently searchable
        results = service.search("TRIGA")
        ids = {r["model_id"] for r in results}
        assert "triga-test-mcnp-v1" in ids
        assert "triga-test-mcnp-modified" in ids

    def test_rom_trained_from_hifi(self, service, valid_model_dir, rom_model_dir):
        """ROM developer trains a surrogate from a physics model — lineage tracked."""
        service.add(valid_model_dir)
        result = service.add(rom_model_dir)
        assert result.success

        chain = service.lineage("triga-test-rom2-v1")
        assert len(chain) == 1
        assert chain[0]["relationship_type"] == "trained_from"

    def test_version_bump_on_same_model(self, service, valid_model_dir, tmp_path):
        """Same model_id, new version — should work (not a duplicate)."""
        service.add(valid_model_dir)

        # Create v2 of the same model
        v2_dir = tmp_path / "triga-test-mcnp-v1-v2"
        v2_dir.mkdir()
        for f in valid_model_dir.iterdir():
            if f.is_file():
                (v2_dir / f.name).write_bytes(f.read_bytes())
        manifest = yaml.safe_load((v2_dir / "model.yaml").read_text())
        manifest["version"] = "2.0.0"
        (v2_dir / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))

        result = service.add(v2_dir)
        assert result.success
        assert result.version == "2.0.0"

        # Show should list both versions
        info = service.show("triga-test-mcnp-v1")
        assert len(info["versions"]) == 2


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_unicode_in_description(self, service, valid_model_dir):
        """Model with unicode characters in description and tags."""
        manifest = yaml.safe_load((valid_model_dir / "model.yaml").read_text())
        manifest["description"] = "TRIGA reactor — k∞ = 1.001, ΔT = 5.2°C"
        manifest["tags"] = ["TRIGA", "k-infinity", "Δρ"]
        (valid_model_dir / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))

        result = service.add(valid_model_dir)
        assert result.success

        info = service.show("triga-test-mcnp-v1")
        assert "k∞" in info["description"]

    def test_empty_tags_accepted(self, service, valid_model_dir):
        manifest = yaml.safe_load((valid_model_dir / "model.yaml").read_text())
        manifest["tags"] = []
        (valid_model_dir / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))
        result = service.add(valid_model_dir)
        assert result.success

    def test_very_long_model_id(self, tmp_path, service):
        """model_id at boundary of 255 chars."""
        long_id = "a" * 200  # within limit
        d = tmp_path / long_id
        d.mkdir()
        manifest = {
            "model_id": long_id,
            "name": "Long ID test",
            "version": "1.0.0",
            "status": "draft",
            "reactor_type": "custom",
            "facility": "test",
            "physics_code": "MCNP",
            "physics_domain": ["neutronics"],
            "created_by": "test@example.com",
            "created_at": "2026-01-01T00:00:00Z",
            "access_tier": "public",
        }
        (d / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))
        result = service.add(d)
        assert result.success

    def test_model_with_nested_subdirectories(self, service, tmp_path):
        """Model dir with deep nesting (cross_sections/, mesh/, etc.)."""
        d = tmp_path / "nested-model"
        d.mkdir()
        (d / "cross_sections").mkdir()
        (d / "cross_sections" / "endf8.dat").write_text("XS data")
        (d / "mesh").mkdir()
        (d / "mesh" / "core.e").write_bytes(b"\x00\x01\x02")
        manifest = {
            "model_id": "nested-model",
            "name": "Nested",
            "version": "1.0.0",
            "status": "draft",
            "reactor_type": "TRIGA",
            "facility": "test",
            "physics_code": "SAM",
            "physics_domain": ["thermal_hydraulics"],
            "created_by": "test@example.com",
            "created_at": "2026-01-01T00:00:00Z",
            "access_tier": "public",
        }
        (d / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))
        result = service.add(d)
        assert result.success

        # Pull and verify nested files preserved
        pulled = tmp_path / "pulled-nested"
        service.pull("nested-model", pulled)
        assert (pulled / "cross_sections" / "endf8.dat").read_text() == "XS data"
        assert (pulled / "mesh" / "core.e").read_bytes() == b"\x00\x01\x02"

    def test_concurrent_different_models(self, service, tmp_path):
        """Add two different models — no conflicts."""
        for name in ("model-alpha", "model-beta"):
            d = tmp_path / name
            d.mkdir()
            manifest = {
                "model_id": name,
                "name": name.replace("-", " ").title(),
                "version": "1.0.0",
                "status": "draft",
                "reactor_type": "TRIGA",
                "facility": "test",
                "physics_code": "MCNP",
                "physics_domain": ["neutronics"],
                "created_by": "test@example.com",
                "created_at": "2026-01-01T00:00:00Z",
                "access_tier": "public",
            }
            (d / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))
            result = service.add(d)
            assert result.success

        models = service.list_models()
        assert len(models) == 2

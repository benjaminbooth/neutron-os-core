"""Tests for neut model clone — pull + fork for editing."""

from __future__ import annotations

import pytest
import yaml
from sqlalchemy import create_engine

from axiom.infra.storage import LocalStorageProvider


@pytest.fixture
def svc(tmp_path):
    from neutron_os.extensions.builtins.model_corral.db_models import Base
    from neutron_os.extensions.builtins.model_corral.service import ModelCorralService

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    storage = LocalStorageProvider({"base_dir": str(tmp_path / "store")})
    return ModelCorralService(engine=engine, storage=storage)


@pytest.fixture
def original_model(svc, tmp_path):
    d = tmp_path / "triga-netl-mcnp-v3"
    d.mkdir()
    manifest = {
        "model_id": "triga-netl-mcnp-v3",
        "name": "TRIGA NETL MCNP v3",
        "version": "3.2.1",
        "status": "production",
        "reactor_type": "TRIGA",
        "facility": "NETL",
        "physics_code": "MCNP",
        "physics_domain": ["neutronics"],
        "created_by": "nick@utexas.edu",
        "created_at": "2026-01-15T00:00:00Z",
        "access_tier": "facility",
        "input_files": [{"path": "input.i", "type": "main_input"}],
        "description": "Production MCNP model for TRIGA transient",
        "tags": ["production", "transient"],
    }
    (d / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))
    (d / "input.i").write_text("c MCNP production input\n")
    (d / "README.md").write_text("# TRIGA NETL MCNP v3\n")
    svc.add(d)
    return "triga-netl-mcnp-v3"


class TestModelClone:
    def test_clone_creates_directory(self, svc, original_model, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.clone import model_clone

        clone_dir = model_clone(original_model, svc, output_dir=tmp_path)
        assert clone_dir.exists()
        assert clone_dir.name == "triga-netl-mcnp-v3-fork"

    def test_clone_with_custom_name(self, svc, original_model, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.clone import model_clone

        clone_dir = model_clone(
            original_model, svc, new_name="my-improved-model", output_dir=tmp_path
        )
        assert clone_dir.name == "my-improved-model"

    def test_clone_sets_parent_model(self, svc, original_model, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.clone import model_clone

        clone_dir = model_clone(original_model, svc, output_dir=tmp_path)
        data = yaml.safe_load((clone_dir / "model.yaml").read_text())
        assert data["parent_model"] == "triga-netl-mcnp-v3"

    def test_clone_resets_version_and_status(self, svc, original_model, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.clone import model_clone

        clone_dir = model_clone(original_model, svc, output_dir=tmp_path)
        data = yaml.safe_load((clone_dir / "model.yaml").read_text())
        assert data["version"] == "0.1.0"
        assert data["status"] == "draft"

    def test_clone_copies_input_files(self, svc, original_model, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.clone import model_clone

        clone_dir = model_clone(original_model, svc, output_dir=tmp_path)
        assert (clone_dir / "input.i").exists()
        assert "MCNP production input" in (clone_dir / "input.i").read_text()

    def test_clone_updates_readme(self, svc, original_model, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.clone import model_clone

        clone_dir = model_clone(original_model, svc, output_dir=tmp_path)
        readme = (clone_dir / "README.md").read_text()
        assert "Forked from" in readme
        assert "triga-netl-mcnp-v3" in readme

    def test_clone_validates(self, svc, original_model, tmp_path):
        """Cloned model should pass validation (valid model.yaml)."""
        from neutron_os.extensions.builtins.model_corral.commands.clone import model_clone
        from neutron_os.extensions.builtins.model_corral.manifest import validate_model_dir

        clone_dir = model_clone(original_model, svc, output_dir=tmp_path)
        result = validate_model_dir(clone_dir)
        assert result.valid, f"Cloned model failed validation: {result.errors}"

    def test_clone_then_add_creates_lineage(self, svc, original_model, tmp_path):
        """Full workflow: clone → edit → add → lineage tracked."""
        from neutron_os.extensions.builtins.model_corral.commands.clone import model_clone

        clone_dir = model_clone(original_model, svc, output_dir=tmp_path)

        # Edit the input file
        (clone_dir / "input.i").write_text("c Modified MCNP input\nc Added new tally\n")

        # Submit the fork
        result = svc.add(clone_dir)
        assert result.success

        # Lineage should trace back to original
        chain = svc.lineage(result.model_id)
        assert len(chain) == 1
        assert chain[0]["parent_model_id"] == "triga-netl-mcnp-v3"

    def test_clone_nonexistent_fails(self, svc, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.clone import model_clone

        with pytest.raises(RuntimeError, match="Failed to pull"):
            model_clone("nonexistent-model", svc, output_dir=tmp_path)

    def test_clone_existing_dir_with_explicit_name_fails(self, svc, original_model, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.clone import model_clone

        (tmp_path / "my-explicit-name").mkdir()
        with pytest.raises(FileExistsError):
            model_clone(original_model, svc, new_name="my-explicit-name", output_dir=tmp_path)

    def test_auto_name_avoids_collision(self, svc, original_model, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.clone import model_clone

        # First clone takes -fork
        d1 = model_clone(original_model, svc, output_dir=tmp_path)
        assert d1.name == "triga-netl-mcnp-v3-fork"

        # Second clone gets -fork-2
        d2 = model_clone(original_model, svc, output_dir=tmp_path)
        assert d2.name == "triga-netl-mcnp-v3-fork-2"

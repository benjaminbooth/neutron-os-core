"""Tests for model.yaml manifest parsing and validation.

TDD: Tests written BEFORE implementation.
"""

from __future__ import annotations

from pathlib import Path

import yaml

FIXTURES = Path(__file__).parent / "fixtures"


class TestValidManifests:
    def test_valid_hifi_manifest_passes(self):
        from neutron_os.extensions.builtins.model_corral.manifest import parse_model_yaml

        data = yaml.safe_load((FIXTURES / "valid-hifi" / "model.yaml").read_text())
        result = parse_model_yaml(data)
        assert result.valid is True
        assert result.errors == []

    def test_valid_rom_manifest_passes(self):
        from neutron_os.extensions.builtins.model_corral.manifest import parse_model_yaml

        data = yaml.safe_load((FIXTURES / "valid-rom" / "model.yaml").read_text())
        result = parse_model_yaml(data)
        assert result.valid is True
        assert result.errors == []


class TestInvalidManifests:
    def test_missing_model_id_fails(self):
        from neutron_os.extensions.builtins.model_corral.manifest import parse_model_yaml

        data = yaml.safe_load((FIXTURES / "invalid-missing-id" / "model.yaml").read_text())
        result = parse_model_yaml(data)
        assert result.valid is False
        assert any("model_id" in e for e in result.errors)

    def test_invalid_reactor_type_fails(self):
        from neutron_os.extensions.builtins.model_corral.manifest import parse_model_yaml

        data = {
            "model_id": "test-model",
            "name": "Test",
            "version": "1.0.0",
            "status": "draft",
            "reactor_type": "UNKNOWN_REACTOR",
            "facility": "test",
            "physics_code": "MCNP",
            "physics_domain": ["neutronics"],
            "created_by": "test@example.com",
            "created_at": "2026-01-01T00:00:00Z",
            "access_tier": "public",
        }
        result = parse_model_yaml(data)
        assert result.valid is False

    def test_invalid_status_fails(self):
        from neutron_os.extensions.builtins.model_corral.manifest import parse_model_yaml

        data = {
            "model_id": "test-model",
            "name": "Test",
            "version": "1.0.0",
            "status": "bogus",
            "reactor_type": "TRIGA",
            "facility": "test",
            "physics_code": "MCNP",
            "physics_domain": ["neutronics"],
            "created_by": "test@example.com",
            "created_at": "2026-01-01T00:00:00Z",
            "access_tier": "public",
        }
        result = parse_model_yaml(data)
        assert result.valid is False

    def test_model_id_format_enforced(self):
        from neutron_os.extensions.builtins.model_corral.manifest import parse_model_yaml

        data = {
            "model_id": "My Model!",
            "name": "Test",
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
        result = parse_model_yaml(data)
        assert result.valid is False

    def test_semver_enforced(self):
        from neutron_os.extensions.builtins.model_corral.manifest import parse_model_yaml

        data = {
            "model_id": "test-model",
            "name": "Test",
            "version": "1.2",
            "status": "draft",
            "reactor_type": "TRIGA",
            "facility": "test",
            "physics_code": "MCNP",
            "physics_domain": ["neutronics"],
            "created_by": "test@example.com",
            "created_at": "2026-01-01T00:00:00Z",
            "access_tier": "public",
        }
        result = parse_model_yaml(data)
        assert result.valid is False


class TestDirectoryValidation:
    def test_valid_dir_passes(self):
        from neutron_os.extensions.builtins.model_corral.manifest import validate_model_dir

        result = validate_model_dir(FIXTURES / "valid-hifi")
        assert result.valid is True

    def test_missing_model_yaml_fails(self, tmp_path):
        from neutron_os.extensions.builtins.model_corral.manifest import validate_model_dir

        empty = tmp_path / "empty-model"
        empty.mkdir()
        result = validate_model_dir(empty)
        assert result.valid is False
        assert any("model.yaml" in e for e in result.errors)

    def test_missing_input_files_fails(self, tmp_path):
        from neutron_os.extensions.builtins.model_corral.manifest import validate_model_dir

        model_dir = tmp_path / "broken-refs"
        model_dir.mkdir()
        (model_dir / "model.yaml").write_text(
            yaml.dump(
                {
                    "model_id": "broken-refs",
                    "name": "Broken",
                    "version": "1.0.0",
                    "status": "draft",
                    "reactor_type": "TRIGA",
                    "facility": "test",
                    "physics_code": "MCNP",
                    "physics_domain": ["neutronics"],
                    "created_by": "test@example.com",
                    "created_at": "2026-01-01T00:00:00Z",
                    "access_tier": "public",
                    "input_files": [{"path": "nonexistent.i", "type": "main_input"}],
                }
            )
        )
        result = validate_model_dir(model_dir)
        assert result.valid is False
        assert any("nonexistent.i" in e for e in result.errors)

    def test_federation_fields_optional(self):
        from neutron_os.extensions.builtins.model_corral.manifest import parse_model_yaml

        data = yaml.safe_load((FIXTURES / "valid-hifi" / "model.yaml").read_text())
        assert "federation" not in data
        result = parse_model_yaml(data)
        assert result.valid is True

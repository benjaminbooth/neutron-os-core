"""Tests for `neut model init` command. TDD: written before implementation."""

from __future__ import annotations

import pytest
import yaml


class TestModelInit:
    def test_creates_directory(self, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.init import model_init

        model_init("my-model", output_dir=tmp_path)
        assert (tmp_path / "my-model").is_dir()

    def test_creates_model_yaml(self, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.init import model_init

        model_init("my-model", output_dir=tmp_path)
        model_yaml = tmp_path / "my-model" / "model.yaml"
        assert model_yaml.exists()
        data = yaml.safe_load(model_yaml.read_text())
        assert data["model_id"] == "my-model"

    def test_creates_readme(self, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.init import model_init

        model_init("my-model", output_dir=tmp_path)
        assert (tmp_path / "my-model" / "README.md").exists()

    def test_reactor_type_flag(self, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.init import model_init

        model_init("triga-model", reactor_type="TRIGA", output_dir=tmp_path)
        data = yaml.safe_load((tmp_path / "triga-model" / "model.yaml").read_text())
        assert data["reactor_type"] == "TRIGA"

    def test_physics_code_flag(self, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.init import model_init

        model_init("mcnp-model", physics_code="MCNP", output_dir=tmp_path)
        data = yaml.safe_load((tmp_path / "mcnp-model" / "model.yaml").read_text())
        assert data["physics_code"] == "MCNP"

    def test_existing_dir_fails(self, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.init import model_init

        (tmp_path / "existing").mkdir()
        with pytest.raises(FileExistsError):
            model_init("existing", output_dir=tmp_path)

    def test_output_validates(self, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.init import model_init
        from neutron_os.extensions.builtins.model_corral.manifest import validate_model_dir

        model_init("valid-test", reactor_type="TRIGA", physics_code="MCNP", output_dir=tmp_path)
        result = validate_model_dir(tmp_path / "valid-test")
        assert result.valid is True, f"Validation failed: {result.errors}"

    def test_kebab_case_enforced(self, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.init import model_init

        with pytest.raises(ValueError):
            model_init("My Model!", output_dir=tmp_path)

    def test_vscode_config_created(self, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.init import model_init

        model_init("vscode-test", output_dir=tmp_path)
        vscode_dir = tmp_path / "vscode-test" / ".vscode"
        assert (vscode_dir / "settings.json").exists()
        assert (vscode_dir / "extensions.json").exists()

        import json

        settings = json.loads((vscode_dir / "settings.json").read_text())
        assert "yaml.schemas" in settings

        extensions = json.loads((vscode_dir / "extensions.json").read_text())
        assert "redhat.vscode-yaml" in extensions["recommendations"]

    def test_editorconfig_created(self, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.init import model_init

        model_init("editor-test", output_dir=tmp_path)
        ec = tmp_path / "editor-test" / ".editorconfig"
        assert ec.exists()
        content = ec.read_text()
        assert "indent_size = 2" in content
        assert "*.yaml" in content

    def test_yaml_has_schema_directive(self, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.init import model_init

        model_init("schema-test", output_dir=tmp_path)
        content = (tmp_path / "schema-test" / "model.yaml").read_text()
        assert "yaml-language-server" in content
        assert "model-schema.json" in content

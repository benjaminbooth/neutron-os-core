"""Tests for model_corral CLI scaffold + AEOS manifest."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestExtensionManifest:
    def test_toml_exists(self):
        toml_path = Path(__file__).parent.parent / "axiom-extension.toml"
        assert toml_path.exists()

    def test_toml_parseable(self):
        import tomllib

        toml_path = Path(__file__).parent.parent / "axiom-extension.toml"
        data = tomllib.loads(toml_path.read_text())
        assert data["extension"]["name"] == "model_corral"
        assert data["extension"]["builtin"] is True
        assert data["extension"]["aeos_version"] == "0.1.0"

    def test_cli_noun_is_model(self):
        import tomllib

        toml_path = Path(__file__).parent.parent / "axiom-extension.toml"
        data = tomllib.loads(toml_path.read_text())
        provides = data.get("extension", {}).get("provides", [])
        nouns = [p.get("noun") for p in provides if p.get("kind") == "cmd"]
        assert "model" in nouns

    def test_facility_noun_present(self):
        import tomllib

        toml_path = Path(__file__).parent.parent / "axiom-extension.toml"
        data = tomllib.loads(toml_path.read_text())
        provides = data.get("extension", {}).get("provides", [])
        nouns = [p.get("noun") for p in provides if p.get("kind") == "cmd"]
        assert "facility" in nouns


class TestCliParser:
    def test_parser_has_subcommands(self):
        from neutron_os.extensions.builtins.model_corral.cli import build_parser

        parser = build_parser()
        # Should have init and validate at minimum
        assert parser is not None

    def test_help_exits_zero(self):
        from neutron_os.extensions.builtins.model_corral.cli import main

        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_init_subcommand_exists(self):
        from neutron_os.extensions.builtins.model_corral.cli import build_parser

        parser = build_parser()
        # Should parse without error
        args = parser.parse_args(["init", "test-model"])
        assert args.action == "init"

    def test_validate_subcommand_exists(self):
        from neutron_os.extensions.builtins.model_corral.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["validate", "."])
        assert args.action == "validate"

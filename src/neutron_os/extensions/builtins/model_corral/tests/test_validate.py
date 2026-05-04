"""Tests for `neut model validate` command. TDD: written before implementation."""

from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


class TestModelValidate:
    def test_valid_dir_returns_zero(self):
        from neutron_os.extensions.builtins.model_corral.commands.validate import cmd_validate

        rc = cmd_validate(str(FIXTURES / "valid-hifi"), output_format="json")
        assert rc == 0

    def test_missing_model_yaml_returns_nonzero(self, tmp_path):
        from neutron_os.extensions.builtins.model_corral.commands.validate import cmd_validate

        empty = tmp_path / "empty"
        empty.mkdir()
        rc = cmd_validate(str(empty), output_format="json")
        assert rc != 0

    def test_schema_errors_reported(self, capsys):
        from neutron_os.extensions.builtins.model_corral.commands.validate import cmd_validate

        rc = cmd_validate(str(FIXTURES / "invalid-missing-id"), output_format="json")
        assert rc != 0
        output = json.loads(capsys.readouterr().out)
        assert output["valid"] is False
        assert len(output["errors"]) > 0

    def test_json_output(self, capsys):
        from neutron_os.extensions.builtins.model_corral.commands.validate import cmd_validate

        cmd_validate(str(FIXTURES / "valid-hifi"), output_format="json")
        output = json.loads(capsys.readouterr().out)
        assert output["valid"] is True

    def test_human_output(self, capsys):
        from neutron_os.extensions.builtins.model_corral.commands.validate import cmd_validate

        cmd_validate(str(FIXTURES / "valid-hifi"), output_format="human")
        output = capsys.readouterr().out
        assert "valid" in output.lower() or "pass" in output.lower()

"""Tests for progressive disclosure — TieredHelpFormatter and record_action wiring."""

from __future__ import annotations

from io import StringIO

import pytest

from axiom.infra.cli_tiers import (
    get_user_tier,
    record_action,
    set_user_tier,
)
from neutron_os.extensions.builtins.model_corral.cli import build_parser as model_build_parser
from neutron_os.extensions.builtins.model_corral.facilities.cli import (
    build_parser as facility_build_parser,
)


@pytest.fixture(autouse=True)
def _isolated_profile(tmp_path, monkeypatch):
    """Redirect cli_tiers profile to a temp dir so tests don't touch real config."""
    profile = tmp_path / ".axi" / "profile.json"
    monkeypatch.setattr("axiom.infra.cli_tiers._profile_path", lambda: profile)


def _help_text(parser) -> str:
    """Capture --help output from a parser."""
    buf = StringIO()
    try:
        parser.print_help(buf)
    except SystemExit:
        pass
    return buf.getvalue()


# ---- Tier filtering in model --help ----


class TestModelTieredHelp:
    def test_tier_0_hides_advanced_commands(self):
        """At tier 0, --help should not show tier 1+ commands in the subparser list."""
        set_user_tier(0)
        parser = model_build_parser()
        text = _help_text(parser)

        # Extract just the positional arguments / subparser section
        # (exclude epilog which contains workflow examples mentioning all commands)
        lines = text.split("\n")
        subparser_lines = []
        in_positional = False
        for line in lines:
            if "positional arguments" in line:
                in_positional = True
            elif in_positional and (line.startswith("option") or line.startswith("Common")):
                break
            elif in_positional:
                subparser_lines.append(line)
        subparser_text = "\n".join(subparser_lines)

        # Tier 0 commands should appear in subparser list
        assert "init" in subparser_text
        assert "validate" in subparser_text
        assert "add" in subparser_text

        # Tier 1+ commands should be hidden from subparser list
        assert "clone" not in subparser_text
        assert "sweep" not in subparser_text
        assert "share" not in subparser_text

        # Usage line should only show tier 0 commands
        usage_line = (
            [line for line in lines if line.strip().startswith("{")][0]
            if any("{" in line for line in lines)
            else text.split("\n")[0]
        )
        assert "clone" not in usage_line

        # Hint about hidden commands
        assert "more commands available" in text

    def test_tier_4_shows_all(self):
        """At tier 4, --help should show every command."""
        set_user_tier(4)
        parser = model_build_parser()
        text = _help_text(parser)

        assert "init" in text
        assert "clone" in text
        assert "sweep" in text
        assert "share" in text
        assert "audit" in text
        assert "more commands available" not in text

    def test_commands_work_regardless_of_tier(self):
        """All commands are always parseable, even if hidden from help."""
        set_user_tier(0)
        parser = model_build_parser()

        # clone is tier 1, hidden at tier 0, but should still parse
        args = parser.parse_args(["clone", "some-model"])
        assert args.action == "clone"
        assert args.model_id == "some-model"

        # sweep is tier 2
        args = parser.parse_args(["sweep", ".", "--param", "enrichment", "--values", "0.05,0.10"])
        assert args.action == "sweep"


# ---- Tier filtering in facility --help ----


class TestFacilityTieredHelp:
    def test_tier_0_shows_basic_facility_commands(self):
        set_user_tier(0)
        parser = facility_build_parser()
        text = _help_text(parser)

        assert "list" in text
        assert "install" in text
        assert "show" in text

    def test_tier_0_hides_advanced_facility_commands(self):
        set_user_tier(0)
        parser = facility_build_parser()
        text = _help_text(parser)

        # facility:uninstall is tier 1, facility:publish is tier 3, facility:sync is tier 4
        assert "publish" not in text
        assert "sync" not in text


# ---- record_action auto-advance ----


class TestRecordActionAdvance:
    def test_model_add_advances_to_tier_1(self):
        """After model:add, user should auto-advance to tier 1."""
        assert get_user_tier() == 0
        record_action("model", "add")
        assert get_user_tier() == 1

    def test_share_advances_to_tier_2(self):
        """model:share should advance to tier 2."""
        record_action("model", "add")  # need tier 1 first
        record_action("model", "share")
        assert get_user_tier() == 2

    def test_tier_never_decreases(self):
        """Recording a tier 0 action after reaching tier 1 shouldn't decrease tier."""
        record_action("model", "add")
        assert get_user_tier() == 1
        record_action("model", "init")
        assert get_user_tier() == 1

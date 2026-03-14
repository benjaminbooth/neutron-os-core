"""Tests for the 'Silent Contributor' demo scenario."""

from __future__ import annotations

from neutron_os.extensions.builtins.demo.runner import DemoRunner
from neutron_os.extensions.builtins.demo.scenarios.collaborator import build_scenario, FIXTURES_DIR


class TestCollaboratorScenario:
    def test_scenario_builds(self):
        """Scenario builds without errors."""
        scenario = build_scenario()
        assert scenario.name == "The Silent Contributor"
        assert scenario.slug == "collaborator"

    def test_has_nine_acts(self):
        """Scenario has exactly 9 acts (Connect + 8 demo acts, including Triga DT wiki drift)."""
        scenario = build_scenario()
        assert len(scenario.acts) == 9

    def test_acts_numbered_sequentially(self):
        """Acts are numbered 1 through N."""
        scenario = build_scenario()
        numbers = [a.number for a in scenario.acts]
        assert numbers == list(range(1, len(scenario.acts) + 1))

    def test_first_act_is_connect(self):
        """Act 1 is the Connect act (credential setup)."""
        scenario = build_scenario()
        assert scenario.acts[0].title == "Connect"
        assert any("config" in cmd for cmd in scenario.acts[0].commands)

    def test_all_acts_have_commands(self):
        """Every act has at least one command."""
        scenario = build_scenario()
        for act in scenario.acts:
            assert len(act.commands) > 0, f"Act {act.number} has no commands"

    def test_all_acts_have_descriptions(self):
        """Every act has a description."""
        scenario = build_scenario()
        for act in scenario.acts:
            assert act.description, f"Act {act.number} has no description"

    def test_modes_alternate(self):
        """Scenario uses both CLI and chat modes."""
        scenario = build_scenario()
        modes = {a.mode for a in scenario.acts}
        assert "cli" in modes
        assert "chat" in modes

    def test_has_next_steps(self):
        """Scenario has post-demo onboarding next steps."""
        scenario = build_scenario()
        assert len(scenario.next_steps) >= 1
        full_text = " ".join(scenario.next_steps)
        assert "neut config" in full_text

    def test_fixtures_exist(self):
        """Demo fixtures are present."""
        assert (FIXTURES_DIR / "weekly_summary_demo.md").exists()
        assert (FIXTURES_DIR / "prd_skeleton_reactor_log.md").exists()

    def test_weekly_summary_fixture_content(self):
        """Weekly summary fixture has expected sections and no sensitive data."""
        content = (FIXTURES_DIR / "weekly_summary_demo.md").read_text()
        assert "Active Blockers" in content
        assert "55 commits" in content
        assert "NeutronOS" in content
        # Must not contain real staff names
        assert "Jeongwon" not in content
        assert "Clarno" not in content
        assert "Ben Booth" not in content
        # Must not contain internal identifiers
        assert "TRIGA" not in content
        assert "TACC" not in content

    def test_prd_skeleton_fixture_content(self):
        """PRD skeleton has TODO markers and no sensitive data."""
        content = (FIXTURES_DIR / "prd_skeleton_reactor_log.md").read_text()
        assert "[TODO:" in content
        assert "Jeongwon" not in content
        assert "TRIGA" not in content

    def test_commands_reference_valid_fixture_path(self):
        """Act commands that reference the fixture use a resolvable path."""
        scenario = build_scenario()
        for act in scenario.acts:
            for cmd in act.commands:
                if "weekly_summary_demo.md" in cmd:
                    # Path embedded in command must exist on disk
                    path_str = cmd.split()[-1]
                    from pathlib import Path
                    assert Path(path_str).exists(), f"Fixture path in command does not exist: {path_str}"

    def test_runs_in_auto_mode(self):
        """Scenario runs to completion in auto mode."""
        scenario = build_scenario()
        runner = DemoRunner(scenario, auto=True)
        runner.run()
        assert len(runner.completed_acts) >= 1

    def test_setup_teardown_callable(self):
        """Setup and teardown don't raise."""
        scenario = build_scenario()
        if scenario.setup_fn:
            scenario.setup_fn()
        if scenario.teardown_fn:
            scenario.teardown_fn()


class TestScenarioRegistry:
    def test_list_scenarios(self):
        """Scenario registry lists collaborator."""
        from neutron_os.extensions.builtins.demo.scenarios import list_scenarios

        scenarios = list_scenarios()
        assert len(scenarios) >= 1
        slugs = [s["slug"] for s in scenarios]
        assert "collaborator" in slugs

    def test_scenarios_have_metadata(self):
        """Each scenario entry has required fields."""
        from neutron_os.extensions.builtins.demo.scenarios import list_scenarios

        for s in list_scenarios():
            assert "slug" in s
            assert "name" in s
            assert "tagline" in s
            assert "acts" in s


class TestDemoCLI:
    def test_run_requires_scenario_flag(self):
        """neut demo run without a flag exits with usage message."""
        from neutron_os.extensions.builtins.demo.cli import get_parser

        parser = get_parser()
        args = parser.parse_args(["run"])
        assert args.scenario is None  # No scenario selected

    def test_collaborator_flag_sets_scenario(self):
        """--collaborator flag resolves to 'collaborator' scenario."""
        from neutron_os.extensions.builtins.demo.cli import get_parser

        parser = get_parser()
        args = parser.parse_args(["run", "--collaborator"])
        assert args.scenario == "collaborator"

    def test_scenario_flag_passthrough(self):
        """--scenario <name> works for custom scenario names."""
        from neutron_os.extensions.builtins.demo.cli import get_parser

        parser = get_parser()
        args = parser.parse_args(["run", "--scenario", "my-custom-demo"])
        assert args.scenario == "my-custom-demo"

    def test_collaborator_and_scenario_are_mutually_exclusive(self):
        """--collaborator and --scenario cannot be used together."""
        import pytest
        from neutron_os.extensions.builtins.demo.cli import get_parser

        parser = get_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["run", "--collaborator", "--scenario", "other"])

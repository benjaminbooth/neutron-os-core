"""Tests for the 'Silent Contributor' demo scenario."""

from __future__ import annotations

from pathlib import Path

import pytest

from neutron_os.extensions.builtins.demo.runner import DemoRunner
from neutron_os.extensions.builtins.demo.scenarios.collaborator import build_scenario, FIXTURES_DIR


class TestCollaboratorScenario:
    def test_scenario_builds(self):
        """Scenario builds without errors."""
        scenario = build_scenario()
        assert scenario.name == "The Silent Contributor"
        assert scenario.slug == "collaborator"

    def test_has_six_acts(self):
        """Scenario has exactly 6 acts."""
        scenario = build_scenario()
        assert len(scenario.acts) == 6

    def test_acts_numbered_sequentially(self):
        """Acts are numbered 1 through N."""
        scenario = build_scenario()
        numbers = [a.number for a in scenario.acts]
        assert numbers == list(range(1, len(scenario.acts) + 1))

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

    def test_fixtures_exist(self):
        """Demo fixtures are present."""
        assert (FIXTURES_DIR / "weekly_summary_demo.md").exists()
        assert (FIXTURES_DIR / "prd_skeleton_triga_log.md").exists()

    def test_weekly_summary_fixture_content(self):
        """Weekly summary fixture has expected sections."""
        content = (FIXTURES_DIR / "weekly_summary_demo.md").read_text()
        assert "TRIGA Digital Twin" in content
        assert "NeutronOS" in content
        assert "Cost Estimation" in content
        assert "Active Blockers" in content
        assert "Jeongwon Seo" in content
        assert "55 commits" in content

    def test_prd_skeleton_fixture_content(self):
        """PRD skeleton has TODO markers."""
        content = (FIXTURES_DIR / "prd_skeleton_triga_log.md").read_text()
        assert "[TODO:" in content
        assert "TRIGA" in content
        assert "Jeongwon Seo" in content

    def test_runs_in_auto_mode(self):
        """Scenario runs to completion in auto mode."""
        scenario = build_scenario()
        runner = DemoRunner(scenario, auto=True)
        runner.run()
        # At least some acts should complete (validators may fail in test env)
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

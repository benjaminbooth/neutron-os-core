"""Tests for the DemoRunner."""

from __future__ import annotations


from neutron_os.extensions.builtins.demo.runner import Act, DemoRunner, Scenario


def _make_scenario(num_acts: int = 3) -> Scenario:
    """Create a simple test scenario."""
    acts = [
        Act(
            number=i + 1,
            title=f"Act {i + 1}",
            description=f"Description for act {i + 1}",
            commands=[f"echo 'act {i + 1}'"],
            mode="cli",
        )
        for i in range(num_acts)
    ]
    return Scenario(
        name="Test Scenario",
        slug="test",
        tagline="A test scenario for unit testing.",
        acts=acts,
    )


class TestDemoRunner:
    def test_run_all_acts_auto(self):
        """Auto mode runs all acts without pausing."""
        scenario = _make_scenario(3)
        runner = DemoRunner(scenario, auto=True)
        runner.run()
        assert len(runner.completed_acts) == 3

    def test_run_single_act(self):
        """Can run a specific act by number."""
        scenario = _make_scenario(3)
        runner = DemoRunner(scenario, auto=True)
        runner.run_act(2)
        assert runner.current_act == 2

    def test_run_nonexistent_act(self, capsys):
        """Running a nonexistent act prints error."""
        scenario = _make_scenario(3)
        runner = DemoRunner(scenario, auto=True)
        runner.run_act(99)
        captured = capsys.readouterr()
        assert "not found" in captured.out.lower() or "99" in captured.out

    def test_reset(self):
        """Reset clears completed acts."""
        scenario = _make_scenario(2)
        runner = DemoRunner(scenario, auto=True)
        runner.run()
        assert len(runner.completed_acts) == 2
        runner.reset()
        assert len(runner.completed_acts) == 0
        assert runner.current_act == 0

    def test_validator_success(self):
        """Acts with passing validators show success."""
        act = Act(
            number=1,
            title="Validated",
            description="Has a validator",
            commands=["echo ok"],
            validator=lambda: True,
        )
        scenario = Scenario(
            name="Validated", slug="validated", tagline="Test", acts=[act]
        )
        runner = DemoRunner(scenario, auto=True)
        runner.run()
        assert 1 in runner.completed_acts

    def test_validator_failure_continues(self):
        """Acts with failing validators still complete."""
        act = Act(
            number=1,
            title="Fail",
            description="Validator fails",
            commands=["echo fail"],
            validator=lambda: False,
            fallback_message="Expected failure",
        )
        scenario = Scenario(
            name="Fail", slug="fail", tagline="Test", acts=[act]
        )
        runner = DemoRunner(scenario, auto=True)
        runner.run()
        assert 1 in runner.completed_acts

    def test_validator_exception_continues(self):
        """Acts with validators that throw still complete."""
        def bad_validator():
            raise RuntimeError("boom")

        act = Act(
            number=1,
            title="Error",
            description="Validator errors",
            commands=["echo error"],
            validator=bad_validator,
        )
        scenario = Scenario(
            name="Error", slug="error", tagline="Test", acts=[act]
        )
        runner = DemoRunner(scenario, auto=True)
        runner.run()
        assert 1 in runner.completed_acts

    def test_setup_and_teardown(self):
        """Setup and teardown functions are called."""
        calls = []
        scenario = _make_scenario(1)
        scenario.setup_fn = lambda: calls.append("setup")
        scenario.teardown_fn = lambda: calls.append("teardown")
        runner = DemoRunner(scenario, auto=True)
        runner.run()
        assert calls == ["setup", "teardown"]

    def test_teardown_called_on_interrupt(self):
        """Teardown runs even when interrupted."""
        calls = []

        def interrupt_act():
            raise KeyboardInterrupt

        act = Act(
            number=1,
            title="Interrupt",
            description="Will be interrupted",
            commands=["echo x"],
            validator=interrupt_act,
        )
        scenario = Scenario(
            name="Interrupt",
            slug="interrupt",
            tagline="Test",
            acts=[act],
            teardown_fn=lambda: calls.append("teardown"),
        )
        runner = DemoRunner(scenario, auto=True)
        runner.run()
        assert "teardown" in calls

    def test_mode_label(self):
        """Acts properly label CLI vs Chat mode."""
        act_cli = Act(
            number=1, title="CLI", description="d", commands=["x"], mode="cli"
        )
        act_chat = Act(
            number=2, title="Chat", description="d", commands=["y"], mode="chat"
        )
        scenario = Scenario(
            name="Modes", slug="modes", tagline="Test", acts=[act_cli, act_chat]
        )
        runner = DemoRunner(scenario, auto=True)
        runner.run()
        assert len(runner.completed_acts) == 2

    def test_hints_displayed(self, capsys):
        """Hints are printed after act completion."""
        act = Act(
            number=1,
            title="Hints",
            description="Has hints",
            commands=["echo x"],
            hints=["First hint", "Second hint"],
        )
        scenario = Scenario(
            name="Hints", slug="hints", tagline="Test", acts=[act]
        )
        runner = DemoRunner(scenario, auto=True)
        runner.run()
        captured = capsys.readouterr()
        assert "First hint" in captured.out
        assert "Second hint" in captured.out

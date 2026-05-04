"""DemoRunner — orchestrates guided demo scenarios.

Reuses tools/agents/setup/renderer.py for consistent visual language
(same colors/banners as `neut config`). Each act:
  1. Prints banner with act number and title
  2. Explains what's about to happen
  3. Shows the command(s)
  4. Pauses for user to execute
  5. Validates outcome and provides coaching hints
  6. Transitions to next act
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from axiom.setup import renderer


@dataclass
class Act:
    """A single act in a demo scenario."""

    number: int
    title: str
    description: str
    commands: list[str]  # Commands to show the user
    mode: str = "cli"  # "cli" or "chat"
    hints: list[str] = field(default_factory=list)
    validator: Callable[[], bool] | None = None
    fallback_message: str = ""  # Shown if validator fails


@dataclass
class Scenario:
    """A complete demo scenario with multiple acts."""

    name: str
    slug: str  # CLI-friendly name (e.g., "collaborator")
    tagline: str
    acts: list[Act] = field(default_factory=list)
    setup_fn: Callable[[], None] | None = None
    teardown_fn: Callable[[], None] | None = None
    next_steps: list[str] = field(default_factory=list)  # Appended to outro


class DemoRunner:
    """Runs a demo scenario interactively."""

    def __init__(self, scenario: Scenario, *, auto: bool = False):
        self.scenario = scenario
        self.auto = auto  # Skip pauses (for testing)
        self.current_act = 0
        self.completed_acts: list[int] = []

    def run(self) -> None:
        """Run all acts in the scenario."""
        self._print_intro()

        if self.scenario.setup_fn:
            self.scenario.setup_fn()

        try:
            for act in self.scenario.acts:
                self.current_act = act.number
                self._run_act(act)
                self.completed_acts.append(act.number)
        except KeyboardInterrupt:
            renderer.blank()
            renderer.warning("Demo interrupted. Progress saved.")
            self._print_progress()
            return
        finally:
            if self.scenario.teardown_fn:
                self.scenario.teardown_fn()

        self._print_outro()

    def run_act(self, act_number: int) -> None:
        """Run a specific act by number."""
        act = next((a for a in self.scenario.acts if a.number == act_number), None)
        if act is None:
            renderer.error(f"Act {act_number} not found.")
            return
        self._run_act(act)

    def _run_act(self, act: Act) -> None:
        """Execute a single act."""
        self.current_act = act.number
        renderer.blank()
        self._print_act_banner(act)
        renderer.text(act.description)
        renderer.blank()

        # Show commands
        mode_label = "CLI" if act.mode == "cli" else "Chat"
        renderer.info(f"Mode: {mode_label}")
        renderer.blank()

        for cmd in act.commands:
            _print_command(cmd)

        renderer.blank()

        # Pause for user
        if not self.auto:
            self._pause(act)

        # Validate
        if act.validator:
            try:
                ok = act.validator()
            except Exception:
                ok = False
            if ok:
                renderer.success("Act completed successfully.")
            else:
                if act.fallback_message:
                    renderer.warning(act.fallback_message)
                else:
                    renderer.warning("Outcome not verified — continuing anyway.")

        # Hints
        if act.hints:
            renderer.blank()
            renderer.info("Tips:")
            for hint in act.hints:
                renderer.text(f"  - {hint}")

    def _print_intro(self) -> None:
        renderer.banner()
        renderer.blank()
        renderer.heading(f"Demo: {self.scenario.name}")
        renderer.text(self.scenario.tagline)
        renderer.blank()
        renderer.text(f"This demo has {len(self.scenario.acts)} acts.")
        renderer.text("Each act shows commands to run. Execute them, then press Enter to continue.")
        renderer.divider()

    def _print_outro(self) -> None:
        renderer.blank()
        renderer.divider()
        renderer.success(f"Demo complete! All {len(self.scenario.acts)} acts finished.")
        renderer.blank()
        renderer.text("What's next:")
        steps = [
            "Explore your extension: neut ext",
            "Enter chat: neut chat",
            "Generate contract docs: neut ext docs",
            "Read the extension contracts: ~/.neut/EXTENSION_CONTRACTS.md",
        ]
        if self.scenario.next_steps:
            steps.extend(self.scenario.next_steps)
        renderer.numbered_steps(steps)

    def _print_act_banner(self, act: Act) -> None:
        total = len(self.scenario.acts)
        renderer.heading(f"Act {act.number}/{total}: {act.title}")

    def _pause(self, act: Act) -> None:
        """Wait for user to execute commands and return."""
        try:
            input("\n  Run the commands above, then press Enter to continue... ")
        except EOFError:
            pass

    def _print_progress(self) -> None:
        total = len(self.scenario.acts)
        done = len(self.completed_acts)
        renderer.blank()
        renderer.text(f"Progress: {done}/{total} acts completed.")
        if done < total:
            next_act = self.scenario.acts[done].number
            renderer.text(f"Resume with: neut demo run {self.scenario.slug} --from {next_act}")

    def reset(self) -> None:
        """Reset demo state."""
        self.current_act = 0
        self.completed_acts.clear()


def _print_command(cmd: str) -> None:
    """Print a command in a visually distinct way."""
    renderer.text(f"  $ {cmd}")

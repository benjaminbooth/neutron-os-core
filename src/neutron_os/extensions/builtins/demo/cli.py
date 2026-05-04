"""CLI entry point for `neut demo`.

Commands:
  neut demo                     List available demos
  neut demo run <scenario>      Run a demo scenario
  neut demo reset               Clean up demo state
"""

from __future__ import annotations

import argparse
import sys


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neut demo",
        description="Guided demonstrations and walkthroughs",
    )
    sub = parser.add_subparsers(dest="action")

    run_p = sub.add_parser("run", help="Run a demo scenario")
    scenario_group = run_p.add_mutually_exclusive_group()
    scenario_group.add_argument(
        "--collaborator",
        dest="scenario",
        action="store_const",
        const="collaborator",
        help="The Silent Contributor — Jay's onboarding walkthrough",
    )
    scenario_group.add_argument(
        "--scenario",
        dest="scenario",
        metavar="NAME",
        help="Run a scenario by name (for external/custom scenarios)",
    )
    run_p.add_argument("--from", dest="from_act", type=int, default=None, help="Start from act N")
    run_p.add_argument("--auto", action="store_true", help="Skip pauses (for testing)")

    sub.add_parser("reset", help="Reset demo state")
    sub.add_parser("list", help="List available scenarios")

    return parser


def _cmd_list() -> None:
    """List available demo scenarios."""
    from .scenarios import list_scenarios

    scenarios = list_scenarios()
    if not scenarios:
        print("No demo scenarios available.")
        return

    print("Available demos:")
    print()
    for s in scenarios:
        print(f"  {s['slug']:<16} {s['name']} ({s['acts']} acts)")
        print(f"  {'':<16} {s['tagline']}")
        print()
    print("Run a demo:")
    print("  neut demo run --collaborator")
    print("  neut demo run --scenario <name>   (for custom/external scenarios)")


def _cmd_run(args: argparse.Namespace) -> None:
    """Run a demo scenario."""
    from .scenarios import SCENARIOS

    if not args.scenario:
        print("Choose a scenario:")
        print()
        _cmd_list()
        sys.exit(1)

    builder = SCENARIOS.get(args.scenario)
    if builder is None:
        print(f"Unknown scenario: {args.scenario!r}")
        print()
        _cmd_list()
        sys.exit(1)

    from .runner import DemoRunner

    scenario = builder()
    runner = DemoRunner(scenario, auto=args.auto)

    if args.from_act is not None:
        # Run from a specific act
        for act in scenario.acts:
            if act.number >= args.from_act:
                runner.run_act(act.number)
    else:
        runner.run()


def _cmd_reset(args: argparse.Namespace) -> None:
    """Reset demo state."""
    print("Demo state reset.")
    print("  Any review sessions from the demo can be reset with: neut doc review --reset")


def main():
    parser = get_parser()
    args = parser.parse_args()

    if args.action is None:
        _cmd_list()
    elif args.action == "run":
        _cmd_run(args)
    elif args.action == "reset":
        _cmd_reset(args)
    elif args.action == "list":
        _cmd_list()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

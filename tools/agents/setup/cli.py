"""CLI handler for neut setup.

Usage:
    neut setup                Run full wizard (or resume if state exists)
    neut setup --status       Show current configuration status
    neut setup --fix <name>   Reconfigure a specific connection
    neut setup --reset        Clear state and start over
"""

from __future__ import annotations

import sys

import argparse

from tools.agents.setup.state import clear_state
from tools.agents.setup.wizard import SetupWizard


def get_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser.

    Exposed for CLI registry introspection and argcomplete.
    """
    parser = argparse.ArgumentParser(
        prog="neut setup",
        description="Interactive onboarding wizard",
    )
    parser.add_argument("--status", action="store_true", help="Show configuration status")
    parser.add_argument("--fix", metavar="NAME", help="Reconfigure a specific connection")
    parser.add_argument("--reset", action="store_true", help="Clear state and start over")
    return parser


def main() -> None:
    """Entry point for `neut setup`."""
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        _print_help()
        return

    if "--reset" in args:
        clear_state()
        print("  Setup state cleared. Run 'neut setup' to start fresh.")
        return

    wizard = SetupWizard()

    if "--status" in args:
        wizard.show_status()
        return

    if "--fix" in args:
        idx = args.index("--fix")
        if idx + 1 < len(args):
            wizard.fix(args[idx + 1])
        else:
            print("  Usage: neut setup --fix <connection-name>")
            print("  Example: neut setup --fix gitlab_token")
        return

    # Default: run the full wizard
    try:
        wizard.run()
    except KeyboardInterrupt:
        print("\n\n  Setup paused. Run 'neut setup' to resume.\n")
        sys.exit(130)


def _print_help() -> None:
    print("neut setup — Interactive onboarding wizard")
    print()
    print("Usage:")
    print("  neut setup              Run full wizard (or resume)")
    print("  neut setup --status     Show current configuration status")
    print("  neut setup --fix NAME   Reconfigure a specific connection")
    print("  neut setup --reset      Clear state and start over")
    print()
    print("Connections:")
    from tools.agents.setup.guides import CREDENTIAL_GUIDES
    for g in CREDENTIAL_GUIDES:
        tag = "required" if g.required else "optional"
        print(f"  {g.env_var.lower():<30s} {g.display_name} ({tag})")

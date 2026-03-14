"""CLI handler for neut config.

Usage:
    neut config                Run full wizard (or resume if state exists)
    neut config --status       Show current configuration status
    neut config --set <name>   Configure a specific connection
    neut config --reset        Clear state and start over
"""

from __future__ import annotations

import sys

import argparse

from neutron_os.setup.state import clear_state
from neutron_os.setup.wizard import SetupWizard


def get_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser.

    Exposed for CLI registry introspection and argcomplete.
    """
    parser = argparse.ArgumentParser(
        prog="neut config",
        description="Interactive onboarding wizard",
    )
    parser.add_argument("--status", action="store_true", help="Show configuration status")
    parser.add_argument("--set", metavar="NAME", help="Configure a specific connection")
    parser.add_argument("--reset", action="store_true", help="Clear state and start over")
    return parser


def main() -> None:
    """Entry point for `neut config`."""
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        _print_help()
        return

    if "--reset" in args:
        clear_state()
        print("  Setup state cleared. Run 'neut config' to start fresh.")
        return

    wizard = SetupWizard()

    if "--status" in args:
        wizard.show_status()
        return

    if "--set" in args:
        idx = args.index("--set")
        if idx + 1 < len(args):
            wizard.fix(args[idx + 1])
        else:
            print("  Usage: neut config --set <connection-name>")
            print("  Example: neut config --set github_token")
        return

    # Default: run the full wizard
    try:
        wizard.run()
    except KeyboardInterrupt:
        print("\n\n  Setup paused. Run 'neut config' to resume.\n")
        sys.exit(130)


def _print_help() -> None:
    print("neut config — Interactive onboarding wizard")
    print()
    print("Usage:")
    print("  neut config              Run full wizard (or resume)")
    print("  neut config --status     Show current configuration status")
    print("  neut config --set NAME   Configure a specific connection")
    print("  neut config --reset      Clear state and start over")
    print()
    print("Connections:")
    from neutron_os.setup.guides import CREDENTIAL_GUIDES
    for g in CREDENTIAL_GUIDES:
        tag = "required" if g.required else "optional"
        print(f"  {g.env_var.lower():<30s} {g.display_name} ({tag})")

"""CLI handler for ``neut doctor`` — AI-powered diagnostics.

Usage:
    neut doctor                  Run environment diagnostics
    neut doctor "error message"  Diagnose a specific error
    neut doctor --error "msg"    Same, explicit flag
    neut doctor --watch          Watch mode (not yet implemented)
"""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for ``neut doctor``."""
    parser = argparse.ArgumentParser(
        prog="neut doctor",
        description="AI-powered environment diagnostics for Neutron OS.",
    )
    parser.add_argument(
        "error_context",
        nargs="?",
        default=None,
        help="Optional error message or context to diagnose.",
    )
    parser.add_argument(
        "-e", "--error",
        dest="error_flag",
        default=None,
        help="Error message to diagnose (alternative to positional arg).",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        default=False,
        help="Watch mode — continuously monitor for errors.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point — delegates to neut_cli.cmd_doctor."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Resolve error context: --error flag takes precedence over positional
    error_context = args.error_flag or args.error_context

    # Import here to avoid circular imports at module level
    from neutron_os.neut_cli import cmd_doctor

    return cmd_doctor(error_context)

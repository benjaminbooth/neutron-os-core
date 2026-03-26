"""NeutronOS CLI — thin wrapper around Axiom CLI with nuclear extensions.

This delegates to axiom's CLI entry point, which discovers extensions
from both axiom's builtins and neutron-os's nuclear-specific extensions.
"""

from __future__ import annotations


def main():
    """Entry point for `neut` command."""
    from axiom.neut_cli import main as axiom_main

    axiom_main()


if __name__ == "__main__":
    main()

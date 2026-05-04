"""NeutronOS CLI — branded entry point built on Axiom.

Registers Neut branding before handing off to Axiom's dispatcher.
NeutronOS users see "neut" and "Neutron OS" throughout the CLI experience.
The Axiom framework is an implementation detail — invisible to operators.
"""

from __future__ import annotations


def main() -> None:
    """Entry point for the `neut` command."""
    try:
        from axiom.infra.branding import BrandingConfig, register
    except ImportError:
        import sys

        print(
            "Error: the Axiom framework is not installed or has been removed.\n"
            "Reinstall Neutron OS to restore it:\n\n"
            "    pip install neutron-os\n",
            file=sys.stderr,
        )
        sys.exit(1)

    register(
        BrandingConfig(
            cli_name="neut",
            product_name="Neutron OS",
            mascot_name="Neut",
            tagline="The intelligence platform for nuclear power systems",
            package_name="neutron-os",
            banner_fn=_neut_banner,
            shell_comment="Neutron OS CLI shortcut",
        )
    )

    # First-run guidance: if bare `neut` with no args, show quick start
    import sys as _sys

    from axiom.axiom_cli import main as axiom_main

    if len(_sys.argv) <= 1:
        _neut_banner()
        _print_quick_start()
        return

    axiom_main()


def _print_quick_start() -> None:
    """Show friendly quick-start for new users on bare `neut` invocation."""
    try:
        from axiom.setup.renderer import _c, _Colors

        def h(text: str) -> str:
            return _c(_Colors.BOLD, text)

        def d(text: str) -> str:
            return _c(_Colors.DIM, text)
    except Exception:

        def h(text: str) -> str:
            return text

        def d(text: str) -> str:
            return text

    print(h("Quick start:"))
    print()
    print(
        f"  neut model add ./your-deck.i    {d('Register an MCNP model (auto-detects code type)')}"
    )
    print(f"  neut model materials            {d('Browse 11 verified material compositions')}")
    print(f"  neut model materials --card UO2 {d('Generate MCNP material cards')}")
    print(f"  neut facility list              {d('See available facility packs')}")
    print(f"  neut chat                       {d('Ask questions with RAG-grounded answers')}")
    print(f"  neut doctor                     {d('Check your setup')}")
    print()
    print(f"  neut --help                     {d('All commands')}")
    print(f"  neut model --help               {d('Model registry commands')}")
    print()


_NEUT_ART = r"""
      ╭────────────╮
      │  ◕      ◕  │   \│/
      │   ╮────╭   ═══════
      ╰───┬────┬───╯   /│\
          ┘    └
    N  E  U  T  R  O  N     O  S
"""


def _neut_banner() -> None:
    """Print the Neut mascot banner — art owned by NeutronOS, not Axiom."""
    try:
        from axiom.setup.renderer import _c, _Colors  # pylint: disable=import-outside-toplevel

        for line in _NEUT_ART.strip("\n").splitlines():
            print(_c(_Colors.BOLD + _Colors.ACCENT_BLUE, line))
        print()
    except Exception:  # pylint: disable=broad-exception-caught
        print("\n  Neutron OS\n")


if __name__ == "__main__":
    main()

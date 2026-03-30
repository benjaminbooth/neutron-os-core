"""NeutronOS CLI — branded entry point built on Axiom.

Registers Neut branding before handing off to Axiom's dispatcher.
NeutronOS users see "neut" and "Neutron OS" throughout the CLI experience.
The Axiom framework is an implementation detail — invisible to operators.
"""

from __future__ import annotations


def main() -> None:
    """Entry point for the `neut` command."""
    from axiom.infra.branding import BrandingConfig, register

    register(BrandingConfig(
        cli_name="neut",
        product_name="Neutron OS",
        mascot_name="Neut",
        tagline="The intelligence platform for nuclear power systems",
        package_name="neutron-os",
        banner_fn=_neut_banner,
        shell_comment="Neutron OS CLI shortcut",
    ))

    from axiom.neut_cli import main as axiom_main
    axiom_main()


def _neut_banner() -> None:
    """Print the Neut mascot banner."""
    try:
        from axiom.setup.renderer import _NEUT_BANNER, _c, _Colors
        for line in _NEUT_BANNER.strip("\n").splitlines():
            print(_c(_Colors.BOLD + _Colors.ACCENT_BLUE, line))
        print()
    except Exception:
        print("\n  Neutron OS\n")


if __name__ == "__main__":
    main()

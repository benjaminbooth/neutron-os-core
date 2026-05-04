"""CLI handler for `neut facility` — facility pack management.

Usage:
    neut facility list                    List installed facility packs
    neut facility show <name>             Show pack details
    neut facility install <path>          Install a facility pack
    neut facility uninstall <name>        Remove a facility pack
    neut facility init <name>             Scaffold a new facility pack
    neut facility publish <path>          Create .facilitypack archive
    neut facility materials <name>        List materials from a pack
    neut facility sync                    Sync facility packs with federation peers
"""

from __future__ import annotations

import argparse
import json
import sys

# Progressive disclosure — graceful degradation if axiom.infra.cli_tiers unavailable
try:
    from axiom.infra.cli_tiers import get_user_tier, should_show_command

    _HAS_CLI_TIERS = True
except ImportError:
    _HAS_CLI_TIERS = False


def _make_tiered_print_help(parser: argparse.ArgumentParser, noun: str):
    """Create a print_help method that filters subcommands by user tier."""
    _original_print_help = parser.print_help

    def _print_help(file=None):
        if not _HAS_CLI_TIERS:
            return _original_print_help(file)

        try:
            tier = get_user_tier()
        except Exception:
            return _original_print_help(file)

        # Save originals and filter
        saved = {}
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                saved["npm"] = action._name_parser_map.copy()
                saved["choices"] = dict(action.choices) if action.choices else {}
                saved["choices_actions"] = list(action._choices_actions)
                hidden = [
                    name
                    for name in list(action._name_parser_map.keys())
                    if not should_show_command(noun, name, tier)
                ]
                hidden_set = set(hidden)
                for name in hidden:
                    del action._name_parser_map[name]
                action.choices = {k: v for k, v in action.choices.items() if k not in hidden_set}
                action._choices_actions = [
                    ca for ca in action._choices_actions if ca.dest not in hidden_set
                ]
                break
        else:
            hidden = []

        _original_print_help(file)

        # Restore
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction) and saved:
                action._name_parser_map = saved["npm"]
                action.choices = saved["choices"]
                action._choices_actions = saved["choices_actions"]
                break

        # Append hint
        if hidden and tier < 4:
            import sys as _sys

            out = file or _sys.stdout
            try:
                from axiom.infra.branding import get_branding as _gb_tier

                _tier_cli = _gb_tier().cli_name
            except Exception:
                _tier_cli = "neut"
            out.write(
                f"\n  ({len(hidden)} more commands available at higher tiers."
                f" Run `{_tier_cli} settings set cli.tier {tier + 1}` to unlock.)\n"
            )

    parser.print_help = _print_help


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neut facility",
        description="Facility pack management — reactor-specific accelerators",
    )
    sub = parser.add_subparsers(dest="action")

    # list
    list_p = sub.add_parser("list", help="List installed facility packs")
    list_p.add_argument("--format", choices=["human", "json"], default="human")

    # show
    show_p = sub.add_parser("show", help="Show pack details")
    show_p.add_argument("name", help="Facility pack name")
    show_p.add_argument("--format", choices=["human", "json"], default="human")

    # install
    install_p = sub.add_parser("install", help="Install a facility pack")
    install_p.add_argument("path", help="Path to pack directory or .facilitypack archive")
    install_p.add_argument(
        "--target", choices=["user", "project"], default="user", help="Install location"
    )
    install_p.add_argument("--json", action="store_true", help="Output JSON")

    # uninstall
    uninst_p = sub.add_parser("uninstall", help="Remove a facility pack")
    uninst_p.add_argument("name", help="Facility pack name")
    uninst_p.add_argument(
        "--target", choices=["user", "project"], default="user", help="Install location"
    )
    uninst_p.add_argument("--confirm", action="store_true", help="Confirm destructive operation")
    uninst_p.add_argument("--json", action="store_true", help="Output JSON")

    # init
    init_p = sub.add_parser("init", help="Scaffold a new facility pack")
    init_p.add_argument("name", help="Pack name (e.g., MY-REACTOR)")
    init_p.add_argument("--reactor-type", default="custom", help="Reactor type")
    init_p.add_argument("--maintainer", default="", help="Maintainer name/email")
    init_p.add_argument("--json", action="store_true", help="Output JSON")

    # publish
    pub_p = sub.add_parser("publish", help="Create .facilitypack archive")
    pub_p.add_argument("path", help="Path to pack directory")
    pub_p.add_argument("-o", "--output", help="Output file path")
    pub_p.add_argument("--json", action="store_true", help="Output JSON")

    # sync
    sync_p = sub.add_parser("sync", help="Sync facility packs with federation peers")
    sync_p.add_argument("--json", action="store_true", help="Output JSON")

    # materials
    mat_p = sub.add_parser("materials", help="List materials from a facility pack")
    mat_p.add_argument("name", help="Facility pack name")
    mat_p.add_argument("--format", choices=["human", "json", "mcnp", "mpact"], default="human")

    _make_tiered_print_help(parser, "facility")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.action:
        parser.print_help()
        return 1

    handlers = {
        "list": _cmd_list,
        "show": _cmd_show,
        "install": _cmd_install,
        "uninstall": _cmd_uninstall,
        "init": _cmd_init,
        "publish": _cmd_publish,
        "materials": _cmd_materials,
        "sync": _cmd_sync,
    }

    handler = handlers.get(args.action)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


def _cmd_list(args) -> int:
    from .registry import discover_packs

    packs = discover_packs()
    output_json = getattr(args, "format", "human") == "json"

    if not packs:
        if output_json:
            print(json.dumps([], indent=2))
        else:
            print("No facility packs installed.")
            print("\nInstall a builtin pack:")
            print("  neut facility install NETL-TRIGA")
        return 0

    if output_json:
        print(json.dumps([p.to_dict() for p in packs], indent=2))
    else:
        print(f"{'Name':<20} {'Reactor':<10} {'Version':<10} {'Source':<10} {'Description'}")
        print("-" * 80)
        for p in packs:
            desc = p.manifest.description[:35] if p.manifest.description else ""
            print(
                f"{p.name:<20} {p.manifest.reactor_type:<10} "
                f"v{p.manifest.version:<9} {p.source:<10} {desc}"
            )
        print(f"\n{len(packs)} pack(s) installed.")
    return 0


def _cmd_show(args) -> int:
    from .registry import get_pack

    pack = get_pack(args.name)
    if pack is None:
        print(f"Facility pack not found: {args.name}")
        return 1

    if getattr(args, "format", "human") == "json":
        print(json.dumps(pack.to_dict(), indent=2))
    else:
        m = pack.manifest
        print(f"Facility Pack: {m.display_name}")
        print(f"  Name:        {m.name}")
        print(f"  Reactor:     {m.reactor_type}")
        print(f"  Version:     {m.version}")
        print(f"  Maintainer:  {m.maintainer}")
        print(f"  License:     {m.license}")
        print(f"  Source:      {pack.source}")
        print(f"  Path:        {pack.path}")
        if m.description:
            print(f"  Description: {m.description[:100]}")
        if m.tags:
            print(f"  Tags:        {', '.join(m.tags)}")

        # Show contents
        sections = []
        if pack.materials_path.exists():
            mat_files = list(pack.materials_path.glob("*.yaml"))
            sections.append(f"{len(mat_files)} material file(s)")
        if pack.templates_path.exists():
            tmpl_dirs = [d for d in pack.templates_path.iterdir() if d.is_dir()]
            sections.append(f"{len(tmpl_dirs)} template(s)")
        if pack.parameters_path.exists():
            param_files = list(pack.parameters_path.glob("*.yaml"))
            sections.append(f"{len(param_files)} parameter file(s)")
        if pack.coreforge_path.exists():
            cf_files = list(pack.coreforge_path.glob("*.py"))
            sections.append(f"{len(cf_files)} CoreForge config(s)")

        if sections:
            print(f"\n  Contents: {', '.join(sections)}")

    return 0


def _cmd_install(args) -> int:
    from pathlib import Path

    from .registry import install_pack

    try:
        pack = install_pack(Path(args.path), target=args.target)
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "name": pack.name,
                        "version": pack.manifest.version,
                        "path": str(pack.path),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Installed: {pack.name} v{pack.manifest.version}")
            print(f"  Location: {pack.path}")
            print(f"\nMaterials are now available via: neut facility materials {pack.name}")
        return 0
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}")
        return 1


def _cmd_uninstall(args) -> int:
    from .registry import uninstall_pack

    if not getattr(args, "confirm", False):
        print(f"This will remove facility pack '{args.name}'. Pass --confirm to proceed.")
        return 1

    if uninstall_pack(args.name, target=args.target):
        if getattr(args, "json", False):
            print(json.dumps({"name": args.name, "removed": True}, indent=2))
        else:
            print(f"Removed: {args.name}")
        return 0
    if getattr(args, "json", False):
        print(json.dumps({"name": args.name, "removed": False, "error": "not found"}, indent=2))
    else:
        print(f"Pack not found: {args.name}")
    return 1


def _cmd_init(args) -> int:
    from .registry import init_pack

    try:
        pack_dir = init_pack(
            args.name,
            reactor_type=getattr(args, "reactor_type", "custom"),
            maintainer=getattr(args, "maintainer", ""),
        )
        if getattr(args, "json", False):
            print(json.dumps({"path": str(pack_dir), "name": args.name}, indent=2))
        else:
            print(f"Created: {pack_dir}/")
            print("\nNext steps:")
            print(f"  1. Add material YAML files to {pack_dir}/materials/")
            print(f"  2. Edit {pack_dir}/manifest.yaml")
            print(f"  3. Run: neut facility publish {pack_dir}")
        return 0
    except FileExistsError as e:
        print(f"Error: {e}")
        return 1


def _cmd_publish(args) -> int:
    from pathlib import Path

    from .registry import publish_pack

    try:
        output = getattr(args, "output", None)
        archive = publish_pack(
            Path(args.path),
            output=Path(output) if output else None,
        )
        if getattr(args, "json", False):
            print(json.dumps({"path": str(archive)}, indent=2))
        else:
            print(f"Published: {archive}")
        return 0
    except ValueError as e:
        print(f"Error: {e}")
        return 1


def _cmd_materials(args) -> int:
    from .registry import get_pack

    pack = get_pack(args.name)
    if pack is None:
        print(f"Facility pack not found: {args.name}")
        return 1

    if not pack.materials_path.exists():
        print(f"No materials in pack: {args.name}")
        return 0

    # Load materials from pack YAML files
    from neutron_os.extensions.builtins.model_corral.materials_db import (
        YamlMaterialSource,
    )

    source = YamlMaterialSource(pack.materials_path, source_name=f"facility:{args.name}")
    materials = source.load()

    fmt = getattr(args, "format", "human")

    if fmt == "json":
        print(json.dumps([m.to_dict() for m in materials], indent=2))
    elif fmt in ("mcnp", "mpact"):
        for i, m in enumerate(materials, 1):
            if fmt == "mcnp":
                print(m.mcnp_cards(mat_number=i))
            else:
                print(m.mpact_card())
            print()
    elif not materials:
        print(f"No materials in pack: {args.name}")
    else:
        print(f"Materials in {pack.manifest.display_name}:\n")
        print(f"{'Name':<15} {'Category':<12} {'Density':<10} {'Description'}")
        print("-" * 75)
        for m in materials:
            print(f"{m.name:<15} {m.category:<12} {m.density:<10.3f} {m.description[:40]}")
        print(f"\n{len(materials)} material(s).")

    return 0


def _cmd_sync(args) -> int:
    from neutron_os.extensions.builtins.model_corral.federation import (
        list_federation_materials,
    )

    materials = list_federation_materials()
    output_json = getattr(args, "json", False)

    if not materials:
        if output_json:
            print(json.dumps([], indent=2))
        else:
            print("No federation materials available.")
            print("\nReceive packs from federation peers first:")
            print("  neut model receive <path-to-.axiompack>")
        return 0

    if output_json:
        print(json.dumps(materials, indent=2))
    else:
        # Group by source pack
        packs: dict[str, list] = {}
        for m in materials:
            packs.setdefault(m["source_pack"], []).append(m)

        print(f"Federation materials from {len(packs)} peer pack(s):\n")
        for pack_name, mats in sorted(packs.items()):
            print(f"  {pack_name} ({len(mats)} material(s)):")
            for m in mats:
                print(f"    {m['name']:<15} {m['category']:<12} {m['density']:.3f} g/cm3")
        print(f"\nTotal: {len(materials)} material(s) from federation peers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

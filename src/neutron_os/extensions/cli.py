"""CLI entry point for `neut ext`.

Commands:
  neut ext                  List installed extensions
  neut ext init <name>      Scaffold new extension
  neut ext docs             Generate EXTENSION_CONTRACTS.md
  neut ext check <name>     Validate an extension
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neut ext",
        description="Manage NeutronOS extensions",
    )
    sub = parser.add_subparsers(dest="action")

    # neut ext init <name>
    init_p = sub.add_parser("init", help="Scaffold a new extension")
    init_p.add_argument("name", help="Extension name")
    init_p.add_argument("--dir", help="Base directory (default: ~/.neut/extensions/)")
    init_p.add_argument("--author", default="", help="Author name")
    init_p.add_argument("--description", default="", help="Extension description")

    # neut ext docs
    sub.add_parser("docs", help="Generate EXTENSION_CONTRACTS.md")

    # neut ext check <name>
    check_p = sub.add_parser("check", help="Validate an extension")
    check_p.add_argument("name", help="Extension name to validate")

    return parser


def _cmd_list() -> None:
    """List installed extensions."""
    from neutron_os.extensions.discovery import discover_extensions

    extensions = discover_extensions()
    if not extensions:
        print("No extensions installed.")
        print()
        print("Get started:")
        print("  neut ext init my-extension    # Create a new extension")
        print("  neut ext docs                 # View extension contracts")
        return

    print(f"{'Name':<20} {'Version':<10} {'Type':<10} {'Capabilities'}")
    print("-" * 70)
    for ext in extensions:
        caps = ", ".join(ext.capabilities) if ext.capabilities else "(empty)"
        tag = "[builtin]" if ext.builtin else "[user]"
        status = " [disabled]" if not ext.enabled else ""
        print(f"{ext.name:<20} {ext.version:<10} {tag:<10} {caps}{status}")

    n_builtin = sum(1 for e in extensions if e.builtin)
    n_user = len(extensions) - n_builtin
    parts = []
    if n_builtin:
        parts.append(f"{n_builtin} builtin")
    if n_user:
        parts.append(f"{n_user} user")
    print()
    print(f"{len(extensions)} extension(s) installed ({', '.join(parts)}).")


def _cmd_init(args: argparse.Namespace) -> None:
    """Scaffold a new extension."""
    from neutron_os.extensions.scaffold import scaffold_extension

    base_dir = Path(args.dir) if args.dir else None

    try:
        ext_dir = scaffold_extension(
            args.name,
            base_dir=base_dir,
            author=args.author,
            description=args.description,
        )
    except FileExistsError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"Extension scaffolded: {ext_dir}")
    print()
    print("Created:")
    print(f"  {ext_dir}/neut-extension.toml     Manifest")
    print(f"  {ext_dir}/tools_ext/              Chat tools")
    print(f"  {ext_dir}/skills/weekly-slides/   SKILL.md")
    print(f"  {ext_dir}/providers/              Docflow providers")
    print(f"  {ext_dir}/cli/                    CLI commands")
    print(f"  {ext_dir}/extractors/             Sense extractors")
    print()
    print("Next steps:")
    print("  neut ext                    # Verify it appears")
    print(f"  neut ext check {args.name}  # Validate")
    print("  neut chat                   # Chat tools are available immediately")


def _cmd_docs(args: argparse.Namespace) -> None:
    """Generate EXTENSION_CONTRACTS.md."""
    from neutron_os.extensions.discovery import generate_contract_docs

    docs = generate_contract_docs()
    out_path = Path.home() / ".neut" / "EXTENSION_CONTRACTS.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(docs, encoding="utf-8")
    print(f"Contract docs written to: {out_path}")
    print()
    print("Paste this file into your AI assistant's context (Claude, Gemini, Cursor)")
    print("so it can generate NeutronOS extensions automatically.")


def _cmd_check(args: argparse.Namespace) -> None:
    """Validate an extension."""
    from neutron_os.extensions.contracts import validate_extension
    from neutron_os.extensions.discovery import discover_extensions

    extensions = discover_extensions()
    ext = next((e for e in extensions if e.name == args.name), None)

    if ext is None:
        print(f"Extension not found: {args.name}")
        print()
        print("Installed extensions:")
        for e in extensions:
            print(f"  {e.name}")
        if not extensions:
            print("  (none)")
        sys.exit(1)

    issues = validate_extension(ext)

    if issues:
        print(f"Validation failed for {args.name}:")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)
    else:
        print(f"Extension {args.name} is valid.")
        print()
        print(f"  Root:         {ext.root}")
        print(f"  Version:      {ext.version}")
        print(f"  Author:       {ext.author or '(not set)'}")
        print(f"  Capabilities: {', '.join(ext.capabilities) or '(none)'}")


def main():
    parser = get_parser()
    args = parser.parse_args()

    if args.action is None:
        _cmd_list()
    elif args.action == "init":
        _cmd_init(args)
    elif args.action == "docs":
        _cmd_docs(args)
    elif args.action == "check":
        _cmd_check(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

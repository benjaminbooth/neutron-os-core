"""neut settings — view and edit neut configuration.

Modeled on Claude Code's settings UX:
  neut settings                              show all active settings
  neut settings get routing.default_mode     read a value
  neut settings set routing.default_mode auto
  neut settings --global set routing.cloud_provider openai
  neut settings reset routing.default_mode   remove project override
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from .store import SettingsStore


def _fmt_value(v: Any) -> str:
    if isinstance(v, bool):
        return str(v).lower()
    return str(v)


def _print_table(settings: dict[str, Any]) -> None:
    """Print settings as a two-column table, grouped by section."""
    from collections import defaultdict

    sections: dict[str, dict[str, Any]] = defaultdict(dict)
    for k, v in sorted(settings.items()):
        parts = k.split(".", 1)
        section = parts[0] if len(parts) > 1 else "general"
        leaf = parts[1] if len(parts) > 1 else parts[0]
        sections[section][leaf] = v

    col_width = max((len(k) for s in sections.values() for k in s), default=20) + 2

    for section, items in sorted(sections.items()):
        print(f"\n  [{section}]")
        for key, val in sorted(items.items()):
            dotted = f"{section}.{key}"
            print(f"    {dotted:<{col_width}}  {_fmt_value(val)}")
    print()


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neut settings",
        description="View and edit neut configuration",
    )
    parser.add_argument(
        "--global", dest="global_scope", action="store_true",
        help="Operate on global settings (~/.neut/settings.toml)",
    )
    sub = parser.add_subparsers(dest="cmd")

    get_p = sub.add_parser("get", help="Read a setting value")
    get_p.add_argument("key", help="Dotted key, e.g. routing.default_mode")

    set_p = sub.add_parser("set", help="Write a setting value")
    set_p.add_argument("key", help="Dotted key, e.g. routing.default_mode")
    set_p.add_argument("value", help="New value")

    reset_p = sub.add_parser("reset", help="Remove a setting override")
    reset_p.add_argument("key", help="Dotted key to reset")

    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()
    scope = "global" if args.global_scope else "project"
    store = SettingsStore()

    if args.cmd is None:
        # Show all settings
        settings = store.all()
        if args.global_scope:
            from .store import _flatten, _load_toml, _GLOBAL_SETTINGS_PATH
            settings = _flatten(_load_toml(_GLOBAL_SETTINGS_PATH))
        if not settings:
            print("\n  No settings configured. Using defaults.\n")
            settings = store.all()
        _print_table(settings)
        return

    if args.cmd == "get":
        val = store.get(args.key)
        if val is None:
            print(f"  (not set — no default)", file=sys.stderr)
            sys.exit(1)
        print(_fmt_value(val))
        return

    if args.cmd == "set":
        # Coerce common types
        raw = args.value
        if raw.lower() in ("true", "yes"):
            value: Any = True
        elif raw.lower() in ("false", "no"):
            value = False
        else:
            try:
                value = int(raw)
            except ValueError:
                value = raw

        store.set(args.key, value, scope=scope)
        target = "~/.neut/settings.toml" if scope == "global" else "runtime/config/settings.toml"
        print(f"  {args.key} = {_fmt_value(value)}  →  {target}")
        return

    if args.cmd == "reset":
        removed = store.reset(args.key, scope=scope)
        if removed:
            print(f"  Removed override: {args.key} ({scope})")
        else:
            print(f"  {args.key} not set in {scope} scope (nothing to reset)")
        return

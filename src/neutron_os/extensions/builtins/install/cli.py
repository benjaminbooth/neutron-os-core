"""neut install — environment-aware setup runner.

Usage:
    neut install                  detect environment and run pending steps
    neut install --env rascal     force a specific environment
    neut install --list           show environments and step status
    neut install --force          re-run all steps (ignore state)
    neut install --step <id>      run a single step by id
"""

from __future__ import annotations

import argparse
import sys

from .installer import (
    Environment,
    InstallStep,
    detect_environment,
    load_manifest,
    run_step,
    _load_state,
    _save_state,
)


def _print_status(env: Environment, state: dict) -> None:
    print(f"\n  Environment: {env.name}")
    if env.description:
        print(f"  {env.description}")
    print()
    print(f"  {'Step':<35} {'Status'}")
    print("  " + "─" * 50)
    for step in env.steps:
        done = state.get(step.id, False)
        symbol = "✓" if done else "○"
        label = step.description or step.id
        print(f"  {symbol} {label:<33} {'done' if done else 'pending'}")
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neut install",
        description="Run environment setup steps from runtime/config/install.toml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  neut install                  Auto-detect environment and run pending steps
  neut install --env rascal     Run rascal environment steps
  neut install --list           Show step status without running anything
  neut install --force          Re-run all steps (ignore completion state)
  neut install --step connect-qwen-rascal   Run one step by id
""",
    )
    parser.add_argument("--env", metavar="NAME", help="Override environment detection")
    parser.add_argument("--list", action="store_true", help="Show step status and exit")
    parser.add_argument("--force", action="store_true", help="Re-run all steps")
    parser.add_argument("--step", metavar="ID", help="Run a single step by id")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    envs = load_manifest()
    if not envs:
        print("\n  No install.toml found.")
        print("  Copy runtime/config.example/install.toml to runtime/config/install.toml")
        print("  and customize for your environment.\n")
        return 1

    env = detect_environment(envs, override=args.env or "")
    if env is None:
        if args.env:
            print(f"\n  Environment '{args.env}' not found in install.toml")
            print(f"  Available: {', '.join(e.name for e in envs)}\n")
            return 1
        print("\n  No matching environment detected.")
        print(f"  Available environments: {', '.join(e.name for e in envs)}")
        print("  Use --env <name> to specify one, or set NEUT_ENV=<name>\n")
        return 1

    state = _load_state()

    if args.list:
        _print_status(env, state)
        return 0

    # Single step override
    if args.step:
        step = next((s for s in env.steps if s.id == args.step), None)
        if step is None:
            print(f"\n  Step '{args.step}' not found in environment '{env.name}'")
            ids = [s.id for s in env.steps]
            print(f"  Available: {', '.join(ids)}\n")
            return 1
        ok = run_step(step, state, force=True)
        _save_state(state)
        return 0 if ok else 1

    # Run all pending steps
    print(f"\n  NeutronOS Install — {env.name}")
    if env.description:
        print(f"  {env.description}")
    print()

    total = len(env.steps)
    completed = sum(1 for s in env.steps if state.get(s.id))
    pending = total - completed

    if pending == 0 and not args.force:
        print(f"  ✓ All {total} steps complete. Use --force to re-run.\n")
        return 0

    print(f"  {completed}/{total} steps complete — running {pending} pending steps")

    any_failed = False
    for step in env.steps:
        ok = run_step(step, state, force=args.force)
        _save_state(state)
        if not ok and step.type != "connect":
            # connect steps can be skipped (user may not have key yet)
            any_failed = True

    print()
    done_count = sum(1 for s in env.steps if state.get(s.id))
    print(f"  {done_count}/{total} steps complete")

    if done_count == total:
        print("  ✓ Installation complete\n")
    else:
        remaining = [s.id for s in env.steps if not state.get(s.id)]
        print(f"  Remaining: {', '.join(remaining)}")
        print("  Re-run `neut install` after addressing any issues\n")

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())

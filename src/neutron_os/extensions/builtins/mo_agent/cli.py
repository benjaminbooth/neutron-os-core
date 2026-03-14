"""CLI handler for `neut mo` — M-O resource steward commands.

Usage:
    neut mo status       Base path, disk free, active entries, pressure level
    neut mo ls           Table of all tracked entries
    neut mo clean        Sweep expired + orphaned entries
    neut mo purge        Delete everything (confirmation prompt)
    neut mo vitals       Live vitals: disk %, mem %, trend arrows, top owners
    neut mo diagnose     Trigger Layer 3 LLM diagnosis (requires gateway)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neut mo",
        description="M-O — Autonomous Resource Steward",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  neut mo status       # Show scratch space status
  neut mo ls           # List all tracked entries
  neut mo clean        # Sweep expired and orphaned entries
  neut mo purge        # Delete all scratch entries
  neut mo vitals       # Detailed vitals snapshot
  neut mo diagnose     # LLM-powered diagnosis
""",
    )

    sub = parser.add_subparsers(dest="action")

    sub.add_parser("status", help="Show M-O status")
    sub.add_parser("ls", help="List all tracked entries")
    sub.add_parser("clean", help="Sweep expired and orphaned entries")

    purge_p = sub.add_parser("purge", help="Delete all scratch entries")
    purge_p.add_argument(
        "-y", "--yes", action="store_true",
        help="Skip confirmation prompt",
    )

    sub.add_parser("vitals", help="Detailed vitals snapshot")
    sub.add_parser("diagnose", help="LLM-powered diagnosis (requires gateway)")

    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.action:
        args.action = "status"

    handlers = {
        "status": _cmd_status,
        "ls": _cmd_ls,
        "clean": _cmd_clean,
        "purge": _cmd_purge,
        "vitals": _cmd_vitals,
        "diagnose": _cmd_diagnose,
    }

    handler = handlers.get(args.action)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


def _get_manager():
    from . import manager
    return manager()


def _cmd_status(args) -> int:
    mgr = _get_manager()
    info = mgr.status()

    if getattr(args, "json", False):
        print(json.dumps(info, indent=2))
        return 0

    print("M-O Status")
    print(f"  Base:      {info['base_dir']}")

    used = _fmt_bytes(info["total_size_bytes"])
    free = _fmt_bytes(info["disk_free_bytes"])
    pct = info["disk_used_pct"]
    print(f"  Disk:      {used} used  {free} free ({pct}%)")

    # Memory (if psutil available)
    try:
        import os
        import psutil
        rss = psutil.Process(os.getpid()).memory_info().rss
        print(f"  Memory:    {_fmt_bytes(rss)} RSS")
    except (ImportError, Exception):
        pass

    # Pressure
    try:
        from .vitals import VitalsMonitor
        from .network import NetworkLedger
        monitor = VitalsMonitor(mgr, NetworkLedger.shared())
        monitor.sample()
        pressure = monitor.check_pressure()
        print(f"  Pressure:  {pressure}")

        leaks = monitor.detect_leaks()
        if leaks:
            print(f"  Leaks:     {len(leaks)} detected")
            for leak in leaks:
                print(f"             {leak.evidence}")
        else:
            print("  Leaks:     none detected")
    except Exception:
        print("  Pressure:  unknown (vitals unavailable)")

    # Entry summary
    entries = mgr.all_entries()
    dirs = sum(1 for e in entries if e.is_dir)
    files = len(entries) - dirs
    parts = []
    if dirs:
        parts.append(f"{dirs} dir{'s' if dirs != 1 else ''}")
    if files:
        parts.append(f"{files} file{'s' if files != 1 else ''}")
    detail = f" ({', '.join(parts)})" if parts else ""
    print(f"  Active:    {len(entries)} entries{detail}")

    if not entries:
        print()
        return 0

    # Entry table
    print()
    print(f"  {'Owner':<20} {'Type':<6} {'Retention':<10} {'Age':<9} {'Size':<10}")
    now = datetime.now(timezone.utc)
    for e in entries:
        etype = "dir" if e.is_dir else "file"
        age = _fmt_age(e.created_at, now)
        from pathlib import Path
        size = _fmt_bytes(mgr._measure_size(Path(e.path), e.is_dir))
        print(f"  {e.owner:<20} {etype:<6} {e.retention:<10} {age:<9} {size:<10}")

    print()
    return 0


def _cmd_ls(args) -> int:
    mgr = _get_manager()
    entries = mgr.all_entries()

    if getattr(args, "json", False):
        print(json.dumps([e.to_dict() for e in entries], indent=2))
        return 0

    if not entries:
        print("No active M-O entries.")
        return 0

    now = datetime.now(timezone.utc)
    print(f"{'ID':<14} {'Owner':<20} {'Type':<6} {'Retention':<10} {'PID':<8} {'Age':<9} {'Path'}")
    print("-" * 100)
    for e in entries:
        etype = "dir" if e.is_dir else "file"
        age = _fmt_age(e.created_at, now)
        # Shorten path for display
        path = e.path
        if len(path) > 40:
            path = "..." + path[-37:]
        print(f"{e.id:<14} {e.owner:<20} {etype:<6} {e.retention:<10} {e.pid:<8} {age:<9} {path}")

    print(f"\n{len(entries)} entries")
    return 0


def _cmd_clean(args) -> int:
    mgr = _get_manager()
    result = mgr.sweep()

    if getattr(args, "json", False):
        print(json.dumps(result, indent=2))
        return 0

    total = result["expired"] + result["orphaned"]
    if total == 0:
        print("Nothing to clean.")
    else:
        print(f"Cleaned {total} entries ({result['expired']} expired, {result['orphaned']} orphaned)")
        if result["errors"]:
            print(f"  {result['errors']} errors during cleanup")

    return 0


def _cmd_purge(args) -> int:
    mgr = _get_manager()
    entries = mgr.all_entries()

    if not entries:
        print("Nothing to purge.")
        return 0

    if not getattr(args, "yes", False):
        print(f"This will delete {len(entries)} entries and all scratch data.")
        try:
            response = input("Continue? [y/N] ")
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return 1
        if response.lower() not in ("y", "yes"):
            print("Aborted.")
            return 1

    result = mgr.purge()

    if getattr(args, "json", False):
        print(json.dumps(result, indent=2))
        return 0

    print(f"Purged {result['deleted']} entries.")
    return 0


def _cmd_vitals(args) -> int:
    try:
        from .vitals import VitalsMonitor
        from .network import NetworkLedger
    except ImportError as e:
        print(f"Vitals unavailable: {e}")
        return 1

    mgr = _get_manager()
    monitor = VitalsMonitor(mgr, NetworkLedger.shared())
    snap = monitor.sample()
    pressure = monitor.check_pressure()
    leaks = monitor.detect_leaks()

    if getattr(args, "json", False):
        data = snap.to_dict()
        data["pressure"] = pressure
        data["leaks"] = [
            {"owner": leak.owner, "pattern": leak.pattern, "evidence": leak.evidence}
            for leak in leaks
        ]
        print(json.dumps(data, indent=2))
        return 0

    print("M-O Vitals")
    print("=" * 50)
    print(f"  Scratch:   {_fmt_bytes(snap.scratch_used_bytes)} used / "
          f"{_fmt_bytes(snap.scratch_free_bytes)} free "
          f"({snap.scratch_pct:.1f}%)")

    if snap.process_rss_bytes is not None:
        print(f"  Memory:    {_fmt_bytes(snap.process_rss_bytes)} RSS")
    if snap.system_mem_pct is not None:
        print(f"  System:    {snap.system_mem_pct:.1f}% memory used")

    print(f"  Pressure:  {pressure}")
    print(f"  Entries:   {snap.active_entries}")

    if snap.entries_by_owner:
        print()
        print("  Top owners:")
        for owner, count in sorted(
            snap.entries_by_owner.items(),
            key=lambda x: snap.bytes_by_owner.get(x[0], 0),
            reverse=True,
        )[:5]:
            size = _fmt_bytes(snap.bytes_by_owner.get(owner, 0))
            print(f"    {owner:<25} {count} entries  {size}")

    if snap.net and snap.net.total_requests > 0:
        print()
        print("  Network (5m window):")
        print(f"    Requests:  {snap.net.total_requests} "
              f"({snap.net.total_errors} errors, {snap.net.error_rate_pct:.1f}%)")
        print(f"    Latency:   avg {snap.net.avg_latency_ms:.0f}ms, "
              f"p95 {snap.net.p95_latency_ms:.0f}ms")
        if snap.net.anomalies:
            print(f"    Anomalies: {len(snap.net.anomalies)}")
            for a in snap.net.anomalies:
                print(f"      [{a.severity}] {a.kind}: {a.evidence}")

    if leaks:
        print()
        print(f"  Leaks ({len(leaks)}):")
        for leak in leaks:
            print(f"    [{leak.pattern}] {leak.evidence}")

    print()
    return 0


def _cmd_diagnose(args) -> int:
    print("M-O Diagnosis (LLM-powered)")
    print("=" * 50)

    try:
        from neutron_os.infra.gateway import Gateway
        gateway = Gateway()
        if not gateway.available:
            print("No LLM gateway available. Configure ANTHROPIC_API_KEY or OPENAI_API_KEY.")
            return 1
    except ImportError:
        print("Gateway module not found.")
        return 1

    mgr = _get_manager()

    try:
        from .vitals import VitalsMonitor
        from .network import NetworkLedger
        from .agent import MoAgent

        monitor = VitalsMonitor(mgr, NetworkLedger.shared())
        snap = monitor.sample()
        pressure = monitor.check_pressure()
        leaks = monitor.detect_leaks()

        agent = MoAgent(gateway=gateway)
        agent.set_manager(mgr, monitor)

        signal = {
            "type": "manual_diagnosis",
            "level": pressure,
            "vitals": snap.to_dict(),
            "leaks": [
                {"owner": leak.owner, "pattern": leak.pattern, "evidence": leak.evidence}
                for leak in leaks
            ],
        }

        print("Analyzing...")
        verdict = agent.diagnose(signal)

        print(f"\nLevel: {verdict.level}")
        print(f"\nDiagnosis:\n{verdict.diagnosis}")

        if verdict.actions_taken:
            print("\nActions taken:")
            for action in verdict.actions_taken:
                print(f"  - {action}")

        if verdict.recommendations:
            print("\nRecommendations:")
            for rec in verdict.recommendations:
                print(f"  - {rec}")

    except Exception as e:
        print(f"Diagnosis failed: {e}")
        return 1

    print()
    return 0


# --- Helpers ---

def _fmt_bytes(n: int) -> str:
    if n < 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n = n / 1024
    return f"{n:.1f} TB"


def _fmt_age(iso_str: str, now: datetime) -> str:
    try:
        created = datetime.fromisoformat(iso_str)
        delta = (now - created).total_seconds()
        if delta < 60:
            return "<1m"
        if delta < 3600:
            return f"{int(delta / 60)}m"
        if delta < 86400:
            return f"{int(delta / 3600)}h"
        return f"{int(delta / 86400)}d"
    except (ValueError, TypeError):
        return "?"


if __name__ == "__main__":
    sys.exit(main())

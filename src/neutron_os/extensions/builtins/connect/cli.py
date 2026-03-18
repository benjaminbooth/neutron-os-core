"""CLI handler for `neut connect` — manage external connections.

Usage:
    neut connect                    List all connections and status
    neut connect <name>             Set up a specific connection
    neut connect <name> --clear     Remove saved credentials
    neut connect --check            Health check all connections
    neut connect --json             Machine-readable output
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from neutron_os.infra.connections import (
    Connection,
    ConnectionHealth,
    ConnectionRegistry,
    HealthStatus,
    check_health,
    clear_credential,
    get_credential,
    get_registry,
    has_credential,
    store_credential,
)


# ---------------------------------------------------------------------------
# Status formatting (for neut status integration)
# ---------------------------------------------------------------------------

_STATUS_SYMBOLS = {
    "configured": "\u2713",    # ✓
    "expired": "\u26a0",       # ⚠
    "missing": "\u25cb",       # ○
    "unhealthy": "\u2717",     # ✗
    "healthy": "\u2713",       # ✓
}


def _connection_status_line(conn: Connection, registry: ConnectionRegistry) -> dict:
    """Get status info for a single connection."""
    has_cred = has_credential(conn.name, registry=registry)

    if conn.kind == "cli":
        from neutron_os.infra.connections import get_cli_tool
        tool = get_cli_tool(conn.name, registry=registry)
        if tool:
            return {
                "name": conn.name,
                "display_name": conn.display_name,
                "status": "healthy",
                "message": f"v{tool.version}" if tool.version else "installed",
                "kind": conn.kind,
                "category": conn.category,
            }
        return {
            "name": conn.name,
            "display_name": conn.display_name,
            "status": "missing",
            "message": f"Not found — {conn.docs_url}" if conn.docs_url else "Not found",
            "kind": conn.kind,
            "category": conn.category,
        }

    if conn.credential_type == "none":
        status = "healthy"
        message = "No credentials needed"
    elif has_cred:
        status = "configured"
        message = "Credential set"
    else:
        tag = "required" if conn.required else "optional"
        status = "missing"
        message = f"Not configured ({tag})"

    return {
        "name": conn.name,
        "display_name": conn.display_name,
        "status": status,
        "message": message,
        "kind": conn.kind,
        "category": conn.category,
    }


def format_status_section(*, registry: Optional[ConnectionRegistry] = None) -> str:
    """Format connections for neut status display."""
    if registry is None:
        registry = get_registry()

    connections = registry.all()
    if not connections:
        return "  No connections registered"

    lines = []
    for conn in sorted(connections, key=lambda c: (c.category, c.name)):
        info = _connection_status_line(conn, registry)
        symbol = _STATUS_SYMBOLS.get(info["status"], "?")
        lines.append(f"  {symbol} {info['display_name']:25s} {info['message']}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Health check all
# ---------------------------------------------------------------------------

def _check_all(registry: ConnectionRegistry, as_json: bool = False) -> int:
    """Run health checks on all connections. Returns 0 if all healthy."""
    connections = registry.all()
    results = []
    any_unhealthy = False

    for conn in sorted(connections, key=lambda c: c.name):
        if conn.health_check:
            health = check_health(conn.name, registry=registry)
        else:
            # No health check — just check credential
            has_cred = has_credential(conn.name, registry=registry)
            if conn.credential_type == "none" or conn.kind == "cli":
                from neutron_os.infra.connections import get_cli_tool
                tool = get_cli_tool(conn.name, registry=registry) if conn.kind == "cli" else True
                health = ConnectionHealth(
                    status=HealthStatus.HEALTHY if tool else HealthStatus.UNHEALTHY,
                    message="OK" if tool else "Not found",
                )
            elif has_cred:
                health = ConnectionHealth(status=HealthStatus.HEALTHY, message="Credential set")
            else:
                health = ConnectionHealth(
                    status=HealthStatus.UNHEALTHY if conn.required else HealthStatus.UNKNOWN,
                    message="No credential",
                )

        if health.status == HealthStatus.UNHEALTHY:
            any_unhealthy = True

        results.append({
            "name": conn.name,
            "display_name": conn.display_name,
            "status": health.status,
            "message": health.message,
            "latency_ms": health.latency_ms,
        })

    if as_json:
        print(json.dumps(results, indent=2))
    else:
        print("\n  Connection Health Check")
        print("  " + "\u2500" * 40)
        for r in results:
            symbol = "\u2713" if r["status"] == "healthy" else (
                "\u26a0" if r["status"] in ("degraded", "unknown") else "\u2717"
            )
            latency = f" ({r['latency_ms']:.0f}ms)" if r["latency_ms"] > 0 else ""
            print(f"  {symbol} {r['display_name']:25s} {r['message']}{latency}")
        print()

    return 1 if any_unhealthy else 0


# ---------------------------------------------------------------------------
# Setup flow
# ---------------------------------------------------------------------------

def _setup_connection(name: str, registry: ConnectionRegistry) -> int:
    """Interactive setup for a single connection."""
    conn = registry.get(name)
    if conn is None:
        print(f"\n  Connection not found: {name}")
        print("  Available connections:")
        for c in sorted(registry.all(), key=lambda c: c.name):
            print(f"    {c.name:20s} {c.display_name}")
        print()
        return 1

    print(f"\n  {conn.display_name}")
    print("  " + "\u2500" * len(conn.display_name))

    if conn.kind == "cli":
        return _setup_cli_tool(conn, registry)

    if conn.credential_type == "none":
        print("  No credentials needed for this connection.")
        print()
        return 0

    return _setup_api_credential(conn, registry)


def _setup_cli_tool(conn: Connection, registry: ConnectionRegistry) -> int:
    """Set up a CLI tool connection — install, configure, verify."""
    import platform
    import shutil
    import subprocess

    from neutron_os.infra.connections import get_cli_tool

    binary = conn.endpoint or conn.name
    tool = get_cli_tool(conn.name, registry=registry)

    if tool:
        print(f"  \u2713 Installed at {tool.path}")
        if tool.version:
            print(f"    Version: {tool.version}")
    else:
        print(f"  \u2717 {binary} not found on PATH\n")

        # Try to install automatically on macOS
        if platform.system() == "Darwin" and shutil.which("brew"):
            try:
                answer = input("  Install via Homebrew? [Y/n] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n  Skipped")
                return 0

            if answer in ("", "y", "yes"):
                print(f"  Installing {binary}...")
                try:
                    subprocess.run(
                        ["brew", "install", binary],
                        check=True, timeout=120,
                    )
                    print("  \u2713 Installed")
                    tool = get_cli_tool(conn.name, registry=registry)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    print(f"  \u2717 Install failed: {e}")
                    if conn.docs_url:
                        print(f"  Manual install: {conn.docs_url}")
                    print()
                    return 1
            else:
                if conn.docs_url:
                    print(f"  Install manually: {conn.docs_url}")
                print()
                return 0
        else:
            if conn.docs_url:
                print(f"  Install: {conn.docs_url}")
            print()
            return 0

    # Post-install hooks for specific tools
    if binary == "ollama" and tool:
        return _setup_ollama_post_install()

    print()
    return 0


def _setup_ollama_post_install() -> int:
    """Ollama-specific post-install: ensure serving + model pulled."""
    import subprocess
    import urllib.request

    from neutron_os.extensions.builtins.settings.store import SettingsStore
    settings = SettingsStore()
    model = settings.get("routing.ollama_model", "llama3.2:1b")

    # Check if serving
    serving = False
    try:
        urllib.request.urlopen("http://localhost:11434", timeout=2)
        serving = True
    except Exception:
        pass

    if not serving:
        print("\n  Ollama is installed but not running.")
        try:
            answer = input("  Start Ollama now? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n  Skipped")
            return 0

        if answer in ("", "y", "yes"):
            print("  Starting ollama serve...")
            # Start in background
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Wait briefly for it to come up
            import time
            for _ in range(5):
                time.sleep(1)
                try:
                    urllib.request.urlopen("http://localhost:11434", timeout=1)
                    serving = True
                    print("  \u2713 Ollama serving")
                    break
                except Exception:
                    pass
            if not serving:
                print("  \u26a0 Ollama didn't start — try `ollama serve` manually")
                return 1
        else:
            print("  Start later with: ollama serve")
            print()
            return 0

    # Check if model is pulled
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10,
        )
        if model in result.stdout:
            print(f"  \u2713 Model {model} ready")
            print()
            return 0
    except Exception:
        pass

    print(f"\n  Routing model ({model}) not yet pulled.")
    try:
        answer = input(f"  Pull {model} now? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n  Skipped")
        return 0

    if answer in ("", "y", "yes"):
        print(f"  Pulling {model} (this may take a minute)...")
        try:
            subprocess.run(
                ["ollama", "pull", model],
                check=True, timeout=300,
            )
            print(f"  \u2713 Model {model} ready")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            print(f"  \u2717 Pull failed — try manually: ollama pull {model}")
            return 1
    else:
        print(f"  Pull later with: ollama pull {model}")

    print()
    return 0


def _setup_api_credential(conn: Connection, registry: ConnectionRegistry) -> int:
    """Set up an API credential — check, prompt, save, verify."""
    current = get_credential(conn.name, registry=registry)
    if current:
        masked = current[:4] + "..." + current[-4:] if len(current) > 10 else "****"
        print(f"  \u2713 Credential: {masked}")

        # Offer to health-check
        if conn.health_check:
            health = check_health(conn.name, registry=registry)
            latency = f" ({health.latency_ms:.0f}ms)" if health.latency_ms else ""
            if health.status == HealthStatus.HEALTHY:
                print(f"  \u2713 Verified{latency}")
            else:
                print(f"  \u26a0 Health check: {health.message}")
        print()
        return 0

    # No credential — prompt for one
    if conn.docs_url:
        print(f"  Get your key: {conn.docs_url}\n")

    try:
        value = input(f"  Paste {conn.display_name} key (Enter to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  Skipped")
        return 0

    if not value:
        if conn.credential_env_var:
            print(f"  Or set: export {conn.credential_env_var}=<key>")
        print()
        return 0

    # Save it
    store_credential(conn.name, value)
    print("  \u2713 Saved")

    # Also set in current process for immediate use
    if conn.credential_env_var:
        import os
        os.environ[conn.credential_env_var] = value

    # Verify if possible
    if conn.health_check:
        from neutron_os.infra.connections import reset_registry
        reset_registry()  # re-discover so new cred is picked up
        health = check_health(conn.name, registry=get_registry())
        if health.status == HealthStatus.HEALTHY:
            print("  \u2713 Verified")
        else:
            print(f"  \u26a0 Could not verify: {health.message}")
            print("    (credential saved — it may still work)")
    print()
    return 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neut connect",
        description="Manage external connections and credentials.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  neut connect                    List all connections
  neut connect github             Set up GitHub connection
  neut connect --check            Health check all connections
  neut connect teams --clear      Remove Teams credentials
  neut connect --json             Machine-readable output
""",
    )

    parser.add_argument(
        "name",
        nargs="?",
        help="Connection to set up or manage",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Health check all connections",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Remove saved credentials for a connection",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    registry = get_registry()

    # neut connect --check
    if args.check:
        return _check_all(registry, as_json=args.json)

    # neut connect <name> --clear
    if args.name and args.clear:
        clear_credential(args.name)
        print(f"\n  Cleared credentials for {args.name}\n")
        return 0

    # neut connect <name> (setup)
    if args.name:
        return _setup_connection(args.name, registry)

    # neut connect (list all)
    connections = registry.all()

    if args.json:
        data = [_connection_status_line(c, registry) for c in connections]
        print(json.dumps(data, indent=2))
        return 0

    if not connections:
        print("\n  No connections registered.")
        print("  Extensions declare connections in neut-extension.toml\n")
        return 0

    print("\n  Connections")
    print("  " + "\u2550" * 40)
    print(format_status_section(registry=registry))
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())

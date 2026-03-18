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

from neutron_os.infra.connections import (
    Connection,
    ConnectionHealth,
    ConnectionRegistry,
    HealthStatus,
    check_health,
    clear_credential,
    format_status_section,
    get_credential,
    get_install_command,
    get_registry,
    has_credential,
    run_post_setup_hook,
    store_credential,
)


# format_status_section and _connection_status_info are in infra/connections.py
# (shared platform layer, not extension-specific)

from neutron_os.infra.connections import _connection_status_info


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

def setup_connection(name: str, registry: ConnectionRegistry) -> int:
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
    """Set up a CLI tool connection — install, configure, verify.

    Uses declarative install_commands from TOML and extensible
    post_setup hooks from the owning extension.
    """
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

        # Use declarative install_commands from TOML
        install_cmd = get_install_command(conn)
        if install_cmd:
            try:
                answer = input(f"  Install with `{install_cmd}`? [Y/n] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n  Skipped")
                return 0

            if answer in ("", "y", "yes"):
                print("  Installing...")
                try:
                    subprocess.run(
                        install_cmd, shell=True,
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

    # Run extension-provided post-setup hook if declared
    hook_result = run_post_setup_hook(conn)
    if hook_result >= 0:
        return hook_result

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

    name_arg = parser.add_argument(
        "name",
        nargs="?",
        help="Connection to set up or manage",
    )

    # argcomplete: offer registered connection names as completions
    try:
        def _complete_connection_names(prefix, parsed_args, **kwargs):
            try:
                return [c.name for c in get_registry().all()
                        if c.name.startswith(prefix)]
            except Exception:
                return []

        name_arg.completer = _complete_connection_names  # type: ignore[attr-defined]
    except Exception:
        pass
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
        return setup_connection(args.name, registry)

    # neut connect (list all)
    connections = registry.all()

    if args.json:
        data = [_connection_status_info(c, registry) for c in connections]
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

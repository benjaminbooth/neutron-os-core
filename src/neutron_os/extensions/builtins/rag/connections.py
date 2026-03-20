"""Lifecycle management for RAG connections.

Ensures PostgreSQL (pgvector) is running before RAG operations.
Provides post-setup hook that saves rag.database_url to settings.
"""

from __future__ import annotations

import logging
import os
import socket

log = logging.getLogger(__name__)


def setup_postgresql() -> int:
    """Post-setup hook for PostgreSQL: prompt for connection URL and save to settings.

    Called by `neut connect postgresql`. Prompts for the PostgreSQL connection
    string, validates TCP reachability, and writes rag.database_url to project
    settings so the chat agent and RAG commands can find the database.
    """
    from neutron_os.extensions.builtins.settings.store import SettingsStore

    settings = SettingsStore()
    current_url = settings.get("rag.database_url", "") or os.environ.get("NEUT_DB_URL", "")

    if current_url:
        masked = current_url[:30] + "..." if len(current_url) > 30 else current_url
        print(f"  Current: {masked}")

    print()
    print("  PostgreSQL connection string format:")
    print("    postgresql://<user>:<password>@<host>:<port>/<database>")
    print()
    print("  Local k3d (port-forwarded):   postgresql://neut:<pw>@localhost:5432/neut_db")
    print("  Rascal (port-forwarded):      postgresql://neut:<pw>@localhost:5432/neut_db")
    print()

    try:
        value = input(
            "  Paste connection URL (Enter to keep current, 'skip' to skip): "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  Skipped")
        return 0

    if value.lower() == "skip":
        print("  Skipped — RAG disabled until rag.database_url is set")
        print()
        return 0

    if not value and current_url:
        value = current_url
        print(f"  Keeping current URL")

    if not value:
        print("  No URL provided — RAG remains disabled")
        print("  Set later: neut settings set rag.database_url postgresql://...")
        print()
        return 0

    # Basic validation
    if not value.startswith("postgresql://"):
        print("  ✗ URL must start with postgresql://")
        return 1

    # TCP reachability check
    try:
        from urllib.parse import urlparse
        parsed = urlparse(value)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        sock = socket.create_connection((host, port), timeout=2)
        sock.close()
        print(f"  ✓ PostgreSQL reachable at {host}:{port}")
    except Exception as e:
        print(f"  ⚠ Could not reach {host}:{port} — {e}")
        print("    (URL saved — run `kubectl port-forward -n neut svc/neut-postgresql 5432:5432`)")

    # Save to project settings
    settings.set("rag.database_url", value)
    print("  ✓ Saved rag.database_url to .neut/settings.toml")
    print()
    print("  Next steps:")
    print("    neut rag index docs/          — index your documents")
    print("    neut rag index runtime/       — index sessions + notes")
    print("    neut chat                     — RAG context now active")
    print()
    return 0


def setup_pack_server() -> int:
    """Post-setup hook for pack-server: prompt for endpoint + API key, health-check, list packs.

    Called by `neut connect pack-server`. Supports named servers (e.g. rascal, tacc)
    so a user can register multiple pack servers. The server name is stored as
    rag.pack_server_url.<name> / rag.pack_server_key.<name>.
    """
    import urllib.request
    import json
    from neutron_os.extensions.builtins.settings.store import SettingsStore

    settings = SettingsStore()

    print()
    print("  Pack server examples:")
    print("    Rascal (UT VPN):   https://rascal.austin.utexas.edu:9000")
    print("    TACC (TACC net):   https://tacc-neut.tacc.utexas.edu:9000")
    print()

    try:
        name = input("  Server name (e.g. 'rascal', 'tacc') [rascal]: ").strip() or "rascal"
        url = input(f"  Pack server URL: ").strip().rstrip("/")
        key = input(f"  API key (Enter to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  Skipped")
        return 0

    if not url:
        print("  No URL provided — skipped")
        return 0

    # Health check — fetch registry
    registry_url = f"{url}/packs/registry.json"
    try:
        req = urllib.request.Request(registry_url)
        if key:
            req.add_header("Authorization", f"Bearer {key}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            registry = json.load(resp)
        packs = registry.get("packs", [])
        print(f"  ✓ Pack server reachable — {len(packs)} pack(s) available:")
        for p in packs[:10]:
            print(f"      {p['pack_id']} v{p['latest_version']}  ({p.get('access_tier', '?')})"
                  f"  — {p.get('description', '')[:60]}")
        if len(packs) > 10:
            print(f"      ... and {len(packs) - 10} more (neut rag pack list --remote --server {name})")
    except Exception as e:
        print(f"  ⚠ Could not reach {registry_url} — {e}")
        print("    (Settings saved — connect to VPN/network and retry)")

    settings.set(f"rag.pack_server_url.{name}", url)
    if key:
        settings.set(f"rag.pack_server_key.{name}", key)
    print(f"  ✓ Saved pack server '{name}' to settings")
    print()
    print(f"  Install a pack:   neut rag pack install <pack-id> --server {name}")
    print(f"  List packs:       neut rag pack list --remote --server {name}")
    print()
    return 0


def ensure_postgresql_running() -> bool:
    """Silently ensure PostgreSQL is available via K3D cluster.

    Returns True if PostgreSQL is responding on localhost:5432.
    Attempts to start the K3D cluster if Docker is running but
    the cluster is stopped. Never prompts.
    """
    if _is_pg_serving():
        return True

    # Try to start the K3D cluster
    try:
        from neutron_os.setup.infra import check_docker, check_k3d, start_cluster, InfraStatus

        docker = check_docker()
        if docker.status != InfraStatus.READY:
            log.debug("Docker not running — cannot auto-start PostgreSQL")
            return False

        k3d = check_k3d()
        if k3d.status != InfraStatus.READY:
            log.debug("K3D not installed — cannot auto-start PostgreSQL")
            return False

        log.info("Auto-starting neut-local K3D cluster for PostgreSQL...")
        if start_cluster():
            # Wait for PostgreSQL to come up
            import time
            for _ in range(10):
                time.sleep(1)
                if _is_pg_serving():
                    log.info("PostgreSQL auto-started")
                    return True

        log.debug("K3D cluster started but PostgreSQL not responding")
        return False

    except ImportError:
        log.debug("infra module not available for auto-start")
        return False
    except Exception as e:
        log.debug("PostgreSQL auto-start failed: %s", e)
        return False


def _is_pg_serving(host: str = "localhost", port: int = 5432) -> bool:
    """Check if PostgreSQL is accepting connections."""
    try:
        sock = socket.create_connection((host, port), timeout=1)
        sock.close()
        return True
    except Exception:
        return False

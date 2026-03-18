"""Connections — unified abstraction for all external integrations.

Provides:
- Connection dataclass: declares an external system
- ConnectionRegistry: discovers and stores connections
- get_credential() / has_credential(): credential resolution chain
- get_cli_tool(): PATH resolution + version detection
- check_health(): health check dispatch
- store_credential() / clear_credential(): secure file storage (0600)

Resolution chain: env var → settings → credential file (0600)

See: docs/requirements/prd-connections.md
     docs/tech-specs/spec-connections.md
"""

from __future__ import annotations

import logging
import os
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

_CREDENTIALS_DIR = Path.home() / ".neut" / "credentials"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class HealthStatus:
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ConnectionHealth:
    """Result of a health check."""
    status: str  # HealthStatus value
    latency_ms: float = 0.0
    message: str = ""


@dataclass
class CLIToolInfo:
    """Resolved CLI tool on PATH."""
    path: Path
    version: str = ""


@dataclass
class Connection:
    """An external system that NeutronOS integrates with."""

    name: str
    display_name: str
    kind: str  # "api" | "browser" | "mcp" | "a2a" | "cli"
    category: str = ""

    # Transport
    endpoint: str = ""
    transport: str = ""

    # Credential
    credential_type: str = "api_key"
    credential_env_var: str = ""
    credential_file: str = ""  # relative to credentials dir

    # Behavior
    required: bool = False
    health_check: str = ""  # "http_get" | "tcp_connect" | "cli_version" | "custom"
    health_endpoint: str = ""
    auto_refresh: bool = False

    # Metadata
    extension: str = ""
    docs_url: str = ""

    # Extensible setup hooks
    post_setup_module: str = ""
    post_setup_function: str = ""
    install_commands: dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.install_commands is None:
            self.install_commands = {}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Connection:
        """Create a Connection from a dict (e.g., parsed TOML)."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    @classmethod
    def from_connection_def(cls, cdef) -> Connection:
        """Create from a contracts.ConnectionDef."""
        return cls(
            name=cdef.name,
            display_name=cdef.display_name,
            kind=cdef.kind,
            category=cdef.category,
            endpoint=cdef.endpoint,
            transport=cdef.transport,
            credential_type=cdef.credential_type,
            credential_env_var=cdef.credential_env_var,
            credential_file=cdef.credential_file,
            required=cdef.required,
            health_check=cdef.health_check,
            health_endpoint=cdef.health_endpoint,
            auto_refresh=cdef.auto_refresh,
            docs_url=cdef.docs_url,
            post_setup_module=cdef.post_setup_module,
            post_setup_function=cdef.post_setup_function,
            install_commands=dict(cdef.install_commands) if cdef.install_commands else {},
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ConnectionRegistry:
    """Discovers and stores Connection declarations."""

    def __init__(self) -> None:
        self._connections: dict[str, Connection] = {}

    def register(self, conn: Connection) -> None:
        self._connections[conn.name] = conn

    def get(self, name: str) -> Optional[Connection]:
        return self._connections.get(name)

    def all(self) -> list[Connection]:
        return list(self._connections.values())

    def by_category(self, category: str) -> list[Connection]:
        return [c for c in self._connections.values() if c.category == category]

    def by_kind(self, kind: str) -> list[Connection]:
        return [c for c in self._connections.values() if c.kind == kind]

    def discover_from_directory(self, search_dir: Path) -> None:
        """Parse [[connections]] from neut-extension.toml files under search_dir.

        Legacy method — prefer discover_from_extensions() which uses
        the proper 3-tier extension discovery system.
        """
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]  # noqa: F401

        for manifest_path in search_dir.rglob("neut-extension.toml"):
            try:
                with open(manifest_path, "rb") as f:
                    data = tomllib.load(f)
            except Exception as e:
                log.debug("Failed to parse %s: %s", manifest_path, e)
                continue

            ext_name = data.get("extension", {}).get("name", "")
            for conn_data in data.get("connections", []):
                conn_data.setdefault("extension", ext_name)
                try:
                    conn = Connection.from_dict(conn_data)
                    self.register(conn)
                except Exception as e:
                    log.warning("Invalid connection in %s: %s", manifest_path, e)

    def discover_from_extensions(self) -> None:
        """Discover connections via the 3-tier extension system.

        Uses extensions.discovery.discover_connections() which scans:
        1. .neut/extensions/ (project-local, highest priority)
        2. ~/.neut/extensions/ (user-global)
        3. builtins/ (shipped with neut)
        """
        try:
            from neutron_os.extensions.discovery import discover_connections
            for cdef in discover_connections():
                conn = Connection.from_connection_def(cdef)
                self.register(conn)
        except Exception as e:
            log.debug("3-tier discovery failed, falling back: %s", e)


# ---------------------------------------------------------------------------
# Credential resolution
# ---------------------------------------------------------------------------

def get_credential(
    name: str,
    *,
    registry: Optional[ConnectionRegistry] = None,
    credentials_dir: Optional[Path] = None,
) -> Optional[str]:
    """Resolve a credential for the named connection.

    Resolution order: env var → settings → credential file (0600).
    Returns None if no credential found (never throws).
    """
    if registry is None:
        registry = _get_global_registry()

    conn = registry.get(name)
    if conn is None:
        return None

    cred_dir = credentials_dir or _CREDENTIALS_DIR

    # 1. Environment variable
    if conn.credential_env_var:
        value = os.environ.get(conn.credential_env_var)
        if value:
            return value

    # 2. Settings (neut settings)
    try:
        from neutron_os.extensions.builtins.settings.store import SettingsStore
        store = SettingsStore()
        settings_key = f"connections.{name}.token"
        value = store.get(settings_key)
        if value:
            return value
    except Exception:
        pass

    # 3. Credential file (must be 0600)
    if conn.credential_file:
        file_path = cred_dir / conn.credential_file
        if file_path.exists():
            mode = file_path.stat().st_mode & 0o777
            if mode != 0o600:
                log.warning(
                    "Credential file %s has permissions %s (expected 0600) — skipping",
                    file_path, oct(mode),
                )
                return None
            return file_path.read_text(encoding="utf-8").strip()

    return None


def has_credential(
    name: str,
    *,
    registry: Optional[ConnectionRegistry] = None,
    credentials_dir: Optional[Path] = None,
) -> bool:
    """Check if a credential is available without retrieving it."""
    return get_credential(name, registry=registry, credentials_dir=credentials_dir) is not None


# ---------------------------------------------------------------------------
# Credential storage
# ---------------------------------------------------------------------------

def store_credential(
    name: str,
    value: str,
    *,
    credentials_dir: Optional[Path] = None,
) -> Path:
    """Store a credential securely. Returns path to the file."""
    cred_dir = credentials_dir or _CREDENTIALS_DIR
    svc_dir = cred_dir / name
    svc_dir.mkdir(parents=True, exist_ok=True)

    token_file = svc_dir / "token"
    token_file.write_text(value, encoding="utf-8")
    token_file.chmod(0o600)
    return token_file


def clear_credential(
    name: str,
    *,
    credentials_dir: Optional[Path] = None,
) -> None:
    """Remove stored credential for a connection."""
    cred_dir = credentials_dir or _CREDENTIALS_DIR
    svc_dir = cred_dir / name
    if svc_dir.exists():
        shutil.rmtree(svc_dir)


# ---------------------------------------------------------------------------
# CLI tool resolution
# ---------------------------------------------------------------------------

def get_cli_tool(
    name: str,
    *,
    registry: Optional[ConnectionRegistry] = None,
) -> Optional[CLIToolInfo]:
    """Find a CLI tool on PATH. Returns None if not installed or not a CLI connection."""
    if registry is None:
        registry = _get_global_registry()

    conn = registry.get(name)
    if conn is None or conn.kind != "cli":
        return None

    binary = conn.endpoint or conn.name
    path = shutil.which(binary)
    if path is None:
        return None

    # Try to get version
    version = ""
    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True, text=True, timeout=5,
        )
        output = result.stdout.strip() or result.stderr.strip()
        # Extract version number
        import re
        match = re.search(r"(\d+\.\d+[\.\d]*)", output)
        if match:
            version = match.group(1)
    except Exception:
        pass

    return CLIToolInfo(path=Path(path), version=version)


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------

_custom_health_checks: dict[str, Callable[[Connection], ConnectionHealth]] = {}


def register_custom_health_check(
    name: str,
    checker: Callable[[Connection], ConnectionHealth],
) -> None:
    """Register a custom health check function for a connection."""
    _custom_health_checks[name] = checker


def check_health(
    name: str,
    *,
    registry: Optional[ConnectionRegistry] = None,
) -> ConnectionHealth:
    """Run a health check for the named connection."""
    if registry is None:
        registry = _get_global_registry()

    conn = registry.get(name)
    if conn is None:
        return ConnectionHealth(status=HealthStatus.UNKNOWN, message=f"Unknown connection: {name}")

    check_type = conn.health_check

    if check_type == "cli_version":
        return _check_cli_version(conn)
    elif check_type == "tcp_connect":
        return _check_tcp_connect(conn)
    elif check_type == "http_get":
        return _check_http_get(conn)
    elif check_type == "custom":
        checker = _custom_health_checks.get(name)
        if checker:
            return checker(conn)
        return ConnectionHealth(
            status=HealthStatus.UNKNOWN,
            message="No custom health check registered",
        )
    elif not check_type:
        # No health check configured — report unknown
        return ConnectionHealth(status=HealthStatus.UNKNOWN, message="No health check configured")

    return ConnectionHealth(status=HealthStatus.UNKNOWN, message=f"Unknown check type: {check_type}")


def _check_cli_version(conn: Connection) -> ConnectionHealth:
    """Check if a CLI binary is available and get its version."""
    binary = conn.endpoint or conn.name
    path = shutil.which(binary)
    if path is None:
        return ConnectionHealth(
            status=HealthStatus.UNHEALTHY,
            message=f"{binary} not found on PATH",
        )

    start = time.monotonic()
    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True, text=True, timeout=5,
        )
        elapsed = (time.monotonic() - start) * 1000
        output = result.stdout.strip() or result.stderr.strip()
        return ConnectionHealth(
            status=HealthStatus.HEALTHY,
            latency_ms=round(elapsed, 1),
            message=output.split("\n")[0][:80] if output else "OK",
        )
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return ConnectionHealth(
            status=HealthStatus.UNHEALTHY,
            latency_ms=round(elapsed, 1),
            message=str(e),
        )


def _check_tcp_connect(conn: Connection) -> ConnectionHealth:
    """TCP connect to host:port with 1s timeout."""
    endpoint = conn.health_endpoint or conn.endpoint
    if ":" not in endpoint:
        return ConnectionHealth(
            status=HealthStatus.UNHEALTHY,
            message=f"Invalid endpoint for TCP check: {endpoint}",
        )

    host, port_str = endpoint.rsplit(":", 1)
    try:
        port = int(port_str)
    except ValueError:
        return ConnectionHealth(
            status=HealthStatus.UNHEALTHY,
            message=f"Invalid port: {port_str}",
        )

    start = time.monotonic()
    try:
        sock = socket.create_connection((host, port), timeout=1)
        sock.close()
        elapsed = (time.monotonic() - start) * 1000
        return ConnectionHealth(
            status=HealthStatus.HEALTHY,
            latency_ms=round(elapsed, 1),
            message=f"Connected to {host}:{port}",
        )
    except Exception:
        elapsed = (time.monotonic() - start) * 1000
        return ConnectionHealth(
            status=HealthStatus.UNHEALTHY,
            latency_ms=round(elapsed, 1),
            message=f"Cannot reach {host}:{port}",
        )


def _check_http_get(conn: Connection) -> ConnectionHealth:
    """GET the health endpoint, check for 200."""
    url = conn.health_endpoint or conn.endpoint
    if not url:
        return ConnectionHealth(
            status=HealthStatus.UNHEALTHY,
            message="No health endpoint configured",
        )

    start = time.monotonic()
    try:
        import requests
        response = requests.get(url, timeout=5)
        elapsed = (time.monotonic() - start) * 1000
        if response.status_code < 400:
            return ConnectionHealth(
                status=HealthStatus.HEALTHY,
                latency_ms=round(elapsed, 1),
                message=f"HTTP {response.status_code}",
            )
        return ConnectionHealth(
            status=HealthStatus.UNHEALTHY,
            latency_ms=round(elapsed, 1),
            message=f"HTTP {response.status_code}",
        )
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return ConnectionHealth(
            status=HealthStatus.UNHEALTHY,
            latency_ms=round(elapsed, 1),
            message=str(e)[:100],
        )


# ---------------------------------------------------------------------------
# Global registry singleton
# ---------------------------------------------------------------------------

_global_registry: Optional[ConnectionRegistry] = None


def _get_global_registry() -> ConnectionRegistry:
    """Lazy-init global registry via 3-tier extension discovery."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ConnectionRegistry()
        _global_registry.discover_from_extensions()
    return _global_registry


def get_registry() -> ConnectionRegistry:
    """Get the global connection registry."""
    return _get_global_registry()


def reset_registry() -> None:
    """Reset the global registry (for testing)."""
    global _global_registry
    _global_registry = None


# ---------------------------------------------------------------------------
# Extensible setup hooks
# ---------------------------------------------------------------------------

def run_post_setup_hook(conn: Connection) -> int:
    """Run an extension-provided post-setup hook if declared.

    Returns 0 on success, 1 on failure, -1 if no hook declared.
    """
    if not conn.post_setup_module or not conn.post_setup_function:
        return -1

    try:
        import importlib
        mod = importlib.import_module(conn.post_setup_module)
        func = getattr(mod, conn.post_setup_function)
        return func()
    except Exception as e:
        log.warning("Post-setup hook %s.%s failed: %s",
                    conn.post_setup_module, conn.post_setup_function, e)
        return 1


def get_install_command(conn: Connection) -> Optional[str]:
    """Get the platform-appropriate install command from TOML declaration."""
    import platform as _platform
    system = _platform.system().lower()

    platform_map = {
        "darwin": "macos",
        "linux": "linux",
        "windows": "windows",
    }
    key = platform_map.get(system, system)
    return conn.install_commands.get(key) or conn.install_commands.get("default")


# ---------------------------------------------------------------------------
# Status formatting (shared by neut status + neut connect)
# ---------------------------------------------------------------------------

_STATUS_SYMBOLS = {
    "configured": "\u2713",
    "healthy": "\u2713",
    "expired": "\u26a0",
    "missing": "\u25cb",
    "unhealthy": "\u2717",
}


def format_status_section(*, registry: Optional[ConnectionRegistry] = None) -> str:
    """Format connections for display in neut status."""
    if registry is None:
        registry = _get_global_registry()

    connections = registry.all()
    if not connections:
        return "  No connections registered"

    lines = []
    for conn in sorted(connections, key=lambda c: (c.category, c.name)):
        info = _connection_status_info(conn, registry)
        symbol = _STATUS_SYMBOLS.get(info["status"], "?")
        lines.append(f"  {symbol} {info['display_name']:25s} {info['message']}")

    return "\n".join(lines)


def _connection_status_info(conn: Connection, registry: ConnectionRegistry) -> dict:
    """Get status info for a single connection."""
    if conn.kind == "cli":
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

    has_cred = has_credential(conn.name, registry=registry)
    if conn.credential_type == "none":
        status, message = "healthy", "No credentials needed"
    elif has_cred:
        status, message = "configured", "Credential set"
    else:
        tag = "required" if conn.required else "optional"
        status, message = "missing", f"Not configured ({tag})"

    return {
        "name": conn.name,
        "display_name": conn.display_name,
        "status": status,
        "message": message,
        "kind": conn.kind,
        "category": conn.category,
    }

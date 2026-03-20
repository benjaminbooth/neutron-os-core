"""Managed service lifecycle — provider pattern with platform backends.

Supports launchd (macOS), systemd (Linux), and Windows Task Scheduler.
Providers are tried in order with automatic fallback.

Service definitions live in ~/.neut/services/.

Usage:
    from neutron_os.infra.services import get_service_manager

    svc = get_service_manager("ollama", binary="ollama", args=["serve"])
    svc.install()   # Register with OS (persists across reboots)
    svc.start()     # Start the service
    svc.stop()      # Stop the service
    svc.status()    # Returns ServiceInfo
    svc.uninstall() # Remove registration
"""

from __future__ import annotations

import abc
import logging
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

_SERVICES_DIR = Path.home() / ".neut" / "services"


class ServiceStatus:
    RUNNING = "running"
    STOPPED = "stopped"
    NOT_INSTALLED = "not_installed"
    UNKNOWN = "unknown"


@dataclass
class ServiceInfo:
    """Status of a managed service."""
    name: str
    status: str  # ServiceStatus value
    pid: int = 0
    message: str = ""
    provider: str = ""  # Which backend is managing this


# ---------------------------------------------------------------------------
# Abstract provider
# ---------------------------------------------------------------------------

class ServiceProvider(abc.ABC):
    """Abstract base for platform-specific service management."""

    @abc.abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'launchd', 'systemd', 'subprocess')."""

    @abc.abstractmethod
    def available(self) -> bool:
        """Whether this provider works on the current platform."""

    @abc.abstractmethod
    def install(self, svc: ServiceDef) -> bool:
        """Register the service for persistent startup."""

    @abc.abstractmethod
    def start(self, svc: ServiceDef) -> bool:
        """Start the service."""

    @abc.abstractmethod
    def stop(self, svc: ServiceDef) -> bool:
        """Stop the service."""

    @abc.abstractmethod
    def status(self, svc: ServiceDef) -> ServiceInfo:
        """Check if the service is running."""

    @abc.abstractmethod
    def uninstall(self, svc: ServiceDef) -> bool:
        """Remove the service registration."""


@dataclass
class ServiceDef:
    """Definition of a managed service."""
    name: str
    binary: str
    args: list[str]
    env: dict[str, str]
    service_id: str = ""

    def __post_init__(self):
        if not self.service_id:
            self.service_id = f"com.neutron-os.{self.name}"


# ---------------------------------------------------------------------------
# macOS: launchd provider
# ---------------------------------------------------------------------------

class LaunchdProvider(ServiceProvider):
    """macOS launchd service management."""

    def name(self) -> str:
        return "launchd"

    def available(self) -> bool:
        return platform.system() == "Darwin"

    def _plist_path(self, svc: ServiceDef) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / f"{svc.service_id}.plist"

    def install(self, svc: ServiceDef) -> bool:
        binary_path = shutil.which(svc.binary) or svc.binary

        env_xml = ""
        if svc.env:
            entries = "\n".join(
                f"            <key>{k}</key>\n            <string>{v}</string>"
                for k, v in svc.env.items()
            )
            env_xml = f"""
        <key>EnvironmentVariables</key>
        <dict>
{entries}
        </dict>"""

        args_xml = "\n".join(f"        <string>{a}</string>" for a in [binary_path] + svc.args)
        log_dir = _SERVICES_DIR
        log_dir.mkdir(parents=True, exist_ok=True)

        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{svc.service_id}</string>
    <key>ProgramArguments</key>
    <array>
{args_xml}
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>{env_xml}
    <key>StandardOutPath</key>
    <string>{log_dir / f'{svc.name}.stdout.log'}</string>
    <key>StandardErrorPath</key>
    <string>{log_dir / f'{svc.name}.stderr.log'}</string>
</dict>
</plist>
"""
        plist_path = self._plist_path(svc)
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        plist_path.write_text(plist, encoding="utf-8")
        log.info("Wrote launchd plist: %s", plist_path)
        return True

    def start(self, svc: ServiceDef) -> bool:
        try:
            subprocess.run(
                ["launchctl", "load", "-w", str(self._plist_path(svc))],
                capture_output=True, timeout=10,
            )
            return True
        except Exception as e:
            log.warning("launchctl load failed: %s", e)
            return False

    def stop(self, svc: ServiceDef) -> bool:
        try:
            subprocess.run(
                ["launchctl", "unload", str(self._plist_path(svc))],
                capture_output=True, timeout=10,
            )
            return True
        except Exception:
            return False

    def status(self, svc: ServiceDef) -> ServiceInfo:
        if not self._plist_path(svc).exists():
            return ServiceInfo(name=svc.name, status=ServiceStatus.NOT_INSTALLED, provider="launchd")
        try:
            result = subprocess.run(
                ["launchctl", "list", svc.service_id],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return ServiceInfo(name=svc.name, status=ServiceStatus.RUNNING, provider="launchd")
            return ServiceInfo(name=svc.name, status=ServiceStatus.STOPPED, provider="launchd")
        except Exception:
            return ServiceInfo(name=svc.name, status=ServiceStatus.UNKNOWN, provider="launchd")

    def uninstall(self, svc: ServiceDef) -> bool:
        self.stop(svc)
        self._plist_path(svc).unlink(missing_ok=True)
        return True


# ---------------------------------------------------------------------------
# Linux: systemd provider
# ---------------------------------------------------------------------------

class SystemdProvider(ServiceProvider):
    """Linux systemd user service management."""

    def name(self) -> str:
        return "systemd"

    def available(self) -> bool:
        return platform.system() == "Linux" and shutil.which("systemctl") is not None

    def _unit_path(self, svc: ServiceDef) -> Path:
        return Path.home() / ".config" / "systemd" / "user" / f"neut-{svc.name}.service"

    def install(self, svc: ServiceDef) -> bool:
        binary_path = shutil.which(svc.binary) or svc.binary
        exec_start = f"{binary_path} {' '.join(svc.args)}".strip()

        env_lines = "\n".join(f"Environment={k}={v}" for k, v in svc.env.items())

        unit = f"""[Unit]
Description=NeutronOS managed: {svc.name}
After=network.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=on-failure
RestartSec=5
{env_lines}

[Install]
WantedBy=default.target
"""
        unit_path = self._unit_path(svc)
        unit_path.parent.mkdir(parents=True, exist_ok=True)
        unit_path.write_text(unit, encoding="utf-8")
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        subprocess.run(["systemctl", "--user", "enable", f"neut-{svc.name}"], capture_output=True)
        log.info("Wrote systemd unit: %s", unit_path)
        return True

    def start(self, svc: ServiceDef) -> bool:
        try:
            result = subprocess.run(
                ["systemctl", "--user", "start", f"neut-{svc.name}"],
                capture_output=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def stop(self, svc: ServiceDef) -> bool:
        try:
            result = subprocess.run(
                ["systemctl", "--user", "stop", f"neut-{svc.name}"],
                capture_output=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def status(self, svc: ServiceDef) -> ServiceInfo:
        if not self._unit_path(svc).exists():
            return ServiceInfo(name=svc.name, status=ServiceStatus.NOT_INSTALLED, provider="systemd")
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", f"neut-{svc.name}"],
                capture_output=True, text=True, timeout=5,
            )
            active = result.stdout.strip()
            if active == "active":
                return ServiceInfo(name=svc.name, status=ServiceStatus.RUNNING, provider="systemd")
            return ServiceInfo(name=svc.name, status=ServiceStatus.STOPPED, provider="systemd", message=active)
        except Exception:
            return ServiceInfo(name=svc.name, status=ServiceStatus.UNKNOWN, provider="systemd")

    def uninstall(self, svc: ServiceDef) -> bool:
        self.stop(svc)
        subprocess.run(["systemctl", "--user", "disable", f"neut-{svc.name}"], capture_output=True)
        self._unit_path(svc).unlink(missing_ok=True)
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        return True


# ---------------------------------------------------------------------------
# Windows: Task Scheduler provider
# ---------------------------------------------------------------------------

class WindowsTaskProvider(ServiceProvider):
    """Windows Task Scheduler service management."""

    def name(self) -> str:
        return "windows_task"

    def available(self) -> bool:
        return platform.system() == "Windows"

    def install(self, svc: ServiceDef) -> bool:
        binary_path = shutil.which(svc.binary) or svc.binary
        args_str = " ".join(svc.args)
        task_name = f"NeutronOS_{svc.name}"
        try:
            subprocess.run([
                "schtasks", "/Create",
                "/TN", task_name,
                "/TR", f'"{binary_path}" {args_str}',
                "/SC", "ONLOGON",
                "/RL", "LIMITED",
                "/F",
            ], capture_output=True, check=True, timeout=15)
            log.info("Created Windows task: %s", task_name)
            return True
        except Exception as e:
            log.warning("schtasks create failed: %s", e)
            return False

    def start(self, svc: ServiceDef) -> bool:
        try:
            result = subprocess.run(
                ["schtasks", "/Run", "/TN", f"NeutronOS_{svc.name}"],
                capture_output=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def stop(self, svc: ServiceDef) -> bool:
        try:
            result = subprocess.run(
                ["schtasks", "/End", "/TN", f"NeutronOS_{svc.name}"],
                capture_output=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def status(self, svc: ServiceDef) -> ServiceInfo:
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", f"NeutronOS_{svc.name}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return ServiceInfo(name=svc.name, status=ServiceStatus.NOT_INSTALLED, provider="windows_task")
            if "Running" in result.stdout:
                return ServiceInfo(name=svc.name, status=ServiceStatus.RUNNING, provider="windows_task")
            return ServiceInfo(name=svc.name, status=ServiceStatus.STOPPED, provider="windows_task")
        except Exception:
            return ServiceInfo(name=svc.name, status=ServiceStatus.UNKNOWN, provider="windows_task")

    def uninstall(self, svc: ServiceDef) -> bool:
        self.stop(svc)
        try:
            subprocess.run(
                ["schtasks", "/Delete", "/TN", f"NeutronOS_{svc.name}", "/F"],
                capture_output=True, timeout=10,
            )
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Fallback: subprocess provider (no persistence)
# ---------------------------------------------------------------------------

class SubprocessProvider(ServiceProvider):
    """Fallback: raw background process. Does not survive reboots."""

    def name(self) -> str:
        return "subprocess"

    def available(self) -> bool:
        return True  # Always available as last resort

    def install(self, svc: ServiceDef) -> bool:
        return True  # No-op — subprocess doesn't persist

    def start(self, svc: ServiceDef) -> bool:
        binary_path = shutil.which(svc.binary) or svc.binary
        try:
            env = {**os.environ, **svc.env}
            subprocess.Popen(
                [binary_path] + svc.args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
            return True
        except Exception as e:
            log.warning("subprocess start failed: %s", e)
            return False

    def stop(self, svc: ServiceDef) -> bool:
        return False  # Can't reliably stop a detached subprocess

    def status(self, svc: ServiceDef) -> ServiceInfo:
        return ServiceInfo(name=svc.name, status=ServiceStatus.UNKNOWN, provider="subprocess")

    def uninstall(self, svc: ServiceDef) -> bool:
        return True  # Nothing to uninstall


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

_PROVIDERS: list[ServiceProvider] = [
    LaunchdProvider(),
    SystemdProvider(),
    WindowsTaskProvider(),
    SubprocessProvider(),  # Always-available fallback
]


class ServiceManager:
    """Facade that picks the best available provider and delegates."""

    def __init__(
        self,
        name: str,
        binary: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ):
        self._svc = ServiceDef(
            name=name,
            binary=binary,
            args=args or [],
            env=env or {},
        )
        self._provider = self._pick_provider()

    def _pick_provider(self) -> ServiceProvider:
        for p in _PROVIDERS:
            if p.available():
                return p
        return SubprocessProvider()  # Should never happen

    @property
    def provider_name(self) -> str:
        return self._provider.name()

    def install(self) -> bool:
        return self._provider.install(self._svc)

    def start(self) -> bool:
        return self._provider.start(self._svc)

    def stop(self) -> bool:
        return self._provider.stop(self._svc)

    def status(self) -> ServiceInfo:
        return self._provider.status(self._svc)

    def uninstall(self) -> bool:
        return self._provider.uninstall(self._svc)

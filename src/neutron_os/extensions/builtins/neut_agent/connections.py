"""Post-setup hooks and lifecycle management for neut_agent connections.

Called by neut connect when a connection declares post_setup_module
pointing here. Keeps tool-specific setup logic in the owning extension.

Uses infra.services.ServiceManager for persistent service lifecycle
(launchd on macOS, systemd on Linux) — independent of how the binary
was installed.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
import urllib.request

log = logging.getLogger(__name__)

_OLLAMA_ENV = {
    "OLLAMA_FLASH_ATTENTION": "1",
    "OLLAMA_KV_CACHE_TYPE": "q8_0",
}


def _get_ollama_service():
    """Create a ServiceManager for Ollama."""
    from neutron_os.infra.services import ServiceManager

    binary = shutil.which("ollama") or "ollama"
    return ServiceManager(
        name="ollama",
        binary=binary,
        args=["serve"],
        env=_OLLAMA_ENV,
    )


def setup_ollama() -> int:
    """Post-install hook for Ollama: register as managed service + pull model.

    Called by `neut connect ollama` after installation. Installs a
    launchd/systemd service so Ollama runs persistently (survives reboots)
    with optimized settings. The user never thinks about Ollama again.
    """
    from neutron_os.extensions.builtins.settings.store import SettingsStore

    settings = SettingsStore()
    model = settings.get("routing.ollama_model", "llama3.2:1b")

    if not _is_ollama_serving():
        svc = _get_ollama_service()
        svc.install()
        svc.start()
        print("  Registering Ollama as managed service...")

        for _ in range(8):
            time.sleep(1)
            if _is_ollama_serving():
                print("  \u2713 Ollama running (managed service, starts at login)")
                break
        else:
            print("  \u26a0 Ollama service didn't start")
            svc_info = svc.status()
            print(f"    Status: {svc_info.status}")
            print("    Logs: ~/.neut/services/ollama.stderr.log")
            return 1
    else:
        print("  \u2713 Ollama already running")

    # Pull routing model if needed
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

    print(f"  Pulling routing model ({model})...")
    try:
        subprocess.run(
            ["ollama", "pull", model],
            check=True, timeout=300,
        )
        print(f"  \u2713 Model {model} ready")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print(f"  \u2717 Pull failed \u2014 try manually: ollama pull {model}")
        return 1

    print()
    return 0


def ensure_ollama_running() -> bool:
    """Silently ensure Ollama is serving. Called by the router before inference.

    Returns True if Ollama is available, False if not installed or won't start.
    Never prompts, never prints — this is a background operation.
    """
    if not shutil.which("ollama"):
        return False

    if _is_ollama_serving():
        return True

    # Try to start via managed service
    try:
        svc = _get_ollama_service()
        info = svc.status()

        from neutron_os.infra.services import ServiceStatus
        if info.status == ServiceStatus.NOT_INSTALLED:
            # Install and start
            svc.install()
            svc.start()
        elif info.status == ServiceStatus.STOPPED:
            svc.start()
        # else: already running or unknown — try anyway

    except Exception as e:
        log.debug("Service manager failed, trying direct start: %s", e)
        # Fallback: raw Popen (e.g., services module not available)
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            return False

    # Wait for it to come up
    for _ in range(5):
        time.sleep(0.5)
        if _is_ollama_serving():
            log.info("Ollama auto-started via managed service")
            return True

    log.debug("Ollama auto-start failed")
    return False


def _is_ollama_serving() -> bool:
    """Check if Ollama API is responding."""
    try:
        urllib.request.urlopen("http://localhost:11434", timeout=1)
        return True
    except Exception:
        return False

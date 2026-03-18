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


def setup_qwen_rascal() -> int:
    """Post-setup hook for Qwen on Rascal: configure models.toml with EC routing."""
    from neutron_os import REPO_ROOT
    models_path = REPO_ROOT / "runtime" / "config" / "models.toml"

    if not models_path.exists():
        print("  \u2717 models.toml not found — run neut config first")
        return 1

    content = models_path.read_text(encoding="utf-8")

    # Check if qwen-rascal is already properly configured
    if 'routing_tier = "export_controlled"' in content and "qwen-rascal" in content:
        print("  \u2713 Qwen on Rascal already configured for EC routing")

        # Check VPN reachability
        import socket
        try:
            sock = socket.create_connection(("10.159.142.118", 41883), timeout=2)
            sock.close()
            print("  \u2713 VPN connected — rascal is reachable")
        except Exception:
            print("  \u26a0 Rascal not reachable — connect to UT VPN first")

        print()
        return 0

    # Update existing qwen entry or add new one
    if "qwen-local" in content or "qwen-rascal" in content:
        # Replace existing qwen provider with properly configured one
        import re
        # Remove old qwen provider block
        content = re.sub(
            r'\[\[gateway\.providers\]\]\s*\n'
            r'name\s*=\s*"qwen-(?:local|rascal)".*?'
            r'(?=\[\[gateway\.providers\]\]|\Z)',
            '',
            content,
            flags=re.DOTALL,
        )

    # Add properly configured qwen-rascal provider
    qwen_block = '''
[[gateway.providers]]
name = "qwen-rascal"
endpoint = "https://10.159.142.118:41883/v1"
model = "qwen"
api_key_env = "QWEN_API_KEY"
priority = 1
routing_tier = "export_controlled"
requires_vpn = true
use_for = ["extraction", "synthesis", "fallback"]
'''
    content = content.rstrip() + "\n" + qwen_block

    # Also ensure anthropic has routing_tier = "public"
    if 'name = "anthropic"' in content and "routing_tier" not in content.split('name = "anthropic"')[1].split("[[")[0]:
        content = content.replace(
            'use_for = ["extraction", "synthesis", "correlation", "fallback"]',
            'routing_tier = "public"\n'
            'use_for = ["extraction", "synthesis", "correlation", "fallback"]',
            1,
        )

    models_path.write_text(content, encoding="utf-8")
    print("  \u2713 Configured Qwen on Rascal for export-controlled routing")
    print("    Anthropic → public queries")
    print("    Qwen/Rascal → export-controlled queries (VPN required)")

    # Check VPN
    import socket
    try:
        sock = socket.create_connection(("10.159.142.118", 41883), timeout=2)
        sock.close()
        print("  \u2713 VPN connected — rascal is reachable")
    except Exception:
        print("  \u26a0 Rascal not reachable — connect to UT VPN to use EC routing")

    print()
    return 0


def _is_ollama_serving() -> bool:
    """Check if Ollama API is responding."""
    try:
        urllib.request.urlopen("http://localhost:11434", timeout=1)
        return True
    except Exception:
        return False

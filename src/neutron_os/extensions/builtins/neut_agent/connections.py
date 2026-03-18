"""Post-setup hooks for neut_agent connections.

Called by neut connect when a connection declares post_setup_module
pointing here. Keeps tool-specific setup logic in the owning extension.
"""

from __future__ import annotations

import subprocess
import urllib.request


def setup_ollama() -> int:
    """Post-install hook for Ollama: ensure serving + pull routing model."""
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
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
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
                print("  \u26a0 Ollama didn't start \u2014 try `ollama serve` manually")
                return 1
        else:
            print("  Start later with: ollama serve")
            print()
            return 0

    # Check if routing model is pulled
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
            print(f"  \u2717 Pull failed \u2014 try manually: ollama pull {model}")
            return 1
    else:
        print(f"  Pull later with: ollama pull {model}")

    print()
    return 0

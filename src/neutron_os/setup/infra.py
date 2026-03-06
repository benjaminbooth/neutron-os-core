"""Infrastructure setup for NeutronOS.

Handles Docker, K3D, and PostgreSQL setup with:
- Automatic prerequisite detection
- Guided installation for missing components
- LLM-powered troubleshooting
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class InfraStatus(Enum):
    """Status of infrastructure components."""
    READY = "ready"
    MISSING = "missing"
    NEEDS_START = "needs_start"
    ERROR = "error"


@dataclass
class InfraCheck:
    """Result of an infrastructure check."""
    name: str
    status: InfraStatus
    version: str = ""
    message: str = ""
    fix_action: Optional[str] = None
    auto_fixable: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "version": self.version,
            "message": self.message,
            "fix_action": self.fix_action,
            "auto_fixable": self.auto_fixable,
        }


# ---------------------------------------------------------------------------
# Detection Functions
# ---------------------------------------------------------------------------

def check_docker() -> InfraCheck:
    """Check if Docker is installed and running."""
    docker_path = shutil.which("docker")
    if not docker_path:
        return InfraCheck(
            name="Docker",
            status=InfraStatus.MISSING,
            message="Docker not installed",
            fix_action="install_docker",
            auto_fixable=False,  # User must install Docker Desktop manually
        )

    # Check version
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True, text=True, timeout=5
        )
        version = result.stdout.strip().split()[2].rstrip(",") if result.stdout else ""
    except Exception:
        version = ""

    # Check if Docker daemon is running
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return InfraCheck(
                name="Docker",
                status=InfraStatus.READY,
                version=version,
                message="Running",
            )
        else:
            return InfraCheck(
                name="Docker",
                status=InfraStatus.NEEDS_START,
                version=version,
                message="Docker daemon not running",
                fix_action="start_docker",
                auto_fixable=True,
            )
    except subprocess.TimeoutExpired:
        return InfraCheck(
            name="Docker",
            status=InfraStatus.NEEDS_START,
            version=version,
            message="Docker daemon not responding",
            fix_action="start_docker",
            auto_fixable=True,
        )
    except Exception as e:
        return InfraCheck(
            name="Docker",
            status=InfraStatus.ERROR,
            version=version,
            message=str(e),
        )


def check_k3d() -> InfraCheck:
    """Check if K3D is installed."""
    k3d_path = shutil.which("k3d")
    if not k3d_path:
        return InfraCheck(
            name="K3D",
            status=InfraStatus.MISSING,
            message="K3D not installed",
            fix_action="install_k3d",
            auto_fixable=True,  # Can auto-install via brew or curl
        )

    try:
        result = subprocess.run(
            ["k3d", "version"],
            capture_output=True, text=True, timeout=5
        )
        # Parse version from "k3d version v5.6.0"
        version = ""
        if result.stdout:
            parts = result.stdout.strip().split()
            for p in parts:
                if p.startswith("v") or (p and p[0].isdigit()):
                    version = p
                    break

        return InfraCheck(
            name="K3D",
            status=InfraStatus.READY,
            version=version,
            message="Installed",
        )
    except Exception as e:
        return InfraCheck(
            name="K3D",
            status=InfraStatus.ERROR,
            message=str(e),
        )


def check_kubectl() -> InfraCheck:
    """Check if kubectl is installed."""
    kubectl_path = shutil.which("kubectl")
    if not kubectl_path:
        return InfraCheck(
            name="kubectl",
            status=InfraStatus.MISSING,
            message="kubectl not installed",
            fix_action="install_kubectl",
            auto_fixable=True,
        )

    try:
        result = subprocess.run(
            ["kubectl", "version", "--client", "-o", "json"],
            capture_output=True, text=True, timeout=5
        )
        version = ""
        if result.returncode == 0 and result.stdout:
            try:
                data = json.loads(result.stdout)
                version = data.get("clientVersion", {}).get("gitVersion", "")
            except json.JSONDecodeError:
                version = "installed"

        return InfraCheck(
            name="kubectl",
            status=InfraStatus.READY,
            version=version,
            message="Installed",
        )
    except Exception as e:
        return InfraCheck(
            name="kubectl",
            status=InfraStatus.ERROR,
            message=str(e),
        )


def check_neut_cluster() -> InfraCheck:
    """Check if the neut-local K3D cluster exists and is running."""
    try:
        result = subprocess.run(
            ["k3d", "cluster", "list", "-o", "json"],
            capture_output=True, text=True, timeout=10
        )

        clusters = json.loads(result.stdout) if result.stdout else []

        for cluster in clusters:
            if cluster.get("name") == "neut-local":
                running = cluster.get("serversRunning", 0) > 0
                if running:
                    return InfraCheck(
                        name="neut-local cluster",
                        status=InfraStatus.READY,
                        message="Running",
                    )
                else:
                    return InfraCheck(
                        name="neut-local cluster",
                        status=InfraStatus.NEEDS_START,
                        message="Cluster exists but stopped",
                        fix_action="start_cluster",
                        auto_fixable=True,
                    )

        return InfraCheck(
            name="neut-local cluster",
            status=InfraStatus.MISSING,
            message="Cluster not created",
            fix_action="create_cluster",
            auto_fixable=True,
        )
    except FileNotFoundError:
        return InfraCheck(
            name="neut-local cluster",
            status=InfraStatus.ERROR,
            message="K3D not installed",
        )
    except json.JSONDecodeError:
        return InfraCheck(
            name="neut-local cluster",
            status=InfraStatus.ERROR,
            message="Could not parse K3D output",
        )
    except Exception as e:
        return InfraCheck(
            name="neut-local cluster",
            status=InfraStatus.ERROR,
            message=str(e),
        )


# ---------------------------------------------------------------------------
# Installation Functions
# ---------------------------------------------------------------------------

def install_k3d() -> bool:
    """Install K3D using the appropriate method for the OS."""
    system = platform.system()

    if system == "Darwin":
        # macOS - prefer Homebrew
        if shutil.which("brew"):
            print("Installing K3D via Homebrew...")
            result = subprocess.run(
                ["brew", "install", "k3d"],
                capture_output=False
            )
            return result.returncode == 0

    # Linux/macOS fallback - use official install script
    print("Installing K3D via official script...")
    try:
        result = subprocess.run(
            ["bash", "-c", "curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash"],
            capture_output=False
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error installing K3D: {e}")
        return False


def install_kubectl() -> bool:
    """Install kubectl using the appropriate method for the OS."""
    system = platform.system()

    if system == "Darwin":
        # macOS - prefer Homebrew
        if shutil.which("brew"):
            print("Installing kubectl via Homebrew...")
            result = subprocess.run(
                ["brew", "install", "kubectl"],
                capture_output=False
            )
            return result.returncode == 0

    # kubectl often comes with Docker Desktop, so check again
    if shutil.which("kubectl"):
        return True

    print("Please install kubectl manually:")
    print("  https://kubernetes.io/docs/tasks/tools/")
    return False


def start_docker() -> bool:
    """Attempt to start Docker Desktop."""
    system = platform.system()

    if system == "Darwin":
        print("Starting Docker Desktop...")
        try:
            subprocess.run(
                ["open", "-a", "Docker"],
                capture_output=True
            )
            # Wait for Docker to start
            print("Waiting for Docker to initialize...")
            for i in range(30):
                time.sleep(2)
                result = subprocess.run(
                    ["docker", "info"],
                    capture_output=True, timeout=5
                )
                if result.returncode == 0:
                    print("Docker started successfully.")
                    return True
            print("Docker started but taking a while to initialize...")
            return True
        except Exception as e:
            print(f"Could not start Docker: {e}")
            return False
    elif system == "Linux":
        print("Starting Docker service...")
        try:
            result = subprocess.run(
                ["sudo", "systemctl", "start", "docker"],
                capture_output=False
            )
            return result.returncode == 0
        except Exception:
            print("Please start Docker manually: sudo systemctl start docker")
            return False

    print("Please start Docker Desktop manually.")
    return False


def start_cluster() -> bool:
    """Start the neut-local K3D cluster."""
    print("Starting neut-local cluster...")
    try:
        result = subprocess.run(
            ["k3d", "cluster", "start", "neut-local"],
            capture_output=False
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error starting cluster: {e}")
        return False


def create_cluster() -> bool:
    """Create and start the neut-local K3D cluster with PostgreSQL."""
    try:
        # Use the existing k3d_up function which handles everything
        from neutron_os.extensions.builtins.sense_agent.pgvector_store import k3d_up
        return k3d_up()
    except ImportError:
        print("Error: Could not import k3d_up. Run from project root.")
        return False
    except Exception as e:
        print(f"Error creating cluster: {e}")
        return False


# ---------------------------------------------------------------------------
# Main Infrastructure Setup
# ---------------------------------------------------------------------------

@dataclass
class InfraSetupResult:
    """Result of infrastructure setup."""
    success: bool
    checks: list[InfraCheck]
    message: str

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "checks": [c.to_dict() for c in self.checks],
            "message": self.message,
        }


def run_infra_checks(skip_cluster: bool = False) -> list[InfraCheck]:
    """Run all infrastructure checks without fixing anything."""
    checks = [
        check_docker(),
        check_k3d(),
        check_kubectl(),
    ]
    if not skip_cluster:
        # Only check cluster if K3D is installed
        if checks[1].status == InfraStatus.READY:
            checks.append(check_neut_cluster())
    return checks


def run_infra_setup(
    auto_fix: bool = True,
    interactive: bool = True,
    skip_cluster: bool = False,
) -> InfraSetupResult:
    """Run complete infrastructure setup.

    Args:
        auto_fix: Automatically fix issues that can be auto-fixed
        interactive: Prompt user for manual fixes
        skip_cluster: Skip cluster creation (just check prerequisites)

    Returns:
        InfraSetupResult with status of all checks
    """
    from neutron_os.setup import renderer

    checks: list[InfraCheck] = []
    all_ready = True

    # Step 1: Check Docker
    docker = check_docker()
    checks.append(docker)

    if docker.status == InfraStatus.MISSING:
        all_ready = False
        renderer.status_line("Docker", "Not installed", False)
        if interactive:
            _guide_docker_install()
        return InfraSetupResult(
            success=False,
            checks=checks,
            message="Docker Desktop must be installed first",
        )

    if docker.status == InfraStatus.NEEDS_START:
        renderer.status_line("Docker", "Not running", False)
        if auto_fix:
            if start_docker():
                docker.status = InfraStatus.READY
                docker.message = "Started"
                renderer.status_line("Docker", "Started", True)
            else:
                all_ready = False
        else:
            all_ready = False

    if docker.status == InfraStatus.READY:
        ver = f" ({docker.version})" if docker.version else ""
        renderer.status_line("Docker", f"Ready{ver}", True)

    # Step 2: Check K3D
    k3d = check_k3d()
    checks.append(k3d)

    if k3d.status == InfraStatus.MISSING:
        renderer.status_line("K3D", "Not installed", False)
        if auto_fix:
            renderer.info("Installing K3D...")
            if install_k3d():
                k3d.status = InfraStatus.READY
                k3d.message = "Installed"
                renderer.status_line("K3D", "Installed", True)
            else:
                all_ready = False
        else:
            all_ready = False
    elif k3d.status == InfraStatus.READY:
        ver = f" ({k3d.version})" if k3d.version else ""
        renderer.status_line("K3D", f"Ready{ver}", True)

    # Step 3: Check kubectl (usually comes with Docker Desktop)
    kubectl = check_kubectl()
    checks.append(kubectl)

    if kubectl.status == InfraStatus.MISSING:
        renderer.status_line("kubectl", "Not installed", False)
        if auto_fix:
            renderer.info("Installing kubectl...")
            if install_kubectl():
                kubectl.status = InfraStatus.READY
                renderer.status_line("kubectl", "Installed", True)
            else:
                all_ready = False
        else:
            all_ready = False
    elif kubectl.status == InfraStatus.READY:
        ver = f" ({kubectl.version})" if kubectl.version else ""
        renderer.status_line("kubectl", f"Ready{ver}", True)

    # Step 4: Check/create cluster (if not skipping)
    if not skip_cluster and k3d.status == InfraStatus.READY:
        cluster = check_neut_cluster()
        checks.append(cluster)

        if cluster.status == InfraStatus.MISSING:
            renderer.status_line("neut-local cluster", "Not created", False)
            if auto_fix:
                renderer.info("Creating cluster with PostgreSQL + pgvector...")
                if create_cluster():
                    cluster.status = InfraStatus.READY
                    cluster.message = "Created and running"
                    renderer.status_line("neut-local cluster", "Ready", True)
                else:
                    all_ready = False
            else:
                all_ready = False
        elif cluster.status == InfraStatus.NEEDS_START:
            renderer.status_line("neut-local cluster", "Stopped", False)
            if auto_fix:
                if start_cluster():
                    cluster.status = InfraStatus.READY
                    cluster.message = "Started"
                    renderer.status_line("neut-local cluster", "Started", True)
                else:
                    all_ready = False
            else:
                all_ready = False
        elif cluster.status == InfraStatus.READY:
            renderer.status_line("neut-local cluster", "Running", True)

    return InfraSetupResult(
        success=all_ready,
        checks=checks,
        message="Infrastructure ready" if all_ready else "Some components need attention",
    )


def _guide_docker_install() -> None:
    """Show Docker installation guidance."""
    from neutron_os.setup import renderer

    system = platform.system()

    renderer.blank()
    renderer.heading("Docker Desktop Required")
    renderer.text(
        "NeutronOS uses Docker to run PostgreSQL locally.\n"
        "This is the only manual installation required.\n"
    )

    if system == "Darwin":
        renderer.numbered_steps([
            "Go to https://www.docker.com/products/docker-desktop/",
            "Download Docker Desktop for Mac",
            "Open the .dmg and drag Docker to Applications",
            "Launch Docker from Applications",
            "Wait for Docker to finish starting (whale icon in menu bar)",
            "Run 'neut infra' again",
        ])

        # Offer to open the download page
        renderer.blank()
        if renderer.prompt_yn("Open Docker Desktop download page?", default=True):
            import webbrowser
            webbrowser.open("https://www.docker.com/products/docker-desktop/")

    elif system == "Linux":
        renderer.numbered_steps([
            "Install Docker Engine: https://docs.docker.com/engine/install/",
            "Add your user to the docker group:",
            "  sudo usermod -aG docker $USER",
            "Log out and back in (or run: newgrp docker)",
            "Run 'neut infra' again",
        ])

    elif system == "Windows":
        renderer.numbered_steps([
            "Go to https://www.docker.com/products/docker-desktop/",
            "Download Docker Desktop for Windows",
            "Run the installer",
            "Enable WSL 2 backend when prompted",
            "Restart your computer if required",
            "Launch Docker Desktop",
            "Run 'neut infra' again",
        ])

    renderer.blank()


# ---------------------------------------------------------------------------
# LLM-Powered Troubleshooting
# ---------------------------------------------------------------------------

def get_troubleshooting_context(checks: list[InfraCheck]) -> str:
    """Generate context for LLM troubleshooting."""
    system = platform.system()

    lines = [
        f"System: {system} {platform.release()}",
        f"Python: {platform.python_version()}",
        "",
        "Infrastructure Status:",
    ]

    for check in checks:
        status_icon = {
            InfraStatus.READY: "✓",
            InfraStatus.MISSING: "✗",
            InfraStatus.NEEDS_START: "○",
            InfraStatus.ERROR: "!",
        }.get(check.status, "?")

        lines.append(f"  {status_icon} {check.name}: {check.message}")
        if check.version:
            lines.append(f"      Version: {check.version}")

    return "\n".join(lines)


def troubleshoot_with_llm(checks: list[InfraCheck], error_output: str = "") -> str:
    """Use LLM to diagnose and suggest fixes for infrastructure issues.

    Returns suggested fixes as a string.
    """
    try:
        from neutron_os.ask import ask_llm
    except ImportError:
        return "LLM troubleshooting not available (ask module not found)"

    context = get_troubleshooting_context(checks)

    prompt = f"""You are helping troubleshoot NeutronOS infrastructure setup.

Current state:
{context}

{f"Error output: {error_output}" if error_output else ""}

The user needs:
1. Docker Desktop running
2. K3D installed (for local Kubernetes)
3. kubectl installed
4. neut-local K3D cluster with PostgreSQL + pgvector

Provide concise, actionable steps to fix any issues. Focus on the first blocking issue.
If Docker is missing, that's the priority - everything else depends on it.
Keep your response under 200 words.
"""

    try:
        response = ask_llm(prompt, max_tokens=500)
        return response
    except Exception as e:
        return f"Could not get LLM assistance: {e}"


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main(args: list[str] | None = None) -> int:
    """CLI entry point for infrastructure setup."""
    import argparse
    from neutron_os.setup import renderer

    parser = argparse.ArgumentParser(
        description="Set up NeutronOS infrastructure (Docker, K3D, PostgreSQL)",
        prog="neut infra",
    )
    parser.add_argument(
        "--check", "-c",
        action="store_true",
        help="Only check status, don't fix anything",
    )
    parser.add_argument(
        "--no-cluster",
        action="store_true",
        help="Skip cluster creation (just check prerequisites)",
    )
    parser.add_argument(
        "--troubleshoot", "-t",
        action="store_true",
        help="Use LLM to diagnose issues",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    parsed = parser.parse_args(args)

    if parsed.json:
        # JSON mode - quiet checks
        checks = run_infra_checks(skip_cluster=parsed.no_cluster)
        all_ready = all(c.status == InfraStatus.READY for c in checks)
        result = InfraSetupResult(
            success=all_ready,
            checks=checks,
            message="Infrastructure ready" if all_ready else "Issues found",
        )
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if all_ready else 1

    renderer.banner()
    renderer.heading("Infrastructure Setup")
    renderer.text("Checking Docker, K3D, and PostgreSQL...\n")

    result = run_infra_setup(
        auto_fix=not parsed.check,
        interactive=True,
        skip_cluster=parsed.no_cluster,
    )

    renderer.blank()

    if result.success:
        renderer.success("All infrastructure ready!")
        renderer.text("\nYou can now use:")
        renderer.text("  neut db status    # Check database connection")
        renderer.text("  neut db migrate   # Run schema migrations")
        renderer.text("  neut sense ...    # Run sense commands")
        return 0
    else:
        renderer.warning(result.message)

        if parsed.troubleshoot:
            renderer.blank()
            renderer.heading("LLM Diagnosis")
            suggestion = troubleshoot_with_llm(result.checks)
            renderer.text(suggestion)
        else:
            renderer.text("\nRun with --troubleshoot for LLM-powered diagnosis.")

        return 1


if __name__ == "__main__":
    sys.exit(main())

"""Interactive onboarding wizard for neut config.

Orchestrates the 6-phase flow:
  PROBE → SUMMARY → CREDENTIALS → CONFIG → TEST → DONE

Each phase auto-saves progress so users can resume with `neut config`.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional

from neutron_os.setup import renderer
from neutron_os.setup.guides import (
    CREDENTIAL_GUIDES,
    CredentialGuide,
    get_llm_guides,
)
from neutron_os.setup.probe import ProbeResult, run_probe
from neutron_os.setup.state import SetupState, load_state, save_state
from neutron_os.setup.tester import ChannelTester

# Phase names in order
# infra phase sets up Docker/K3D/PostgreSQL if needed
PHASES = ["probe", "summary", "infra", "credentials", "config", "test", "done"]


class SetupWizard:
    """Orchestrates the interactive setup flow."""

    def __init__(self, root: Optional[Path] = None):
        if root is None:
            from neutron_os.setup.probe import _find_project_root
            root = _find_project_root()
        self.root = root
        self.state: SetupState = load_state(root) or SetupState()
        self.probe_result: Optional[ProbeResult] = None

    def run(self) -> None:
        """Run the full wizard, resuming from last saved phase."""
        renderer.banner()

        # Determine starting phase
        start_idx = 0
        if self.state.completed_phases:
            last = self.state.completed_phases[-1]
            if last in PHASES:
                start_idx = PHASES.index(last) + 1

        # All phases already done — show status instead of empty resume
        if start_idx >= len(PHASES):
            renderer.info("Setup already complete. Showing current status.\n")
            self.show_status()
            renderer.blank()
            renderer.info("Run 'neut config --reset' to start over.")
            return

        if start_idx > 0:
            renderer.info("Resuming from where you left off...\n")
        else:
            renderer.text("Let's get your environment ready.\n")

        for phase in PHASES[start_idx:]:
            self.state.current_phase = phase
            save_state(self.state, self.root)

            handler = getattr(self, f"_phase_{phase}", None)
            if handler:
                handler()

            self.state.mark_phase_complete(phase)
            save_state(self.state, self.root)

    # ------------------------------------------------------------------
    # Phase: PROBE
    # ------------------------------------------------------------------

    def _phase_probe(self) -> None:
        renderer.heading("Checking your system")
        renderer.text("This takes a few seconds...\n")
        self.probe_result = run_probe(self.root)
        self.state.probe_result = self.probe_result.to_dict()

    # ------------------------------------------------------------------
    # Phase: SUMMARY
    # ------------------------------------------------------------------

    @staticmethod
    def _friendly_os(os_name: str, os_version: str) -> str:
        """Convert OS identifiers to user-friendly names."""
        if os_name == "Darwin":
            return f"macOS {os_version}"
        if os_name == "Windows":
            return f"Windows {os_version}"
        if os_name == "Linux":
            return f"Linux {os_version}"
        return f"{os_name} {os_version}"

    @staticmethod
    def _clean_version(raw: str) -> str:
        """Strip noise from version strings (e.g. 'git version 2.50.1 (Apple Git-155)' → '2.50.1')."""
        import re
        match = re.search(r"(\d+\.\d+[\.\d]*)", raw)
        return match.group(1) if match else raw

    def _phase_summary(self) -> None:
        if self.probe_result is None:
            self.probe_result = ProbeResult.from_dict(self.state.probe_result)

        pr = self.probe_result
        renderer.heading("Your System")

        # System info
        renderer.status_line(
            "Operating system",
            self._friendly_os(pr.os_name, pr.os_version),
            True,
        )
        renderer.status_line("Python", pr.python_version, True)

        if pr.is_git_repo:
            renderer.status_line("Project", "Found (branch: {})".format(pr.git_branch), True)
        else:
            renderer.status_line("Project", "Not inside a git repository", False)

        renderer.status_line(
            "Network", "Connected" if pr.dns_available else "No network detected", pr.dns_available
        )
        renderer.blank()

        # Dependencies
        renderer.heading("Tools & Libraries")
        for dep in pr.dependencies:
            label = dep.purpose or dep.name
            if dep.found:
                ver = f" ({self._clean_version(dep.version)})" if dep.version else ""
                renderer.status_line(label, f"Ready{ver}", True)
            else:
                tag = "required" if dep.required else "optional"
                renderer.status_line(label, f"Not found ({tag})", not dep.required)
        renderer.blank()

        # Existing config — group MS 365 into one line
        working = []
        needs_setup = []
        ms_vars = {"MS_GRAPH_CLIENT_ID", "MS_GRAPH_CLIENT_SECRET", "MS_GRAPH_TENANT_ID"}
        ms_set = all(pr.env_vars_set.get(v) for v in ms_vars)

        for var, is_set in pr.env_vars_set.items():
            if var in ms_vars:
                continue  # handled as a group below
            name = renderer.friendly_name(var)
            if is_set:
                working.append(name)
            else:
                needs_setup.append(name)

        # Add MS 365 as a single grouped item
        if ms_set:
            working.append("Microsoft 365 connection")
        else:
            needs_setup.append("Microsoft 365 connection")

        if working:
            renderer.heading("Already Configured")
            for item in working:
                renderer.success(item)

        if needs_setup:
            renderer.heading("Needs Setup")
            for item in needs_setup:
                renderer.warning(item)
        renderer.blank()

    # ------------------------------------------------------------------
    # Phase: INFRA (Docker, K3D, PostgreSQL)
    # ------------------------------------------------------------------

    def _phase_infra(self) -> None:
        """Set up infrastructure: Docker, K3D, PostgreSQL."""
        from neutron_os.setup.infra import (
            check_docker,
            check_k3d,
            check_neut_cluster,
            InfraStatus,
            run_infra_setup,
        )

        # Quick check if infrastructure is already ready
        docker = check_docker()
        k3d = check_k3d()

        if docker.status == InfraStatus.READY and k3d.status == InfraStatus.READY:
            cluster = check_neut_cluster()
            if cluster.status == InfraStatus.READY:
                renderer.heading("Infrastructure")
                renderer.success("Docker, K3D, and PostgreSQL already configured")
                renderer.blank()
                return

        renderer.heading("Infrastructure Setup")
        renderer.text(
            "NeutronOS uses Docker and K3D to run PostgreSQL locally.\n"
            "This provides the database for document embeddings and history.\n"
        )

        # Check if user wants to set up infrastructure now
        if not renderer.prompt_yn("Set up local database infrastructure now?", default=True):
            renderer.info("Skipped — you can set this up later with: neut infra")
            self.state.infra_configured = False
            return

        # Run the infrastructure setup
        renderer.blank()
        result = run_infra_setup(
            auto_fix=True,
            interactive=True,
            skip_cluster=False,
        )

        renderer.blank()
        if result.success:
            renderer.success("Infrastructure ready!")
            self.state.infra_configured = True
        else:
            renderer.warning("Some infrastructure components need attention.")
            renderer.text("You can complete setup later with: neut infra")
            self.state.infra_configured = False

        renderer.blank()

    # ------------------------------------------------------------------
    # Phase: CREDENTIALS
    # ------------------------------------------------------------------

    def _phase_credentials(self) -> None:
        renderer.heading("Connection Settings")
        renderer.text("Let's set up your connections. You can skip any for now.\n")

        # Re-hydrate probe result if needed
        if self.probe_result is None:
            self.probe_result = ProbeResult.from_dict(self.state.probe_result)

        # Group MS 365 credentials
        ms_vars = {"MS_GRAPH_CLIENT_ID", "MS_GRAPH_CLIENT_SECRET", "MS_GRAPH_TENANT_ID"}

        # Process LLM guides first (enables chat-assisted mode), then the rest
        llm_envs = {g.env_var for g in get_llm_guides()}
        llm_guides = [g for g in CREDENTIAL_GUIDES if g.env_var in llm_envs]
        non_ms_guides = [
            g for g in CREDENTIAL_GUIDES
            if g.env_var not in llm_envs and g.env_var not in ms_vars
        ]
        ms_guides = [g for g in CREDENTIAL_GUIDES if g.env_var in ms_vars]

        for guide in llm_guides + non_ms_guides:
            # Skip already-configured credentials
            if self.state.credentials_configured.get(guide.env_var):
                continue
            if self.probe_result.env_vars_set.get(guide.env_var):
                renderer.success(f"{guide.display_name} — already set")
                self.state.credentials_configured[guide.env_var] = True
                save_state(self.state, self.root)
                continue

            self._configure_credential(guide)

        # Handle MS 365 as a group
        ms_all_set = all(
            self.state.credentials_configured.get(g.env_var)
            or self.probe_result.env_vars_set.get(g.env_var)
            for g in ms_guides
        )
        if not ms_all_set:
            self._configure_ms365_group(ms_guides)

    def _configure_ms365_group(self, guides: list[CredentialGuide]) -> None:
        """Walk through all 3 MS 365 credentials as one grouped section."""
        renderer.divider()
        renderer.text(
            f"\n  {renderer._c(renderer._Colors.BOLD, 'Microsoft 365 connection')} (required)"
        )
        renderer.text("  Enables file sharing, document storage, and team collaboration.")
        renderer.text("  This needs 3 values from the Azure Portal.\n")

        if not renderer.prompt_yn("Set up Microsoft 365 now?", default=False):
            renderer.info("Skipped — you can set this up later with: neut config --set ms_graph_client_id")
            for g in guides:
                self.state.credentials_configured[g.env_var] = False
            save_state(self.state, self.root)
            return

        # Show combined steps
        url = "https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps"
        renderer.numbered_steps([
            "Go to the Azure Portal",
            'Navigate to "App registrations" and create a new registration',
            "From the Overview page, copy the Application (client) ID",
            "Copy the Directory (tenant) ID from the same page",
            'Go to "Certificates & secrets" → "New client secret" and copy the Value',
        ])
        renderer.blank()
        renderer.text(f"  Link: {renderer._c(renderer._Colors.DIM, url)}")
        renderer.blank()

        # Offer to open browser once for all three
        if renderer.prompt_yn("Open this page in your browser?"):
            webbrowser.open(url)
            renderer.blank()
            renderer.info("A page should have opened in your browser.")
            renderer.info("Follow the steps above, then come back here to paste each value.")
            renderer.blank()

        # Prompt for each value
        for guide in guides:
            env_var_set = (self.probe_result.env_vars_set.get(guide.env_var)
                           if self.probe_result else False)
            if self.state.credentials_configured.get(guide.env_var) or env_var_set:
                renderer.success(f"{guide.display_name} — already set")
                self.state.credentials_configured[guide.env_var] = True
                continue

            renderer.blank()
            renderer.text(f"  {renderer._c(renderer._Colors.BOLD, guide.display_name)}")
            self._prompt_and_save_credential(guide)

    def _configure_credential(self, guide: CredentialGuide) -> None:
        """Walk the user through configuring a single credential."""
        renderer.divider()
        tag = "required" if guide.required else "optional"
        renderer.text(f"\n  {renderer._c(renderer._Colors.BOLD, guide.display_name)} ({tag})")
        renderer.text(f"  {guide.description}\n")

        if not renderer.prompt_yn(f"Set up {guide.display_name} now?", default=False):
            renderer.info("Skipped — you can set this up later with: neut config --set "
                          f"{guide.env_var.lower()}")
            self.state.credentials_configured[guide.env_var] = False
            save_state(self.state, self.root)
            return

        # Show steps and URL
        renderer.numbered_steps(guide.steps)
        if guide.url:
            renderer.blank()
            renderer.text(f"  Link: {renderer._c(renderer._Colors.DIM, guide.url)}")
        renderer.blank()

        # Offer to open URL
        if guide.url and renderer.prompt_yn("Open this page in your browser?"):
            webbrowser.open(guide.url)
            renderer.blank()
            renderer.info("A page should have opened in your browser.")
            renderer.info("Follow the steps above, then come back here to paste the value.")
            renderer.blank()

        self._prompt_and_save_credential(guide)

    def _prompt_and_save_credential(self, guide: CredentialGuide) -> None:
        """Prompt for a credential value with validation and retry."""
        renderer.text("(press Enter with nothing to skip)\n")
        for attempt in range(3):
            value = renderer.prompt_secret(f"Paste your {guide.display_name}")
            if not value:
                renderer.info("Skipped")
                self.state.credentials_configured[guide.env_var] = False
                save_state(self.state, self.root)
                return

            if guide.validate(value):
                self._save_credential(guide.env_var, value)
                renderer.success(f"{guide.display_name} saved")
                self.state.credentials_configured[guide.env_var] = True
                save_state(self.state, self.root)
                return
            else:
                remaining = 2 - attempt
                if remaining > 0:
                    renderer.warning(
                        f"That doesn't look right. "
                        f"({remaining} {'tries' if remaining > 1 else 'try'} left)"
                    )
                else:
                    renderer.error("Could not validate — saving anyway. You can fix later.")
                    self._save_credential(guide.env_var, value)
                    self.state.credentials_configured[guide.env_var] = True
                    save_state(self.state, self.root)
                    return

    def _save_credential(self, env_var: str, value: str) -> None:
        """Append or update a credential in the .env file."""
        env_path = self.root / ".env"

        # Also set in current process
        os.environ[env_var] = value

        if env_path.exists():
            content = env_path.read_text(encoding="utf-8")
            # Update existing line
            pattern = re.compile(rf"^{re.escape(env_var)}=.*$", re.MULTILINE)
            if pattern.search(content):
                content = pattern.sub(f"{env_var}={value}", content)
                env_path.write_text(content, encoding="utf-8")
                return

        # Append new line
        with open(env_path, "a", encoding="utf-8") as f:
            f.write(f"\n{env_var}={value}\n")

    # ------------------------------------------------------------------
    # Phase: CONFIG
    # ------------------------------------------------------------------

    def _phase_config(self) -> None:
        renderer.heading("Configuration Files")

        # Check which files already exist
        facility_exists = (self.root / "runtime" / "config" / "facility.toml").exists()
        models_exists = (self.root / "runtime" / "config" / "models.toml").exists()
        docflow_exists = (self.root / ".doc-workflow.yaml").exists()
        claude_exists = (self.root / ".claude" / "context.md").exists()

        all_exist = facility_exists and models_exists and docflow_exists and claude_exists
        if all_exist:
            renderer.info("All configuration files already in place.")
            self.state.config_files_created["facility.toml"] = True
            self.state.config_files_created["models.toml"] = True
            self.state.config_files_created[".doc-workflow.yaml"] = True
            self.state.config_files_created[".claude/context.md"] = True
            renderer.blank()
            return

        renderer.text("Setting up your project configuration.\n")

        # Only ask facility questions if facility.toml needs creating
        facility_type = "research"
        facility_name = "My Facility"
        if not facility_exists:
            facility_type = self._ask_facility_type()
            facility_name = renderer.prompt_text(
                "What's the name of your facility?", default="My Facility"
            )
            self.state.user_choices["facility_type"] = facility_type
            self.state.user_choices["facility_name"] = facility_name

        # Generate only missing config files
        self._generate_facility_toml(facility_name, facility_type)
        self._generate_models_toml()
        self._generate_doc_workflow_yaml()
        self._generate_claude_context()

        renderer.blank()

    def _ask_facility_type(self) -> str:
        options = ["Research reactor", "Commercial reactor", "Government facility"]
        idx = renderer.prompt_choice(
            "What type of facility are you working with?", options
        )
        return ["research", "commercial", "government"][idx]

    def _generate_facility_toml(self, name: str, ftype: str) -> None:
        """Generate facility.toml from template."""
        dest = self.root / "runtime" / "config" / "facility.toml"
        if dest.exists():
            renderer.info("facility.toml already exists — keeping current version")
            self.state.config_files_created["facility.toml"] = True
            return

        template = self.root / "runtime" / "config.example" / "facility.toml"
        if not template.exists():
            renderer.warning("facility.toml template not found — skipping")
            return

        content = template.read_text(encoding="utf-8")
        content = content.replace('name = "UT TRIGA Mark II"', f'name = "{name}"')
        content = content.replace('type = "research"', f'type = "{ftype}"')

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        renderer.success("Created facility.toml")
        self.state.config_files_created["facility.toml"] = True

    def _generate_models_toml(self) -> None:
        """Generate models.toml with detected LLM providers uncommented."""
        dest = self.root / "runtime" / "config" / "models.toml"
        if dest.exists():
            renderer.info("models.toml already exists — keeping current version")
            self.state.config_files_created["models.toml"] = True
            return

        template = self.root / "runtime" / "config.example" / "models.toml"
        if not template.exists():
            renderer.warning("models.toml template not found — skipping")
            return

        content = template.read_text(encoding="utf-8")

        # Uncomment providers based on available keys
        if os.environ.get("ANTHROPIC_API_KEY"):
            # Uncomment the Anthropic provider block
            content = content.replace("# [[gateway.providers]]", "[[gateway.providers]]", 1)
            content = content.replace('# name = "anthropic"', 'name = "anthropic"')
            content = content.replace(
                '# endpoint = "https://api.anthropic.com/v1"',
                'endpoint = "https://api.anthropic.com/v1"',
            )
            content = content.replace(
                '# model = "claude-sonnet-4-20250514"',
                'model = "claude-sonnet-4-20250514"',
            )
            content = content.replace(
                '# api_key_env = "ANTHROPIC_API_KEY"',
                'api_key_env = "ANTHROPIC_API_KEY"',
            )
            content = content.replace("# priority = 1", "priority = 1")

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        renderer.success("Created models.toml")
        self.state.config_files_created["models.toml"] = True

    def _generate_doc_workflow_yaml(self) -> None:
        """Generate .doc-workflow.yaml from template."""
        dest = self.root / ".doc-workflow.yaml"
        if dest.exists():
            renderer.info(".doc-workflow.yaml already exists — keeping current version")
            self.state.config_files_created[".doc-workflow.yaml"] = True
            return

        template = self.root / ".doc-workflow.yaml.example"
        if not template.exists():
            renderer.warning(".doc-workflow.yaml template not found — skipping")
            return

        content = template.read_text(encoding="utf-8")

        # Set storage provider based on MS 365 availability
        has_ms = all(
            os.environ.get(v)
            for v in ["MS_GRAPH_CLIENT_ID", "MS_GRAPH_CLIENT_SECRET", "MS_GRAPH_TENANT_ID"]
        )
        if not has_ms:
            # Switch to local storage if MS 365 isn't configured
            content = content.replace("provider: onedrive", "provider: local")

        dest.write_text(content, encoding="utf-8")
        renderer.success("Created .doc-workflow.yaml")
        self.state.config_files_created[".doc-workflow.yaml"] = True

    def _generate_claude_context(self) -> None:
        """Generate .claude/context.md from template."""
        dest = self.root / ".claude" / "context.md"
        if dest.exists():
            renderer.info(".claude/context.md already exists — keeping current version")
            self.state.config_files_created[".claude/context.md"] = True
            return

        template = self.root / ".claude.example" / "context.md"
        if not template.exists():
            renderer.warning(".claude/context.md template not found — skipping")
            return

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template, dest)
        renderer.success("Created .claude/context.md — edit this with your details")
        self.state.config_files_created[".claude/context.md"] = True

    # ------------------------------------------------------------------
    # Phase: TEST
    # ------------------------------------------------------------------

    def _phase_test(self) -> None:
        renderer.heading("Testing Connections")
        renderer.text("Verifying each configured connection...\n")

        tester = ChannelTester(self.root)
        results = tester.run_all()

        for i, result in enumerate(results):
            renderer.progress_bar(i + 1, len(results))
            if result.skipped:
                renderer.info(f"{result.display_name}: {result.message}")
            elif result.passed:
                renderer.success(f"{result.display_name}: {result.message}")
            else:
                renderer.error(f"{result.display_name}: {result.message}")

            status = "pass" if result.passed else ("skip" if result.skipped else "fail")
            self.state.test_results[result.channel] = status

        # Store display names for the done phase
        self.state.user_choices["_channel_names"] = {
            r.channel: r.display_name for r in results
        }

        save_state(self.state, self.root)
        renderer.blank()

    # ------------------------------------------------------------------
    # Phase: DONE
    # ------------------------------------------------------------------

    def _phase_done(self) -> None:
        renderer.heading("Setup Complete")
        renderer.blank()

        # Note about saved credentials
        env_path = self.root / ".env"
        if env_path.exists():
            renderer.success("Your connection settings are saved in .env")
            renderer.info("They load automatically every time you run a neut command.")
            renderer.blank()

        # Summary of results
        passed = sum(1 for v in self.state.test_results.values() if v == "pass")
        total = len(self.state.test_results)
        renderer.text(f"  {passed}/{total} connections working\n")

        # Show working connections
        channel_names = self.state.user_choices.get("_channel_names", {})
        for channel, status in self.state.test_results.items():
            name = channel_names.get(channel, channel.replace("_", " ").title())
            if status == "pass":
                renderer.success(name)
            elif status == "skip":
                renderer.info(f"{name} (not configured)")
            else:
                renderer.error(f"{name} (needs attention)")

        renderer.blank()

        # Offer to install the `neut` shortcut command
        import shutil
        if not shutil.which("neut"):
            self._offer_shell_alias()

        cmd = "neut" if shutil.which("neut") else "python neut.py"

        renderer.heading("Next Steps")
        renderer.text("Try these commands:")
        renderer.text(f"  {cmd} doc status      — Check document lifecycle status")
        renderer.text(f"  {cmd} doc providers   — List available document providers")
        renderer.text(f"  {cmd} setup --status  — Review your configuration anytime")
        renderer.blank()

    # ------------------------------------------------------------------
    # Shell alias
    # ------------------------------------------------------------------

    def _offer_shell_alias(self) -> None:
        """Add a `neut` alias to the user's shell config."""
        # Find venv binary - check parent dir first (workspace layout), then local
        venv_neut = self.root.parent / ".venv" / "bin" / "neut"
        if not venv_neut.exists():
            venv_neut = self.root / ".venv" / "bin" / "neut"
        if not venv_neut.exists():
            # Fall back to hoping it's on PATH
            venv_neut = Path("neut")

        if platform.system() == "Windows":
            self._offer_powershell_alias(venv_neut)
            return

        shell = os.environ.get("SHELL", "")
        if "zsh" in shell:
            rc_file = Path.home() / ".zshrc"
            source_hint = "source ~/.zshrc"
        elif "bash" in shell:
            rc_file = Path.home() / ".bashrc"
            source_hint = "source ~/.bashrc"
        else:
            return  # Unknown shell, skip

        alias_line = f'alias neut="{venv_neut}"'

        # Don't duplicate
        if rc_file.exists():
            content = rc_file.read_text(encoding="utf-8")
            if "alias neut=" in content:
                return

        with open(rc_file, "a", encoding="utf-8") as f:
            f.write(f"\n# Neutron OS CLI shortcut\n{alias_line}\n")

        renderer.success(f"Added 'neut' shortcut to {rc_file.name}")
        renderer.info(f"Open a new terminal or run: {source_hint}")
        renderer.blank()

    def _offer_powershell_alias(self, venv_neut: Path) -> None:
        """Add a `neut` function to the PowerShell profile."""
        try:
            # Get PowerShell profile path
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "$PROFILE"],
                capture_output=True, text=True, timeout=5,
            )
            profile_path = result.stdout.strip()
            if not profile_path:
                return
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return

        profile = Path(profile_path)
        # On Windows, venv binary is in Scripts\neut.exe
        if venv_neut.suffix != ".exe":
            venv_neut = venv_neut.parent.parent / "Scripts" / "neut.exe"
        func_line = f'function neut {{ & "{venv_neut}" @args }}'

        # Don't duplicate
        if profile.exists():
            content = profile.read_text(encoding="utf-8")
            if "function neut" in content:
                return

        profile.parent.mkdir(parents=True, exist_ok=True)
        with open(profile, "a", encoding="utf-8") as f:
            f.write(f"\n# Neutron OS CLI shortcut\n{func_line}\n")

        renderer.success("Added 'neut' shortcut to PowerShell profile")
        renderer.info("Open a new PowerShell window to use it.")
        renderer.blank()

    # ------------------------------------------------------------------
    # Status display (non-interactive)
    # ------------------------------------------------------------------

    def _show_repo_sources(self) -> None:
        """Probe configured repo sources and display status."""
        renderer.heading("Repository Sources")
        try:
            from neutron_os.extensions.builtins.repo.config import detect_sources
            sources = detect_sources()
            if not sources:
                renderer.warning("No repo sources detected (set GITLAB_TOKEN or GITHUB_TOKEN)")
                return
            for source in sources:
                # Try to authenticate
                try:
                    from neutron_os.extensions.builtins.repo.orchestrator import _create_provider
                    provider = _create_provider(source)
                    ok = provider.authenticate()
                except Exception:
                    ok = False
                label = f"{source.provider.title()}  {source.group_or_org} ({source.token_env})"
                if ok:
                    renderer.success(label)
                else:
                    renderer.error(f"{label} — auth failed")
            renderer.text(f"\n  {len(sources)} repo source(s) detected")
        except Exception as exc:
            renderer.warning(f"Could not probe repo sources: {exc}")

    def show_status(self) -> None:
        """Display current configuration status without entering wizard."""
        renderer.heading("Neutron OS Configuration Status")

        probe = run_probe(self.root)

        # Connection settings
        renderer.heading("Connection Settings")
        for var, is_set in probe.env_vars_set.items():
            name = renderer.friendly_name(var)
            if is_set:
                renderer.success(f"{name} — configured")
            else:
                renderer.warning(f"{name} — not set")

        # Repo sources
        self._show_repo_sources()

        # Config files
        renderer.heading("Configuration Files")
        for path, exists in probe.config_files_exist.items():
            if exists:
                renderer.success(path)
            else:
                renderer.warning(f"{path} — missing")

        # Dependencies
        renderer.heading("Tools & Libraries")
        for dep in probe.dependencies:
            label = dep.purpose or dep.name
            if dep.found:
                ver = f" ({dep.version})" if dep.version else ""
                renderer.status_line(label, f"Found{ver}", True)
            else:
                tag = "required" if dep.required else "optional"
                renderer.status_line(label, f"Not found ({tag})", not dep.required)

        renderer.blank()

    # ------------------------------------------------------------------
    # Fix a specific connection
    # ------------------------------------------------------------------

    def fix(self, name: str) -> None:
        """Reconfigure a specific connection by credential name."""
        # Normalize: accept both env var name and lowercase form
        lookup = name.upper().replace("-", "_")

        from neutron_os.setup.guides import get_guide
        guide = get_guide(lookup)
        if guide is None:
            # Try matching by lowercase
            for g in CREDENTIAL_GUIDES:
                if g.env_var.lower() == name.lower():
                    guide = g
                    break

        if guide is None:
            renderer.error(f"Unknown connection: {name}")
            renderer.text("Available connections:")
            for g in CREDENTIAL_GUIDES:
                renderer.text(f"  {g.env_var.lower()} — {g.display_name}")
            return

        renderer.heading(f"Reconfigure: {guide.display_name}")
        self._configure_credential(guide)
        renderer.success("Done. Run 'neut config --status' to verify.")

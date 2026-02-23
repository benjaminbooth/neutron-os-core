"""Tests for tools.agents.setup.wizard."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.agents.setup.renderer import set_color_enabled
from tools.agents.setup.state import SetupState, save_state
from tools.agents.setup.wizard import PHASES, SetupWizard


@pytest.fixture(autouse=True)
def _disable_color():
    set_color_enabled(False)
    yield
    set_color_enabled(False)


class TestPhases:
    def test_phase_order(self):
        assert PHASES == ["probe", "summary", "credentials", "config", "test", "done"]

    def test_all_phases_have_handlers(self):
        wizard = SetupWizard.__new__(SetupWizard)
        wizard.root = None
        wizard.state = SetupState()
        wizard.probe_result = None
        for phase in PHASES:
            handler = getattr(wizard, f"_phase_{phase}", None)
            assert handler is not None, f"Missing handler for phase: {phase}"


class TestWizardProbe:
    def test_probe_populates_state(self, tmp_path):
        wizard = SetupWizard(root=tmp_path)
        wizard._phase_probe()
        assert wizard.probe_result is not None
        assert wizard.state.probe_result != {}
        assert wizard.probe_result.os_name != ""


class TestFriendlyOS:
    def test_darwin_becomes_macos(self):
        assert SetupWizard._friendly_os("Darwin", "25.3.0") == "macOS 25.3.0"

    def test_linux_stays_linux(self):
        assert SetupWizard._friendly_os("Linux", "6.1.0") == "Linux 6.1.0"

    def test_windows_stays_windows(self):
        assert SetupWizard._friendly_os("Windows", "10") == "Windows 10"

    def test_unknown_os_passes_through(self):
        assert SetupWizard._friendly_os("FreeBSD", "13.2") == "FreeBSD 13.2"


class TestCleanVersion:
    def test_strips_git_noise(self):
        assert SetupWizard._clean_version("git version 2.50.1 (Apple Git-155)") == "2.50.1"

    def test_already_clean(self):
        assert SetupWizard._clean_version("3.8.3") == "3.8.3"

    def test_pandoc_version(self):
        assert SetupWizard._clean_version("pandoc 3.8.3") == "3.8.3"

    def test_no_match_passes_through(self):
        assert SetupWizard._clean_version("unknown") == "unknown"


class TestWizardSummary:
    def test_summary_displays(self, tmp_path, capsys):
        wizard = SetupWizard(root=tmp_path)
        wizard._phase_probe()
        wizard._phase_summary()
        out = capsys.readouterr().out
        assert "Your System" in out

    def test_summary_shows_macos_not_darwin(self, tmp_path, capsys):
        wizard = SetupWizard(root=tmp_path)
        wizard._phase_probe()
        if wizard.probe_result and wizard.probe_result.os_name == "Darwin":
            wizard._phase_summary()
            out = capsys.readouterr().out
            assert "macOS" in out
            assert "Darwin" not in out

    def test_summary_groups_ms365(self, tmp_path, capsys, monkeypatch):
        monkeypatch.delenv("MS_GRAPH_CLIENT_ID", raising=False)
        monkeypatch.delenv("MS_GRAPH_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("MS_GRAPH_TENANT_ID", raising=False)
        wizard = SetupWizard(root=tmp_path)
        wizard._phase_probe()
        wizard._phase_summary()
        out = capsys.readouterr().out
        # Should show one grouped item, not three separate ones
        assert "Microsoft 365 connection" in out
        assert "Microsoft 365 app ID" not in out


class TestWizardConfig:
    def test_generates_files(self, tmp_path, monkeypatch):
        # Set up template files
        config_example = tmp_path / "tools" / "agents" / "config.example"
        config_example.mkdir(parents=True)
        (config_example / "facility.toml").write_text(
            '[facility]\nname = "UT TRIGA Mark II"\ntype = "research"\n'
        )
        (config_example / "models.toml").write_text(
            '[gateway]\nformat = "openai"\n'
        )
        (tmp_path / ".doc-workflow.yaml.example").write_text(
            "storage:\n  provider: onedrive\n"
        )
        claude_example = tmp_path / ".claude.example"
        claude_example.mkdir()
        (claude_example / "context.md").write_text("# My Context\n")

        wizard = SetupWizard(root=tmp_path)
        # Mock user input
        monkeypatch.setattr("builtins.input", lambda _: "1")  # Research reactor
        monkeypatch.setattr(
            "tools.agents.setup.renderer.prompt_text",
            lambda label, default="": "Test Facility",
        )
        monkeypatch.setattr(
            "tools.agents.setup.renderer.prompt_choice",
            lambda q, opts: 0,
        )

        wizard._phase_config()

        assert (tmp_path / "tools" / "agents" / "config" / "facility.toml").exists()
        assert (tmp_path / "tools" / "agents" / "config" / "models.toml").exists()
        assert (tmp_path / ".doc-workflow.yaml").exists()
        assert (tmp_path / ".claude" / "context.md").exists()

    def test_skips_existing_files(self, tmp_path, monkeypatch):
        # Create existing files
        config_dir = tmp_path / "tools" / "agents" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "facility.toml").write_text("existing")
        (config_dir / "models.toml").write_text("existing")
        (tmp_path / ".doc-workflow.yaml").write_text("existing")
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "context.md").write_text("existing")

        wizard = SetupWizard(root=tmp_path)
        monkeypatch.setattr(
            "tools.agents.setup.renderer.prompt_text",
            lambda label, default="": "Test",
        )
        monkeypatch.setattr(
            "tools.agents.setup.renderer.prompt_choice",
            lambda q, opts: 0,
        )

        wizard._phase_config()

        # Files should not be overwritten
        assert (config_dir / "facility.toml").read_text() == "existing"
        assert (config_dir / "models.toml").read_text() == "existing"


class TestWizardResume:
    def test_resumes_from_saved_state(self, tmp_path, monkeypatch, capsys):
        # Save state with probe and summary already done
        state = SetupState(
            current_phase="credentials",
            completed_phases=["probe", "summary"],
            probe_result={"os_name": "Darwin", "python_version": "3.11.0"},
        )
        save_state(state, tmp_path)

        wizard = SetupWizard(root=tmp_path)
        assert wizard.state.completed_phases == ["probe", "summary"]


class TestWizardSaveCredential:
    def test_creates_new_env_file(self, tmp_path):
        wizard = SetupWizard(root=tmp_path)
        wizard._save_credential("TEST_KEY", "test_value")

        env_path = tmp_path / ".env"
        assert env_path.exists()
        content = env_path.read_text()
        assert "TEST_KEY=test_value" in content

    def test_updates_existing_env_var(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("# comment\nTEST_KEY=old_value\nOTHER=keep\n")

        wizard = SetupWizard(root=tmp_path)
        wizard._save_credential("TEST_KEY", "new_value")

        content = env_path.read_text()
        assert "TEST_KEY=new_value" in content
        assert "old_value" not in content
        assert "OTHER=keep" in content
        assert "# comment" in content

    def test_appends_new_env_var(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("EXISTING=value\n")

        wizard = SetupWizard(root=tmp_path)
        wizard._save_credential("NEW_KEY", "new_value")

        content = env_path.read_text()
        assert "EXISTING=value" in content
        assert "NEW_KEY=new_value" in content


class TestWizardStatus:
    def test_show_status(self, tmp_path, capsys):
        wizard = SetupWizard(root=tmp_path)
        wizard.show_status()
        out = capsys.readouterr().out
        assert "Configuration Status" in out


class TestWizardFix:
    def test_fix_unknown_connection(self, tmp_path, capsys):
        wizard = SetupWizard(root=tmp_path)
        wizard.fix("nonexistent_thing")
        out = capsys.readouterr().out
        assert "Unknown connection" in out

    def test_fix_known_connection(self, tmp_path, monkeypatch, capsys):
        wizard = SetupWizard(root=tmp_path)
        # Skip the credential setup
        monkeypatch.setattr(
            "tools.agents.setup.renderer.prompt_yn",
            lambda q, default=True: False,
        )
        wizard.fix("GITLAB_TOKEN")
        out = capsys.readouterr().out
        assert "GitLab access key" in out


class TestCrossPlatformAlias:
    """Tests that shell alias works on zsh, bash, and Windows PowerShell."""

    def test_zsh_alias(self, tmp_path, monkeypatch, capsys):
        """On macOS/Linux with zsh, writes alias to ~/.zshrc."""
        monkeypatch.setenv("SHELL", "/bin/zsh")
        zshrc = tmp_path / ".zshrc"
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        wizard = SetupWizard(root=tmp_path)
        with patch("shutil.which", return_value=None):
            wizard._offer_shell_alias()

        assert zshrc.exists()
        content = zshrc.read_text()
        assert "alias neut=" in content
        assert "neut.py" in content
        out = capsys.readouterr().out
        assert "source ~/.zshrc" in out

    def test_bash_alias(self, tmp_path, monkeypatch, capsys):
        """On Linux with bash, writes alias to ~/.bashrc."""
        monkeypatch.setenv("SHELL", "/bin/bash")
        bashrc = tmp_path / ".bashrc"
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        wizard = SetupWizard(root=tmp_path)
        with patch("shutil.which", return_value=None):
            wizard._offer_shell_alias()

        assert bashrc.exists()
        content = bashrc.read_text()
        assert "alias neut=" in content
        out = capsys.readouterr().out
        assert "source ~/.bashrc" in out

    def test_zsh_no_duplicate(self, tmp_path, monkeypatch):
        """Doesn't duplicate alias if already present."""
        monkeypatch.setenv("SHELL", "/bin/zsh")
        zshrc = tmp_path / ".zshrc"
        zshrc.write_text('alias neut="python /old/path/neut.py"\n')
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        wizard = SetupWizard(root=tmp_path)
        with patch("shutil.which", return_value=None):
            wizard._offer_shell_alias()

        content = zshrc.read_text()
        assert content.count("alias neut=") == 1

    def test_unknown_shell_skips(self, tmp_path, monkeypatch, capsys):
        """Unknown shell (e.g., fish, csh) — skips without error."""
        monkeypatch.setenv("SHELL", "/usr/bin/fish")
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        wizard = SetupWizard(root=tmp_path)
        with patch("shutil.which", return_value=None):
            with patch("tools.agents.setup.wizard.platform") as mock_plat:
                mock_plat.system.return_value = "Linux"
                wizard._offer_shell_alias()

        out = capsys.readouterr().out
        assert "neut" not in out  # No alias message

    def test_no_shell_env_var_skips(self, tmp_path, monkeypatch, capsys):
        """Windows doesn't set SHELL — should skip Unix alias silently."""
        monkeypatch.delenv("SHELL", raising=False)
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        wizard = SetupWizard(root=tmp_path)
        with patch("shutil.which", return_value=None):
            with patch("tools.agents.setup.wizard.platform") as mock_plat:
                mock_plat.system.return_value = "Linux"
                wizard._offer_shell_alias()

        out = capsys.readouterr().out
        assert "neut" not in out

    def test_windows_powershell_alias(self, tmp_path, monkeypatch, capsys):
        """On Windows, creates a function in the PowerShell profile."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        ps_profile = tmp_path / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1"

        wizard = SetupWizard(root=tmp_path)
        with patch("shutil.which", return_value=None):
            with patch("tools.agents.setup.wizard.platform") as mock_plat:
                mock_plat.system.return_value = "Windows"
                # Mock powershell command that returns profile path
                mock_result = MagicMock()
                mock_result.stdout = str(ps_profile)
                with patch("subprocess.run", return_value=mock_result):
                    wizard._offer_shell_alias()

        assert ps_profile.exists()
        content = ps_profile.read_text()
        assert "function neut" in content
        out = capsys.readouterr().out
        assert "PowerShell" in out

    def test_windows_powershell_no_duplicate(self, tmp_path, monkeypatch):
        """Doesn't duplicate PowerShell function if already present."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        ps_profile = tmp_path / "ps_profile.ps1"
        ps_profile.write_text('function neut { python "old/neut.py" @args }\n')

        wizard = SetupWizard(root=tmp_path)
        with patch("shutil.which", return_value=None):
            with patch("tools.agents.setup.wizard.platform") as mock_plat:
                mock_plat.system.return_value = "Windows"
                mock_result = MagicMock()
                mock_result.stdout = str(ps_profile)
                with patch("subprocess.run", return_value=mock_result):
                    wizard._offer_shell_alias()

        content = ps_profile.read_text()
        assert content.count("function neut") == 1

    def test_windows_no_powershell_skips(self, tmp_path, monkeypatch, capsys):
        """Windows without PowerShell available — skips gracefully."""
        wizard = SetupWizard(root=tmp_path)
        with patch("shutil.which", return_value=None):
            with patch("tools.agents.setup.wizard.platform") as mock_plat:
                mock_plat.system.return_value = "Windows"
                with patch("subprocess.run", side_effect=FileNotFoundError):
                    wizard._offer_shell_alias()

        out = capsys.readouterr().out
        assert "neut" not in out


class TestCrossPlatformSummary:
    """Tests that summary displays correctly for different OS platforms."""

    def test_summary_linux(self, tmp_path, capsys):
        from tools.agents.setup.probe import ProbeResult
        wizard = SetupWizard(root=tmp_path)
        wizard.probe_result = ProbeResult(
            os_name="Linux",
            os_version="6.1.0-generic",
            python_version="3.11.0",
            is_git_repo=True,
            git_branch="main",
            dns_available=True,
            dependencies=[],
            env_vars_set={},
        )
        wizard.state.probe_result = wizard.probe_result.to_dict()
        wizard._phase_summary()
        out = capsys.readouterr().out
        assert "Linux 6.1.0-generic" in out
        assert "Darwin" not in out

    def test_summary_windows(self, tmp_path, capsys):
        from tools.agents.setup.probe import ProbeResult
        wizard = SetupWizard(root=tmp_path)
        wizard.probe_result = ProbeResult(
            os_name="Windows",
            os_version="10",
            python_version="3.11.0",
            is_git_repo=True,
            git_branch="main",
            dns_available=True,
            dependencies=[],
            env_vars_set={},
        )
        wizard.state.probe_result = wizard.probe_result.to_dict()
        wizard._phase_summary()
        out = capsys.readouterr().out
        assert "Windows 10" in out

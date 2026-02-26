"""Tests for the bootstrap script functionality.

Tests validate the bootstrap.sh script behavior through Python equivalents
and integration tests where possible.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BOOTSTRAP_SCRIPT = REPO_ROOT / "scripts" / "bootstrap.sh"


class TestBootstrapScript:
    """Tests for scripts/bootstrap.sh."""

    def test_bootstrap_script_exists(self):
        """Bootstrap script exists and is executable."""
        assert BOOTSTRAP_SCRIPT.exists()
        assert os.access(BOOTSTRAP_SCRIPT, os.X_OK)

    def test_bootstrap_script_shebang(self):
        """Bootstrap script has proper shebang."""
        content = BOOTSTRAP_SCRIPT.read_text()
        assert content.startswith("#!/usr/bin/env bash")

    def test_bootstrap_script_has_help(self):
        """Bootstrap script supports --help."""
        result = subprocess.run(
            ["bash", str(BOOTSTRAP_SCRIPT), "--help"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        assert "--full" in result.stdout
        assert "direnv" in result.stdout.lower()

    def test_bootstrap_script_set_flags(self):
        """Bootstrap script uses safe bash options."""
        content = BOOTSTRAP_SCRIPT.read_text()
        assert "set -e" in content or "set -euo pipefail" in content

    def test_bootstrap_defines_project_root(self):
        """Bootstrap script correctly determines project root."""
        content = BOOTSTRAP_SCRIPT.read_text()
        assert "PROJECT_ROOT" in content
        assert "SCRIPT_DIR" in content

    def test_bootstrap_creates_venv(self):
        """Bootstrap script creates venv if missing."""
        content = BOOTSTRAP_SCRIPT.read_text()
        assert "python3 -m venv" in content
        assert "VENV_PATH" in content

    def test_bootstrap_installs_package(self):
        """Bootstrap script installs the package in editable mode."""
        content = BOOTSTRAP_SCRIPT.read_text()
        assert "pip install" in content
        assert "-e" in content

    def test_bootstrap_handles_direnv(self):
        """Bootstrap script handles direnv setup."""
        content = BOOTSTRAP_SCRIPT.read_text()
        assert "direnv" in content
        assert "direnv allow" in content


class TestEnvrcFile:
    """Tests for the .envrc direnv configuration."""

    @pytest.fixture
    def envrc_path(self):
        return REPO_ROOT / ".envrc"

    def test_envrc_exists(self, envrc_path):
        """The .envrc file exists."""
        assert envrc_path.exists()

    def test_envrc_sources_venv(self, envrc_path):
        """The .envrc sources the virtual environment."""
        content = envrc_path.read_text()
        assert "source" in content
        assert ".venv/bin/activate" in content

    def test_envrc_auto_installs(self, envrc_path):
        """The .envrc auto-installs package if missing."""
        content = envrc_path.read_text()
        assert "pip install" in content
        assert "neut" in content

    def test_envrc_loads_env(self, envrc_path):
        """The .envrc loads .env file if present."""
        content = envrc_path.read_text()
        assert "dotenv" in content or ".env" in content


class TestProjectStructure:
    """Tests for expected project structure."""

    def test_pyproject_toml_exists(self):
        """pyproject.toml exists with correct structure."""
        pyproject = REPO_ROOT / "pyproject.toml"
        assert pyproject.exists()

        content = pyproject.read_text()
        assert "[project]" in content
        assert 'name = "neutron-os"' in content
        assert "[project.scripts]" in content
        assert "neut" in content

    def test_neut_cli_entry_point(self):
        """neut CLI entry point is correctly configured."""
        pyproject = REPO_ROOT / "pyproject.toml"
        content = pyproject.read_text()
        assert 'neut = "tools.neut_cli:main"' in content

    def test_tools_directory_structure(self):
        """Required tools directories exist."""
        tools_dir = REPO_ROOT / "tools"
        assert tools_dir.exists()
        assert (tools_dir / "neut_cli.py").exists()
        assert (tools_dir / "docflow").is_dir()
        assert (tools_dir / "agents").is_dir()

    def test_claude_md_exists(self):
        """CLAUDE.md documentation exists."""
        claude_md = REPO_ROOT / "CLAUDE.md"
        assert claude_md.exists()

        content = claude_md.read_text()
        assert "bootstrap" in content.lower()
        assert "neut" in content


class TestDevelopmentSetup:
    """Integration tests for development setup workflow."""

    @pytest.mark.slow
    def test_neut_command_available(self):
        """The neut command is available after setup."""
        # This tests the actual installed command
        venv_neut = REPO_ROOT.parent / ".venv" / "bin" / "neut"

        if venv_neut.exists():
            result = subprocess.run(
                [str(venv_neut), "--help"],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0
            assert "sense" in result.stdout
            assert "doc" in result.stdout
        else:
            pytest.skip("venv not set up")

    @pytest.mark.slow
    def test_neut_sense_status(self):
        """neut sense status runs successfully."""
        venv_python = REPO_ROOT.parent / ".venv" / "bin" / "python"

        if venv_python.exists():
            result = subprocess.run(
                [str(venv_python), "-m", "tools.agents.sense.cli", "status"],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            assert result.returncode == 0
        else:
            pytest.skip("venv not set up")

    @pytest.mark.slow
    def test_neut_doc_providers(self):
        """neut doc providers runs successfully."""
        venv_python = REPO_ROOT.parent / ".venv" / "bin" / "python"

        if venv_python.exists():
            result = subprocess.run(
                [str(venv_python), str(REPO_ROOT / "tools" / "neut_cli.py"), "doc", "providers"],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            assert result.returncode == 0
            assert "Generation" in result.stdout
        else:
            pytest.skip("venv not set up")

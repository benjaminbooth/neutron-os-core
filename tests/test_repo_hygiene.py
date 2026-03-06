"""Repo structure hygiene checks.

Catches common mistakes that agents and humans make during refactoring:
- Stale imports referencing old package names
- Test files in the wrong directory (extension tests should be colocated)
- Files that belong in runtime/ placed under src/
- Agent extensions missing the _agent suffix
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _py_files(*dirs: str):
    """Yield all .py files under the given dirs (relative to repo root)."""
    for d in dirs:
        yield from (REPO_ROOT / d).rglob("*.py")


class TestNoStaleImports:
    """Ensure no Python files reference the old 'tools.' package name."""

    @pytest.mark.parametrize("search_dir", ["src", "tests"])
    def test_no_tools_dot_imports(self, search_dir):
        stale = []
        for py in _py_files(search_dir):
            if "__pycache__" in str(py) or py.name == "test_repo_hygiene.py":
                continue
            text = py.read_text(errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "from tools." in stripped or "import tools." in stripped:
                    stale.append(f"{py.relative_to(REPO_ROOT)}:{i}: {stripped}")
        assert stale == [], "Stale 'tools.' imports found:\n" + "\n".join(stale)


class TestExtensionTestsColocated:
    """Extension-specific tests should live in the extension's tests/ dir."""

    EXTENSION_NAMES = [
        "sense_agent", "chat_agent", "mo_agent", "doctor_agent",
        "docflow", "db", "demo", "status", "test", "update",
        "repo", "cost_estimation",
    ]

    def test_no_extension_test_dirs_in_root_tests(self):
        """Root tests/ should not have dirs named after extensions."""
        root_tests = REPO_ROOT / "tests"
        violations = []
        for name in self.EXTENSION_NAMES:
            # Strip _agent suffix for checking — e.g. "sense" shouldn't be in tests/
            short = name.replace("_agent", "")
            candidate = root_tests / short
            if candidate.is_dir():
                violations.append(str(candidate.relative_to(REPO_ROOT)))
        assert violations == [], (
            "Extension tests should be colocated:\n"
            + "\n".join(f"  {v} → src/neutron_os/extensions/builtins/{v.split('/')[-1]}/tests/" for v in violations)
        )


class TestAgentExtensionNaming:
    """Agent-kind extensions must have directory names ending with _agent."""

    def test_agent_dirs_have_suffix(self):
        builtins = REPO_ROOT / "src" / "neutron_os" / "extensions" / "builtins"
        violations = []
        for manifest in builtins.glob("*/neut-extension.toml"):
            text = manifest.read_text()
            if 'kind = "agent"' in text:
                dir_name = manifest.parent.name
                if not dir_name.endswith("_agent"):
                    violations.append(dir_name)
        assert violations == [], (
            f"Agent extensions must end with '_agent': {violations}"
        )


class TestNoRuntimeDataInSrc:
    """Runtime data (config, inbox, sessions) must be in runtime/, not src/."""

    RUNTIME_DIRS = ["config", "inbox", "sessions", "drafts", "approved"]

    def test_no_runtime_dirs_in_src_neutron_os(self):
        src = REPO_ROOT / "src" / "neutron_os"
        violations = []
        for name in self.RUNTIME_DIRS:
            candidate = src / name
            if candidate.is_dir():
                violations.append(str(candidate.relative_to(REPO_ROOT)))
        assert violations == [], (
            "Runtime data dirs found in src/neutron_os/ (should be in runtime/):\n"
            + "\n".join(f"  {v}" for v in violations)
        )

    def test_src_only_contains_package(self):
        """src/ should only contain the neutron_os package — no stray dirs."""
        src = REPO_ROOT / "src"
        allowed = {"neutron_os"}
        violations = []
        for item in src.iterdir():
            if item.is_dir() and item.name not in allowed and item.name != "__pycache__":
                violations.append(item.name)
        assert violations == [], (
            f"Unexpected directories in src/: {violations}\n"
            "Runtime data belongs in runtime/, not src/"
        )


class TestPRDIntegrity:
    """Key PRDs must not be truncated or have formatting stripped.

    AI agents doing bulk search-replace can accidentally damage markdown files.
    This catches it before commit.
    """

    # Minimum line counts for key PRDs (set well below actual to catch truncation)
    PRD_MINIMUMS = {
        "prd_neutron-os-executive.md": 500,
        "prd_reactor-ops-log.md": 200,
        "prd_experiment-manager.md": 500,
        "prd_data-platform.md": 300,
        "prd_compliance-tracking.md": 300,
        "prd_neut-cli.md": 300,
        "prd_medical-isotope.md": 300,
    }

    def test_prd_not_truncated(self):
        reqs = REPO_ROOT / "docs" / "requirements"
        violations = []
        for name, min_lines in self.PRD_MINIMUMS.items():
            f = reqs / name
            if not f.exists():
                violations.append(f"{name}: MISSING")
                continue
            lines = len(f.read_text().splitlines())
            if lines < min_lines:
                violations.append(f"{name}: {lines} lines (minimum {min_lines})")
        assert violations == [], (
            "PRD integrity check failed — possible truncation:\n"
            + "\n".join(f"  {v}" for v in violations)
        )

    def test_executive_prd_has_mermaid(self):
        """Executive PRD must retain its mermaid diagrams."""
        f = REPO_ROOT / "docs" / "requirements" / "prd_neutron-os-executive.md"
        text = f.read_text()
        mermaid_count = text.count("```mermaid")
        assert mermaid_count >= 5, (
            f"Executive PRD has only {mermaid_count} mermaid blocks (expected >=5). "
            "Formatting may have been stripped."
        )


class TestRootDirPolicy:
    """Only approved directories should exist at repo root."""

    ALLOWED_ROOT_DIRS = {
        "src", "tests", "docs", "infra", "scripts", "data",
        "runtime", "archive", "spikes",
        # Hidden dirs
        ".git", ".github", ".claude", ".claude.example",
        ".venv", ".neut", ".pytest_cache", ".vscode",
        # Personal / CI (gitignored)
        "ben-learning", "dist", "__pycache__", ".pip-cache", ".ruff_cache",
    }

    def test_no_unexpected_root_dirs(self):
        violations = []
        for item in REPO_ROOT.iterdir():
            if item.is_dir() and item.name not in self.ALLOWED_ROOT_DIRS:
                violations.append(item.name)
        assert violations == [], (
            f"Unexpected root directories: {violations}\n"
            "New functionality should be an extension in src/neutron_os/extensions/builtins/"
        )

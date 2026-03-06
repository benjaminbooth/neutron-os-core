"""Tests for builtin extension discovery and dispatch.

Covers the fragile paths introduced by the dogfooding refactor:
- Builtin discovery via __file__-relative path
- Project extension discovery via cwd walk (not __file__)
- NEUT_ROOT env var override
- Graceful skip when no .neut/ directory exists
- Builtin vs user dispatch (importlib.import_module vs spec_from_file_location)
- cli_registry dynamic lookup from extensions
- neut ext list showing [builtin] vs [user] tags
"""

import importlib
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock


from neutron_os.extensions.contracts import (
    CLICommandDef,
    Extension,
    parse_manifest,
    validate_extension,
)
from neutron_os.extensions.discovery import (
    _builtin_extensions_dir,
    _project_extensions_dir,
    discover_cli_commands,
    discover_extensions,
    get_extension_dirs,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
NEUT_CLI = str(REPO_ROOT / "src" / "neutron_os" / "neut_cli.py")


# ---------------------------------------------------------------------------
# Builtin directory resolution
# ---------------------------------------------------------------------------


class TestBuiltinExtensionsDir:
    def test_returns_builtins_subdir_of_extensions(self):
        d = _builtin_extensions_dir()
        assert d.name == "builtins"
        assert d.parent.name == "extensions"

    def test_path_is_absolute(self):
        assert _builtin_extensions_dir().is_absolute()

    def test_dir_exists(self):
        assert _builtin_extensions_dir().is_dir()

    def test_relative_to_file_not_cwd(self):
        """Builtins resolve from __file__, not cwd — works after pip install."""
        d = _builtin_extensions_dir()
        # Should be inside the neutron_os package, not relative to cwd
        assert "neutron_os" in str(d) and "extensions" in str(d)


# ---------------------------------------------------------------------------
# Project extensions via cwd walk
# ---------------------------------------------------------------------------


class TestProjectExtensionsDir:
    def test_returns_none_in_clean_dir(self, tmp_path):
        """No .neut/ anywhere → None, no crash."""
        with mock.patch("neutron_os.extensions.discovery.Path.cwd", return_value=tmp_path):
            result = _project_extensions_dir()
        assert result is None

    def test_finds_neut_dir_in_parent(self, tmp_path):
        """Walks up from cwd to find .neut/extensions/."""
        project = tmp_path / "my-project"
        ext_dir = project / ".neut" / "extensions"
        ext_dir.mkdir(parents=True)
        child = project / "src" / "deep" / "nested"
        child.mkdir(parents=True)

        with mock.patch("neutron_os.extensions.discovery.Path.cwd", return_value=child):
            result = _project_extensions_dir()
        assert result == ext_dir

    def test_neut_root_env_override(self, tmp_path):
        """NEUT_ROOT env var takes precedence over cwd walk."""
        project = tmp_path / "explicit-root"
        ext_dir = project / ".neut" / "extensions"
        ext_dir.mkdir(parents=True)

        with mock.patch.dict(os.environ, {"NEUT_ROOT": str(project)}):
            result = _project_extensions_dir()
        assert result == ext_dir

    def test_neut_root_env_missing_dir(self, tmp_path):
        """NEUT_ROOT set but no .neut/extensions/ → None."""
        project = tmp_path / "empty-root"
        project.mkdir()

        with mock.patch.dict(os.environ, {"NEUT_ROOT": str(project)}):
            result = _project_extensions_dir()
        assert result is None


# ---------------------------------------------------------------------------
# get_extension_dirs ordering
# ---------------------------------------------------------------------------


class TestGetExtensionDirs:
    def test_builtins_always_included(self):
        dirs = get_extension_dirs()
        assert any(d.name == "builtins" for d in dirs)

    def test_builtins_last(self):
        """Builtins are lowest precedence (last in list)."""
        dirs = get_extension_dirs()
        assert dirs[-1].name == "builtins"

    def test_project_dir_before_builtins(self, tmp_path):
        project = tmp_path / "proj"
        ext_dir = project / ".neut" / "extensions"
        ext_dir.mkdir(parents=True)

        with mock.patch("neutron_os.extensions.discovery.Path.cwd", return_value=project):
            dirs = get_extension_dirs()
        assert dirs[0] == ext_dir
        assert dirs[-1].name == "builtins"


# ---------------------------------------------------------------------------
# Builtin manifest parsing
# ---------------------------------------------------------------------------


class TestBuiltinManifests:
    def test_all_builtins_have_manifests(self):
        builtins_dir = _builtin_extensions_dir()
        for child in builtins_dir.iterdir():
            if child.is_dir() and child.name != "__pycache__":
                manifest = child / "neut-extension.toml"
                assert manifest.exists(), f"Missing manifest: {child.name}"

    def test_all_builtins_parse_successfully(self):
        builtins_dir = _builtin_extensions_dir()
        for child in sorted(builtins_dir.iterdir()):
            if not child.is_dir() or child.name.startswith("_"):
                continue
            manifest = child / "neut-extension.toml"
            if not manifest.exists():
                continue
            ext = parse_manifest(manifest)
            assert ext.name, f"No name in {child.name}"
            assert ext.builtin is True, f"{child.name} should be builtin=true"

    def test_all_builtins_have_importable_cli_modules(self):
        builtins_dir = _builtin_extensions_dir()
        for child in sorted(builtins_dir.iterdir()):
            if not child.is_dir() or child.name.startswith("_"):
                continue
            manifest = child / "neut-extension.toml"
            if not manifest.exists():
                continue
            ext = parse_manifest(manifest)
            for cmd in ext.cli_commands:
                spec = importlib.util.find_spec(cmd.module)
                assert spec is not None, (
                    f"Builtin {ext.name}: CLI module {cmd.module} not importable"
                )

    def test_builtin_count(self):
        """Sanity: we expect 12 builtins (infra is a core SUBCOMMAND, not an extension)."""
        builtins_dir = _builtin_extensions_dir()
        manifests = list(builtins_dir.glob("*/neut-extension.toml"))
        assert len(manifests) == 12


# ---------------------------------------------------------------------------
# Builtin validation (importability, not file paths)
# ---------------------------------------------------------------------------


class TestBuiltinValidation:
    def test_builtin_validates_importability(self):
        ext = Extension(
            name="test-builtin",
            version="0.1.0",
            description="test",
            author="test",
            root=_builtin_extensions_dir() / "sense_agent",
            builtin=True,
            cli_commands=[CLICommandDef(noun="sense", module="neutron_os.extensions.builtins.sense_agent.cli")],
        )
        issues = validate_extension(ext)
        assert issues == []

    def test_builtin_bad_module_fails(self):
        ext = Extension(
            name="test-builtin-bad",
            version="0.1.0",
            description="test",
            author="test",
            root=_builtin_extensions_dir() / "sense_agent",
            builtin=True,
            cli_commands=[CLICommandDef(noun="x", module="neutron_os.nonexistent.module")],
        )
        issues = validate_extension(ext)
        assert any("not importable" in i for i in issues)

    def test_user_extension_skips_importability_check(self, tmp_path):
        """User extensions check file paths, NOT importability."""
        d = tmp_path / "user-ext"
        d.mkdir()
        (d / "neut-extension.toml").write_text(
            '[extension]\nname = "user-ext"\n'
        )
        (d / "cli").mkdir()
        (d / "cli" / "myverb.py").write_text("def main(): pass")

        ext = Extension(
            name="user-ext",
            version="0.1.0",
            description="",
            author="",
            root=d,
            builtin=False,
            cli_commands=[CLICommandDef(noun="myverb", module="cli.myverb")],
        )
        issues = validate_extension(ext)
        assert issues == []


# ---------------------------------------------------------------------------
# discover_cli_commands includes builtin flag
# ---------------------------------------------------------------------------


class TestDiscoverCLICommandsBuiltinFlag:
    def test_builtins_have_flag(self):
        cmds = discover_cli_commands()
        assert len(cmds) > 0
        for noun, info in cmds.items():
            assert "builtin" in info, f"Command {noun} missing builtin flag"

    def test_sense_is_builtin(self):
        cmds = discover_cli_commands()
        assert "sense" in cmds
        assert cmds["sense"]["builtin"] is True

    def test_user_ext_not_builtin(self, tmp_path):
        """User extension commands have builtin=False."""
        from neutron_os.extensions.scaffold import scaffold_extension

        scaffold_extension("user-test", base_dir=tmp_path)
        cmds = discover_cli_commands(tmp_path)
        # scaffold adds a "logs" command
        if "logs" in cmds:
            assert cmds["logs"]["builtin"] is False


# ---------------------------------------------------------------------------
# CLI dispatch (subprocess, tests the real entry point)
# ---------------------------------------------------------------------------


def _run_neut(*args: str, timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, NEUT_CLI, *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=timeout,
    )


class TestCLIDispatch:
    def test_builtin_sense_status(self):
        result = _run_neut("sense", "status")
        assert result.returncode == 0
        assert "Inbox" in result.stdout or "sense" in result.stdout.lower()

    def test_builtin_status_json(self):
        result = _run_neut("status", "--json")
        assert result.returncode == 0
        assert '"overall"' in result.stdout

    def test_builtin_test_help(self):
        result = _run_neut("test", "--help")
        assert result.returncode == 0
        assert "test" in result.stdout.lower()

    def test_builtin_db_help(self):
        result = _run_neut("db", "--help")
        assert result.returncode == 0
        assert "PostgreSQL" in result.stdout or "db" in result.stdout.lower()

    def test_ext_list_shows_builtin_tag(self):
        result = _run_neut("ext")
        assert result.returncode == 0
        assert "[builtin]" in result.stdout

    def test_ext_list_shows_builtin_count(self):
        result = _run_neut("ext")
        assert result.returncode == 0
        assert "12 builtin" in result.stdout

    def test_help_all_shows_builtins_section(self):
        result = _run_neut("--help-all")
        assert result.returncode == 0
        assert "Builtins" in result.stdout or "builtin" in result.stdout.lower()

    def test_unknown_command_still_suggests(self):
        result = _run_neut("senss")  # typo
        assert result.returncode != 0
        assert "sense" in result.stdout.lower() or "did you mean" in result.stdout.lower()


# ---------------------------------------------------------------------------
# cli_registry sees extensions
# ---------------------------------------------------------------------------


class TestCLIRegistryIntegration:
    def test_registry_includes_builtins(self):
        from neutron_os.cli_registry import _get_cli_modules

        modules = _get_cli_modules()
        assert "sense" in modules
        assert "db" in modules
        assert "config" in modules  # core, always present

    def test_registry_core_plus_extensions(self):
        from neutron_os.cli_registry import _get_cli_modules

        modules = _get_cli_modules()
        # Should have at least core (config, ext) + 10 builtins
        assert len(modules) >= 12


# ---------------------------------------------------------------------------
# User can override a builtin
# ---------------------------------------------------------------------------


class TestUserOverridesBuiltin:
    def test_user_ext_overrides_builtin_by_name(self, tmp_path):
        """User extension with same noun as builtin wins (higher precedence)."""
        user_dir = tmp_path / "user-exts" / "sense"
        user_dir.mkdir(parents=True)
        (user_dir / "neut-extension.toml").write_text(
            """\
[extension]
name = "sense"
version = "99.0.0"
description = "User override of sense"
[[cli.commands]]
noun = "sense"
module = "my_sense"
description = "Custom sense"
"""
        )
        (user_dir / "my_sense.py").write_text("def main(): pass")

        # User dir first, builtins last
        builtins = _builtin_extensions_dir()
        exts = discover_extensions(tmp_path / "user-exts", builtins)

        sense_exts = [e for e in exts if e.name == "sense"]
        assert len(sense_exts) == 1
        assert sense_exts[0].version == "99.0.0"  # user version wins

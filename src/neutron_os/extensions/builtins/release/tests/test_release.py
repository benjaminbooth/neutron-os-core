"""Tests for neut release."""

from neutron_os.extensions.builtins.release.cli import ReleaseManager


class TestBump:
    def test_patch(self):
        assert ReleaseManager.bump("0.4.1", "patch") == "0.4.2"

    def test_minor(self):
        assert ReleaseManager.bump("0.4.1", "minor") == "0.5.0"

    def test_major(self):
        assert ReleaseManager.bump("0.4.1", "major") == "1.0.0"

    def test_from_zero(self):
        assert ReleaseManager.bump("0.0.0", "patch") == "0.0.1"

    def test_major_resets(self):
        assert ReleaseManager.bump("1.3.7", "major") == "2.0.0"

    def test_minor_resets_patch(self):
        assert ReleaseManager.bump("1.3.7", "minor") == "1.4.0"


class TestChangelog:
    def test_categorizes_commits(self):
        mgr = ReleaseManager.__new__(ReleaseManager)
        # Simulate commits_since
        commits = [
            "abc1234 feat: add new feature",
            "def5678 fix: resolve bug",
            "ghi9012 refactor: clean up code",
            "jkl3456 docs: update readme",
            "mno7890 bump: v0.4.0",
            "pqr1234 random change",
        ]
        mgr.commits_since = lambda tag: commits  # type: ignore[method-assign]
        changelog = mgr.build_changelog("v0.3.0")

        assert len(changelog["features"]) == 1
        assert len(changelog["fixes"]) == 1
        assert len(changelog["improvements"]) == 2
        assert len(changelog["other"]) == 1
        assert "bump" not in str(changelog)


class TestCurrentVersion:
    def test_reads_version(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('version = "1.2.3"\n')
        mgr = ReleaseManager.__new__(ReleaseManager)
        mgr.pyproject = pyproject
        assert mgr.current_version() == "1.2.3"

    def test_writes_version(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "1.2.3"\n')
        mgr = ReleaseManager.__new__(ReleaseManager)
        mgr.pyproject = pyproject
        mgr.write_version("1.3.0")
        assert 'version = "1.3.0"' in pyproject.read_text()


class TestCLI:
    def test_status_runs(self):
        from neutron_os.extensions.builtins.release.cli import main
        rc = main(["--status"])
        assert rc == 0

    def test_changelog_runs(self):
        from neutron_os.extensions.builtins.release.cli import main
        rc = main(["--changelog"])
        assert rc == 0

    def test_no_args_shows_help(self, capsys):
        from neutron_os.extensions.builtins.release.cli import main
        rc = main([])
        assert rc == 1

    def test_dry_run(self):
        from neutron_os.extensions.builtins.release.cli import main
        rc = main(["patch", "--dry-run"])
        # May return 0 (clean tree) or 1 (dirty tree) — both are valid
        assert rc in (0, 1)

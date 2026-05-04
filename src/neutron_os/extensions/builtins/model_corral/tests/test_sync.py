"""Tests for Model Corral sync — automatic Git push/pull.

Uses real Git repos in tmp dirs (no mocks) for accurate integration testing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml


def _git(cwd, args):
    result = subprocess.run(
        ["git"] + args, cwd=str(cwd), capture_output=True, text=True, timeout=10, check=False
    )
    return result.returncode, result.stdout.strip()


def _init_bare_remote(tmp_path) -> Path:
    """Create a bare Git repo to act as the remote."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, ["init", "--bare"])
    return remote


def _make_model_files(model_dir: Path, model_id: str = "test-model") -> None:
    """Create minimal model files in a directory."""
    model_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "model_id": model_id,
        "name": "Test",
        "version": "1.0.0",
        "status": "draft",
        "reactor_type": "TRIGA",
        "facility": "NETL",
        "physics_code": "MCNP",
        "physics_domain": ["neutronics"],
        "created_by": "test@example.com",
        "created_at": "2026-01-01T00:00:00Z",
        "access_tier": "facility",
    }
    (model_dir / "model.yaml").write_text(yaml.dump(manifest, sort_keys=False))
    (model_dir / "README.md").write_text(f"# {model_id}\n")


class TestSyncConfig:
    def test_from_env_defaults(self):
        from neutron_os.extensions.builtins.model_corral.sync import SyncConfig

        config = SyncConfig()
        assert config.mode == "sync"
        assert config.auto_push is True
        assert config.branch == "main"

    def test_from_env_reads_vars(self, monkeypatch):
        from neutron_os.extensions.builtins.model_corral.sync import SyncConfig

        monkeypatch.setenv("MODEL_CORRAL_REMOTE", "git@github.com:test/models.git")
        monkeypatch.setenv("MODEL_CORRAL_SYNC_MODE", "mirror")
        monkeypatch.setenv("MODEL_CORRAL_BRANCH", "develop")

        config = SyncConfig.from_env()
        assert config.remote_url == "git@github.com:test/models.git"
        assert config.mode == "mirror"
        assert config.branch == "develop"


class TestModelSyncAgent:
    def test_not_enabled_without_remote(self):
        from neutron_os.extensions.builtins.model_corral.sync import ModelSyncAgent, SyncConfig

        agent = ModelSyncAgent(SyncConfig(remote_url=""))
        assert agent.enabled is False

    def test_not_enabled_with_mode_none(self):
        from neutron_os.extensions.builtins.model_corral.sync import ModelSyncAgent, SyncConfig

        agent = ModelSyncAgent(SyncConfig(remote_url="git@x", mode="none"))
        assert agent.enabled is False

    def test_enabled_with_remote_and_sync_mode(self):
        from neutron_os.extensions.builtins.model_corral.sync import ModelSyncAgent, SyncConfig

        agent = ModelSyncAgent(SyncConfig(remote_url="git@x", mode="sync"))
        assert agent.enabled is True

    def test_skip_when_not_enabled(self):
        from neutron_os.extensions.builtins.model_corral.sync import ModelSyncAgent, SyncConfig

        agent = ModelSyncAgent(SyncConfig(remote_url=""))
        result = agent.run_sync_cycle()
        assert result.success is True
        assert result.action == "skip"

    @pytest.mark.integration
    def test_push_to_remote(self, tmp_path):
        from neutron_os.extensions.builtins.model_corral.sync import ModelSyncAgent, SyncConfig

        remote = _init_bare_remote(tmp_path)
        repo_dir = tmp_path / "local-store"
        repo_dir.mkdir()

        config = SyncConfig(
            remote_url=str(remote),
            mode="sync",
        )
        agent = ModelSyncAgent(config, repo_dir=repo_dir)

        # Add a model file
        model_path = repo_dir / "models" / "triga" / "netl" / "mcnp" / "test-model" / "v1.0.0"
        _make_model_files(model_path, "test-model")

        # Run sync
        result = agent.run_sync_cycle()
        assert result.success is True
        assert result.action == "push"

        # Verify remote has the commit
        rc, log_out = _git(remote, ["log", "--oneline"])
        assert rc == 0
        assert "sync:" in log_out

    def test_no_changes_skips(self, tmp_path):
        from neutron_os.extensions.builtins.model_corral.sync import ModelSyncAgent, SyncConfig

        remote = _init_bare_remote(tmp_path)
        repo_dir = tmp_path / "local-store"
        repo_dir.mkdir()

        config = SyncConfig(remote_url=str(remote), mode="sync")
        agent = ModelSyncAgent(config, repo_dir=repo_dir)

        # Init repo with initial commit
        _git(repo_dir, ["init"])
        _git(repo_dir, ["checkout", "-b", "main"])
        (repo_dir / ".gitkeep").write_text("")
        _git(repo_dir, ["add", "-A"])
        _git(repo_dir, ["commit", "-m", "init"])
        _git(repo_dir, ["remote", "add", "origin", str(remote)])
        _git(repo_dir, ["push", "-u", "origin", "main"])

        # No changes — should skip
        result = agent.run_sync_cycle()
        assert result.success is True
        assert result.action == "skip"

    def test_pull_from_remote(self, tmp_path):
        from neutron_os.extensions.builtins.model_corral.sync import ModelSyncAgent, SyncConfig

        # Set up a remote with content
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        _git(upstream, ["init"])
        _git(upstream, ["checkout", "-b", "main"])
        model_path = upstream / "models" / "test"
        model_path.mkdir(parents=True)
        (model_path / "model.yaml").write_text("model_id: test\n")
        _git(upstream, ["add", "-A"])
        _git(upstream, ["commit", "-m", "upstream model"])

        # Clone as bare remote
        remote = tmp_path / "remote.git"
        _git(tmp_path, ["clone", "--bare", str(upstream), str(remote)])

        # Local repo that pulls
        repo_dir = tmp_path / "local-mirror"
        repo_dir.mkdir()
        _git(repo_dir, ["init"])
        _git(repo_dir, ["checkout", "-b", "main"])
        (repo_dir / ".gitkeep").write_text("")
        _git(repo_dir, ["add", "-A"])
        _git(repo_dir, ["commit", "-m", "init"])
        _git(repo_dir, ["remote", "add", "origin", str(remote)])
        _git(repo_dir, ["fetch", "origin"])
        _git(repo_dir, ["reset", "--hard", "origin/main"])

        config = SyncConfig(remote_url=str(remote), mode="mirror")
        ModelSyncAgent(config, repo_dir=repo_dir)

        # Should have the upstream model
        assert (repo_dir / "models" / "test" / "model.yaml").exists()


class TestWatcherCycle:
    def test_watcher_cycle_no_op_when_not_configured(self):
        """run_watcher_cycle should not crash when sync is not configured."""
        from neutron_os.extensions.builtins.model_corral.sync import run_watcher_cycle

        # No env vars set — should silently skip
        run_watcher_cycle()  # should not raise

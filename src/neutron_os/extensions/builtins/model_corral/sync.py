"""Model Corral sync — event-driven Git push/pull for shared model registries.

Architecture:
- **Primary trigger:** service.add() calls sync_model() immediately — no
  timer delay. The user's workflow is never interrupted.
- **Safety net:** EVE watcher runs every 60s to catch anything missed
  (crash recovery, manual file edits).
- **Sensitivity:** Push first, review async. Mirror Agent scans pushed
  content in the background. If truly sensitive, Mo quarantines
  (revert + notify). The user is never blocked.
- **Commit messages:** Auto-generated from model.yaml metadata.
- **Sharing flow:** Someone shares a model URL/ID → recipient runs
  `neut model pull <id> --open` → cloned to local, opened in IDE,
  ready to fork and re-submit.

Sync modes:
- none:   No sync (standalone NeutronOS)
- sync:   NeutronOS → Git (primary, Git for sharing)
- mirror: Git → NeutronOS (import existing repos)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class SyncConfig:
    """Git sync configuration for Model Corral."""

    remote_url: str = ""
    branch: str = "main"
    mode: str = "sync"  # none | sync | mirror
    auto_push: bool = True

    @classmethod
    def from_env(cls) -> SyncConfig:
        return cls(
            remote_url=os.environ.get("MODEL_CORRAL_REMOTE", ""),
            branch=os.environ.get("MODEL_CORRAL_BRANCH", "main"),
            mode=os.environ.get("MODEL_CORRAL_SYNC_MODE", "sync"),
            auto_push=os.environ.get("MODEL_CORRAL_AUTO_PUSH", "true").lower() == "true",
        )


@dataclass
class SyncResult:
    success: bool
    action: str = ""  # push, pull, skip
    message: str = ""
    commit_message: str = ""
    models_synced: list[str] = field(default_factory=list)
    review_queued: bool = False


class ModelSyncAgent:
    """Event-driven sync between local Model Corral and Git remote."""

    def __init__(self, config: SyncConfig | None = None, repo_dir: Path | None = None):
        self._config = config or SyncConfig.from_env()
        self._repo_dir = repo_dir

    @property
    def enabled(self) -> bool:
        return self._config.mode != "none" and bool(self._config.remote_url)

    # ------------------------------------------------------------------
    # Primary path: called immediately by service.add()
    # ------------------------------------------------------------------

    def sync_model(self, manifest: dict) -> SyncResult:
        """Sync a single model immediately after add. No delay."""
        if not self.enabled:
            return SyncResult(success=True, action="skip", message="Sync not configured")

        repo = self._ensure_repo()
        if repo is None:
            return SyncResult(success=False, message="Could not initialize Git repo")

        if not self._has_changes(repo):
            return SyncResult(success=True, action="skip", message="No changes to sync")

        commit_msg = _build_commit_message(manifest)
        _git(repo, ["add", "-A"])
        _git(repo, ["commit", "-m", commit_msg])

        rc, out = _git(repo, ["push", "origin", self._config.branch])
        if rc != 0:
            return SyncResult(
                success=False,
                action="push",
                message=f"Push failed: {out}",
                commit_message=commit_msg,
            )

        # Queue async sensitivity review (never blocks)
        review_queued = self._queue_review(manifest)

        return SyncResult(
            success=True,
            action="push",
            message=f"Synced {manifest.get('model_id', '?')} v{manifest.get('version', '?')}",
            commit_message=commit_msg,
            models_synced=[manifest.get("model_id", "")],
            review_queued=review_queued,
        )

    # ------------------------------------------------------------------
    # Safety net: called by EVE watcher every 60s
    # ------------------------------------------------------------------

    def run_sync_cycle(self) -> SyncResult:
        """Catch anything missed — crash recovery, manual edits."""
        if not self.enabled:
            return SyncResult(success=True, action="skip", message="Sync not configured")

        if self._config.mode == "mirror":
            return self._pull_from_remote()

        repo = self._ensure_repo()
        if repo is None:
            return SyncResult(success=False, message="Could not initialize Git repo")

        if not self._has_changes(repo):
            return SyncResult(success=True, action="skip", message="No changes")

        _git(repo, ["add", "-A"])
        changed = self._staged_models(repo)
        msg = f"sync: catchup — {len(changed)} model(s)\n\n" + "\n".join(f"- {m}" for m in changed)
        _git(repo, ["commit", "-m", msg])

        rc, out = _git(repo, ["push", "origin", self._config.branch])
        if rc != 0:
            return SyncResult(success=False, action="push", message=f"Push failed: {out}")

        return SyncResult(
            success=True,
            action="push",
            message=f"Catchup: {len(changed)} model(s)",
            models_synced=changed,
        )

    def _pull_from_remote(self) -> SyncResult:
        repo = self._ensure_repo()
        if repo is None:
            return SyncResult(success=False, message="Could not initialize Git repo")

        rc, out = _git(repo, ["pull", "origin", self._config.branch, "--ff-only"])
        if rc != 0:
            return SyncResult(success=False, action="pull", message=f"Pull failed: {out}")
        return SyncResult(success=True, action="pull", message="Pulled latest")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_repo(self) -> Path | None:
        if self._repo_dir is None:
            from axiom.infra.paths import get_user_state_dir

            self._repo_dir = get_user_state_dir() / "model-storage"

        repo = self._repo_dir
        repo.mkdir(parents=True, exist_ok=True)

        if not (repo / ".git").exists():
            _git(repo, ["init"])
            _git(repo, ["checkout", "-b", self._config.branch])

        rc, existing = _git(repo, ["remote", "get-url", "origin"])
        if rc != 0:
            _git(repo, ["remote", "add", "origin", self._config.remote_url])
        elif existing.strip() != self._config.remote_url:
            _git(repo, ["remote", "set-url", "origin", self._config.remote_url])

        return repo

    def _has_changes(self, repo: Path) -> bool:
        rc, out = _git(repo, ["status", "--porcelain"])
        return bool(out.strip())

    def _staged_models(self, repo: Path) -> list[str]:
        rc, out = _git(repo, ["diff", "--cached", "--name-only"])
        if rc != 0:
            return []
        model_ids = set()
        for line in out.strip().splitlines():
            parts = line.split("/")
            if len(parts) >= 5 and parts[0] == "models":
                model_ids.add(parts[4])
        return sorted(model_ids)

    def _queue_review(self, manifest: dict) -> bool:
        """Queue async sensitivity review — never blocks the push.

        Only reviews public-tier models. Facility models skip review.
        Mo picks up the review queue on its heartbeat and runs Mirror
        Agent. If sensitive content found: Mo reverts, notifies owner.
        """
        if manifest.get("access_tier") != "public":
            return False

        try:
            from axiom.infra.paths import get_user_state_dir

            queue_dir = get_user_state_dir() / "review-queue"
            queue_dir.mkdir(parents=True, exist_ok=True)

            entry = {
                "type": "model_sensitivity_review",
                "model_id": manifest.get("model_id"),
                "version": manifest.get("version"),
                "access_tier": "public",
                "timestamp": time.time(),
                "status": "pending",
                "resolution": None,  # pending → clear | quarantined | exempted
            }
            entry_file = queue_dir / f"review-{manifest['model_id']}-{time.time():.0f}.json"
            entry_file.write_text(json.dumps(entry, indent=2))
            return True
        except Exception as e:
            log.warning("Failed to queue review: %s", e)
            return False


# ---------------------------------------------------------------------------
# Commit message generation
# ---------------------------------------------------------------------------


def _build_commit_message(manifest: dict) -> str:
    """Build a rich Git commit message from model.yaml metadata."""
    model_id = manifest.get("model_id", "unknown")
    version = manifest.get("version", "0.0.0")
    reactor = manifest.get("reactor_type", "")
    code = manifest.get("physics_code", "")
    status = manifest.get("status", "draft")
    author = manifest.get("created_by", "")
    description = manifest.get("description", "")

    subject = f"model({model_id}): v{version}"
    lines = [subject, ""]

    if description and not description.startswith("TODO"):
        lines.append(description[:200])
        lines.append("")

    lines.append(f"Reactor:  {reactor}")
    lines.append(f"Code:     {code}")
    lines.append(f"Status:   {status}")
    if author:
        lines.append(f"Author:   {author}")

    rom_tier = manifest.get("rom_tier")
    if rom_tier:
        lines.append(f"ROM Tier: {rom_tier}")
        source = manifest.get("training", {}).get("source_model")
        if source:
            lines.append(f"Trained from: {source}")

    parent = manifest.get("parent_model")
    if parent:
        lines.append(f"Parent:   {parent}")

    tags = manifest.get("tags", [])
    if tags:
        lines.append(f"Tags:     {', '.join(tags)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# EVE Watcher (safety net — primary sync is in service.add())
# ---------------------------------------------------------------------------


def run_watcher_cycle() -> None:
    """Safety net: push anything service.add() missed."""
    agent = ModelSyncAgent()
    if not agent.enabled:
        return

    result = agent.run_sync_cycle()
    if not result.success:
        log.error("Model sync failed: %s", result.message)
    elif result.action in ("push", "pull") and result.models_synced:
        log.info("Model sync catchup: %s %s model(s)", result.action, len(result.models_synced))


# ---------------------------------------------------------------------------
# Git helper
# ---------------------------------------------------------------------------


def _git(cwd: Path, args: list[str]) -> tuple[int, str]:
    """Run a git command. Returns (returncode, stdout)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return result.returncode, result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return -1, str(e)

"""M-O subscriber for mirror_agent — watches commits and flags sensitive content.

Runs in the M-O background loop. On each commit that touches public paths,
runs the LLM sensitivity reviewer and surfaces findings as nudges.

Circuit breakers mirror the M-O pattern: 3-hour cooldown per commit SHA.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

# Circuit breaker
COOLDOWN_SECONDS = 10800  # 3 hours — don't re-review the same commit
_reviewed: dict[str, float] = {}  # commit_sha -> timestamp


def register(bus: Any) -> None:
    """Register mirror handlers on the event bus."""
    bus.subscribe("mo.heartbeat", handle_heartbeat)
    bus.subscribe("mirror.commit", handle_commit)


def handle_heartbeat(topic: str, data: dict[str, Any]) -> None:
    """On each M-O heartbeat, check if HEAD has new unreviewed commits."""
    try:
        repo_root = _repo_root()
        if repo_root is None:
            return

        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True,
        ).strip()

        if not _should_review(sha):
            return

        # Check if any public paths were touched in the last commit
        touched = _public_files_changed(repo_root, "HEAD~1", "HEAD")
        if not touched:
            return

        # Trigger a review
        _run_review(repo_root, sha, touched)

    except Exception:
        pass


def handle_commit(topic: str, data: dict[str, Any]) -> None:
    """Handle explicit mirror.commit event (e.g. from a post-commit hook)."""
    try:
        sha = data.get("sha", "")
        repo_root_str = data.get("repo_root", "")
        if not sha or not repo_root_str:
            return

        repo_root = Path(repo_root_str)
        if not _should_review(sha):
            return

        touched = _public_files_changed(repo_root, f"{sha}~1", sha)
        if touched:
            _run_review(repo_root, sha, touched)
    except Exception:
        pass


def _run_review(repo_root: Path, sha: str, touched_files: list[str]) -> None:
    """Run LLM review on touched files and register nudges for any findings."""
    try:
        from neutron_os.infra.gateway import Gateway
        from neutron_os.infra.nudges import NudgeStore
        from .reviewer import review_mirror_content
        from .cli import PUBLIC_PATHS, EXCLUDE_PATHS

        gateway = Gateway()
        if not gateway.active_provider:
            return

        result = review_mirror_content(
            repo_root=repo_root,
            public_paths=PUBLIC_PATHS,
            exclude_paths=EXCLUDE_PATHS,
            gateway=gateway,
            since_ref=f"{sha}~1",
            max_files=20,
        )

        if result.is_clear:
            return

        store = NudgeStore()
        for review in result.flagged:
            nudge_id = f"mirror-sensitive-{sha[:8]}-{review.path.replace('/', '-')}"
            findings_text = "; ".join(review.findings[:3]) if review.findings else "See file"
            store.add(
                id=nudge_id,
                message=f"Mirror review flagged {review.path}: {findings_text}",
                hint="Run 'neut mirror review' to inspect before publishing.",
            )

    except Exception:
        pass


def _public_files_changed(repo_root: Path, from_ref: str, to_ref: str) -> list[str]:
    """Return public-path files changed between two refs."""
    from .cli import PUBLIC_PATHS, EXCLUDE_PATHS
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", from_ref, to_ref],
            cwd=repo_root, text=True, stderr=subprocess.DEVNULL,
        )
        changed = [l.strip() for l in out.splitlines() if l.strip()]
        return [
            f for f in changed
            if any(f.startswith(p) for p in PUBLIC_PATHS)
            and not any(f.startswith(ex) for ex in EXCLUDE_PATHS)
        ]
    except subprocess.CalledProcessError:
        return []


def _should_review(sha: str) -> bool:
    now = time.time()
    last = _reviewed.get(sha, 0)
    if now - last < COOLDOWN_SECONDS:
        return False
    _reviewed[sha] = now
    return True


def _repo_root() -> Path | None:
    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return Path(root)
    except subprocess.CalledProcessError:
        return None

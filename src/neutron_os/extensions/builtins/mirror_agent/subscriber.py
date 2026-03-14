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
    bus.subscribe("config.changed", handle_config_changed)


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


def handle_config_changed(topic: str, data: dict[str, Any]) -> None:
    """When institutional config changes, regenerate the scrub list from it."""
    changed_file = data.get("file", "")
    if "institutional" not in changed_file:
        return
    try:
        _regenerate_scrub_list()
    except Exception:
        pass


def _regenerate_scrub_list() -> None:
    """Extract names and identifiers from institutional.md → mirror_scrub_terms.txt.

    Uses the LLM to extract proper nouns from the roster — no hardcoded list needed.
    Falls back to a simple regex heuristic if no LLM is available.
    """
    repo_root = _repo_root()
    if repo_root is None:
        return

    institutional = repo_root / "runtime/config/institutional.md"
    scrub_file = repo_root / "runtime/config/mirror_scrub_terms.txt"

    if not institutional.exists():
        return

    content = institutional.read_text()

    try:
        from neutron_os.infra.gateway import Gateway
        gateway = Gateway()
        if gateway.active_provider:
            prompt = (
                "Extract all proper nouns from this institutional roster that should be "
                "kept private in a public open-source repo: staff names (first, last, full), "
                "internal project codenames, system hostnames, IP addresses, and "
                "facility-specific identifiers. Output one term per line, no bullets, no headers.\n\n"
                + content
            )
            resp = gateway.complete(prompt=prompt, system="You extract private identifiers from text.", max_tokens=800)
            response = resp.text if hasattr(resp, "text") else str(resp)
            terms = [line.strip() for line in response.splitlines() if line.strip() and not line.startswith("#")]
        else:
            terms = _extract_terms_heuristic(content)
    except Exception:
        terms = _extract_terms_heuristic(content)

    if not terms:
        return

    existing_header = "# mirror_scrub_terms.txt — gitignored, never mirrored to GitHub\n# Auto-maintained by M-O. Edit institutional.md to change the source.\n\n"
    scrub_file.write_text(existing_header + "\n".join(sorted(set(terms))) + "\n")


def _extract_terms_heuristic(content: str) -> list[str]:
    """Fallback: extract capitalised words likely to be proper nouns."""
    import re
    # Match runs of Title Case words (names, project names)
    matches = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', content)
    # Also grab ALL_CAPS identifiers (acronyms, codenames)
    acronyms = re.findall(r'\b[A-Z]{2,}\b', content)
    # Filter common English words
    stopwords = {"The", "This", "For", "Run", "See", "All", "Each", "Note", "And", "Or"}
    terms = [m for m in matches if m not in stopwords] + acronyms
    return list(set(terms))


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
        changed = [line.strip() for line in out.splitlines() if line.strip()]
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

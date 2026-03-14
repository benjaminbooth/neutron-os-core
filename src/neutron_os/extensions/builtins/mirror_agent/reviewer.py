"""LLM-based sensitivity reviewer for public mirror content.

Scans files that would be published and flags content that may be
sensitive for a nuclear research program: staff names, internal
identifiers, budget data, facility-specific configuration, etc.

Designed to complement path-based allowlists — catches sensitive
content that slips into otherwise-approved files.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


SENSITIVITY_PROMPT = """\
You are a security reviewer for an open-source nuclear facility software project.
Review the following file content and identify anything that should NOT be published
publicly for a nuclear research program.

Flag any of the following if present:
- Staff names, researcher names, or personal identifiers (first names + last names together)
- Internal project codenames that are not the public product name
- Budget figures, cost estimates, or financial data
- Facility-specific configuration (internal hostnames, IP addresses, internal URLs)
- Institutional credentials, tokens, or access details
- Grant proposal details, pre-decisional documents, or strategic roadmaps
- Personally identifiable information (PII)
- Anything that reveals internal organizational structure or personnel

Do NOT flag the following — these are public and expected in this codebase:
- "Neutron OS" or "NeutronOS" — this is the public product name
- Generic nuclear physics terms: TRIGA (reactor type), Cherenkov radiation, neutron flux,
  Monte Carlo, OpenMC, fission, criticality, isotopes, dose rates, etc.
- Standard open-source tooling: GitLab, GitHub, Linear, Docker, Terraform, etc.
- Generic technical terms that appear in any software project
- Public URLs and usernames in those URLs (github.com, pypi.org, anthropic.com, etc.)
- GitHub/GitLab usernames or organization names in clone URLs — these are already public

Respond in this exact format:
VERDICT: CLEAR or REVIEW_NEEDED
FINDINGS:
- <finding 1, or "None" if clear>
- <finding 2>
RECOMMENDATION: <one sentence>

Be conservative for actual sensitive data — if in doubt about a real person's name or
internal identifier, flag it. But do not flag generic domain terminology.
"""


@dataclass
class FileReview:
    path: str
    verdict: str  # "CLEAR" or "REVIEW_NEEDED"
    findings: list[str] = field(default_factory=list)
    recommendation: str = ""
    error: str = ""


@dataclass
class MirrorReview:
    files_reviewed: int = 0
    files_flagged: int = 0
    reviews: list[FileReview] = field(default_factory=list)

    @property
    def is_clear(self) -> bool:
        return self.files_flagged == 0

    @property
    def flagged(self) -> list[FileReview]:
        return [r for r in self.reviews if r.verdict == "REVIEW_NEEDED"]


def review_mirror_content(
    repo_root: Path,
    public_paths: list[str],
    exclude_paths: list[str],
    gateway,
    since_ref: Optional[str] = None,
    max_files: int = 50,
) -> MirrorReview:
    """Review files that would be published to the public mirror.

    Args:
        repo_root: Root of the git repository.
        public_paths: Allowlisted paths (same as push-public.sh PUBLIC_PATHS).
        exclude_paths: Paths excluded from the allowlist.
        gateway: Neutron OS LLM gateway instance.
        since_ref: If given, only review files changed since this git ref.
        max_files: Cap on files reviewed per run (cost control).
    """
    files = _collect_files(repo_root, public_paths, exclude_paths, since_ref, max_files)
    result = MirrorReview()

    for fpath in files:
        review = _review_file(fpath, repo_root, gateway)
        result.reviews.append(review)
        result.files_reviewed += 1
        if review.verdict == "REVIEW_NEEDED":
            result.files_flagged += 1

    return result


def _collect_files(
    repo_root: Path,
    public_paths: list[str],
    exclude_paths: list[str],
    since_ref: Optional[str],
    max_files: int,
) -> list[Path]:
    """Get the set of files to review."""
    if since_ref:
        # Only changed files since the ref
        try:
            out = subprocess.check_output(
                ["git", "diff", "--name-only", since_ref, "HEAD"],
                cwd=repo_root, text=True,
            )
            candidates = [repo_root / p.strip() for p in out.splitlines() if p.strip()]
        except subprocess.CalledProcessError:
            candidates = []
    else:
        # All tracked files in the allowlist
        candidates = []
        for p in public_paths:
            out = subprocess.check_output(
                ["git", "ls-files", p], cwd=repo_root, text=True,
            )
            for line in out.splitlines():
                candidates.append(repo_root / line.strip())

    # Apply exclusions
    exclude_set = {repo_root / p for p in exclude_paths}
    filtered = []
    for f in candidates:
        excluded = any(
            str(f).startswith(str(ex)) for ex in exclude_set
        )
        if not excluded and f.exists() and f.is_file() and _is_text_file(f):
            filtered.append(f)

    return filtered[:max_files]


def _review_file(fpath: Path, repo_root: Path, gateway) -> FileReview:
    """Send a single file to the LLM for sensitivity review."""
    rel = str(fpath.relative_to(repo_root))
    try:
        content = fpath.read_text(encoding="utf-8", errors="replace")
        # Truncate very large files
        if len(content) > 8000:
            content = content[:8000] + "\n\n[... truncated ...]"

        prompt = f"File: {rel}\n\n```\n{content}\n```"
        response = gateway.complete(
            prompt=prompt,
            system=SENSITIVITY_PROMPT,
            max_tokens=512,
        )
        return _parse_response(rel, response.text if hasattr(response, "text") else str(response))
    except Exception as e:
        return FileReview(path=rel, verdict="REVIEW_NEEDED", error=str(e),
                          recommendation="Could not review — inspect manually.")


def _parse_response(path: str, response: str) -> FileReview:
    """Parse the structured LLM response."""
    review = FileReview(path=path, verdict="CLEAR")
    lines = response.strip().splitlines()

    in_findings = False
    for line in lines:
        line = line.strip()
        if line.startswith("VERDICT:"):
            verdict = line.split(":", 1)[1].strip()
            review.verdict = "REVIEW_NEEDED" if "REVIEW" in verdict else "CLEAR"
        elif line.startswith("FINDINGS:"):
            in_findings = True
        elif line.startswith("RECOMMENDATION:"):
            in_findings = False
            review.recommendation = line.split(":", 1)[1].strip()
        elif in_findings and line.startswith("-"):
            finding = line.lstrip("- ").strip()
            if finding and finding.lower() != "none":
                review.findings.append(finding)

    return review


def _is_text_file(path: Path) -> bool:
    """Skip binary files."""
    skip_extensions = {
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
        ".pdf", ".docx", ".xlsx", ".pptx", ".odt",
        ".zip", ".tar", ".gz", ".whl", ".pyc",
        ".m4a", ".mp4", ".wav", ".webm",
        ".duckdb", ".parquet", ".h5",
    }
    return path.suffix.lower() not in skip_extensions

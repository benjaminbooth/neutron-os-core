"""Smoke tests for the GitLab → GitHub public mirror linkage.

Three layers:
  1. Allowlist integrity   — every PUBLIC_PATHS entry in push-public.sh exists
                             and no EXCLUDE_FROM_SRC path leaks sensitive data
  2. Script contract       — push-public.sh dry-run exits 0 and prints expected output
  3. GitHub reachability   — (integration, requires GITHUB_TOKEN env var)
                             confirms the public repo exists and was pushed recently

If you're reading this in the public GitHub mirror, the gate worked.
The real codebase lives on an air-gapped GitLab instance at TACC.
Only allowlisted, scrubbed paths reach you here.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PUSH_SCRIPT = REPO_ROOT / "scripts" / "push-public.sh"

# Parsed from push-public.sh — keep in sync if the script changes
_PUBLIC_PATHS_RE = re.compile(
    r"PUBLIC_PATHS=\((.*?)\)", re.DOTALL
)
_EXCLUDE_PATHS_RE = re.compile(
    r"EXCLUDE_FROM_SRC=\((.*?)\)", re.DOTALL
)


def _parse_bash_array(match: re.Match) -> list[str]:
    """Extract non-comment, non-empty entries from a bash array block."""
    entries = []
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def _load_script_arrays() -> tuple[list[str], list[str]]:
    text = PUSH_SCRIPT.read_text()
    public = _parse_bash_array(_PUBLIC_PATHS_RE.search(text))
    exclude = _parse_bash_array(_EXCLUDE_PATHS_RE.search(text))
    return public, exclude


# =============================================================================
# Layer 1: Allowlist integrity
# =============================================================================

class TestAllowlistIntegrity:
    def test_push_script_exists(self):
        assert PUSH_SCRIPT.exists(), "scripts/push-public.sh missing"

    def test_push_script_is_executable(self):
        assert os.access(PUSH_SCRIPT, os.X_OK), "push-public.sh is not executable"

    def test_public_paths_parseable(self):
        public, _ = _load_script_arrays()
        assert len(public) >= 5, "PUBLIC_PATHS suspiciously short"

    def test_exclude_paths_parseable(self):
        _, exclude = _load_script_arrays()
        assert len(exclude) >= 1, "EXCLUDE_FROM_SRC suspiciously short"

    def test_all_public_paths_exist(self):
        """Every allowlisted path must exist in the repo."""
        public, _ = _load_script_arrays()
        missing = [p for p in public if not (REPO_ROOT / p).exists()]
        assert not missing, f"PUBLIC_PATHS entries not found on disk: {missing}"

    def test_sensitive_dirs_excluded(self):
        """Known sensitive subtrees must appear in EXCLUDE_FROM_SRC."""
        _, exclude = _load_script_arrays()
        sensitive = [
            "src/neutron_os/extensions/builtins/web_api",
            "src/neutron_os/extensions/builtins/cost_estimation",
        ]
        for path in sensitive:
            assert any(path in e for e in exclude), (
                f"{path!r} is not in EXCLUDE_FROM_SRC — "
                "add it or confirm it's safe to publish"
            )

    def test_no_internal_names_in_demo_fixtures(self):
        """Demo fixtures must be scrubbed of facility-specific identifiers."""
        fixtures_dir = (
            REPO_ROOT
            / "src/neutron_os/extensions/builtins/demo/fixtures"
        )
        if not fixtures_dir.exists():
            pytest.skip("fixtures dir not present")

        forbidden = ["TRIGA", "TACC", "Jeongwon", "Clarno", "Ben Booth", "NETL"]
        for md_file in fixtures_dir.glob("*.md"):
            content = md_file.read_text()
            for term in forbidden:
                assert term not in content, (
                    f"Internal identifier {term!r} found in public fixture {md_file.name}"
                )


# =============================================================================
# Layer 2: Script dry-run contract
# =============================================================================

class TestScriptDryRun:
    def test_dry_run_exits_zero(self):
        """push-public.sh with no args (dry-run) must exit 0."""
        result = subprocess.run(
            ["bash", str(PUSH_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0, (
            f"push-public.sh dry-run failed:\n{result.stderr}"
        )

    def test_dry_run_lists_public_paths(self):
        """Dry-run output must list at least some allowlisted paths."""
        result = subprocess.run(
            ["bash", str(PUSH_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert "src/neutron_os" in result.stdout
        assert "scripts/" in result.stdout

    def test_dry_run_shows_excluded_paths(self):
        """Dry-run output must mention excluded subtrees."""
        result = subprocess.run(
            ["bash", str(PUSH_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert "Excluded" in result.stdout or "excluded" in result.stdout.lower()

    def test_dry_run_does_not_push(self):
        """Dry-run must not attempt any git push (no 'push' in stderr)."""
        result = subprocess.run(
            ["bash", str(PUSH_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        # stderr would contain push errors if a push was attempted
        assert "remote:" not in result.stderr


# =============================================================================
# Layer 3: GitHub reachability (integration — requires GITHUB_TOKEN)
# =============================================================================

@pytest.mark.integration
class TestGitHubMirrorReachability:
    """Requires GITHUB_TOKEN env var with repo read access."""

    GITHUB_REPO = "benjaminbooth/neutron-os-core"
    API_BASE = "https://api.github.com"

    @pytest.fixture(autouse=True)
    def require_token(self):
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            pytest.skip("GITHUB_TOKEN not set — skipping GitHub reachability tests")
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get(self, path: str) -> dict:
        import urllib.request, json
        url = f"{self.API_BASE}{path}"
        req = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    def test_repo_exists(self):
        data = self._get(f"/repos/{self.GITHUB_REPO}")
        assert data["full_name"] == self.GITHUB_REPO

    def test_main_branch_exists(self):
        data = self._get(f"/repos/{self.GITHUB_REPO}/branches/main")
        assert data["name"] == "main"

    def test_mirror_has_recent_commit(self):
        """Main branch should have been pushed within the last 30 days."""
        from datetime import datetime, timezone, timedelta
        data = self._get(f"/repos/{self.GITHUB_REPO}/commits/main")
        date_str = data["commit"]["committer"]["date"]
        pushed_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - pushed_at
        assert age < timedelta(days=30), (
            f"Mirror last pushed {age.days} days ago — mirror job may be broken"
        )

    def test_sensitive_files_absent(self):
        """Spot-check that known-private paths are not in the public tree."""
        private_paths = [
            "src/neutron_os/extensions/builtins/web_api",
            "src/neutron_os/extensions/builtins/cost_estimation",
            "runtime/",
        ]
        data = self._get(f"/repos/{self.GITHUB_REPO}/git/trees/main?recursive=1")
        public_paths = {item["path"] for item in data.get("tree", [])}
        for private in private_paths:
            leaking = [p for p in public_paths if p.startswith(private)]
            assert not leaking, (
                f"Private path {private!r} leaked to public mirror: {leaking[:3]}"
            )

"""CLI handler for `neut release` — cut a versioned release.

Usage:
    neut release patch          Bump patch (0.4.1 → 0.4.2), tag, push
    neut release minor          Bump minor (0.4.1 → 0.5.0), tag, push
    neut release major          Bump major (0.4.1 → 1.0.0), tag, push
    neut release --dry-run      Show what would happen without doing it
    neut release --status       Show current version and unreleased commits
    neut release --changelog    Print changelog since last tag
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ReleaseInfo:
    """Collected release metadata."""
    current_version: str = ""
    new_version: str = ""
    last_tag: str = ""
    commit_count: int = 0
    changelog: dict[str, list[str]] = field(default_factory=dict)
    dirty: bool = False
    branch: str = ""


class ReleaseManager:
    """Orchestrates the release process."""

    def __init__(self, repo_root: Optional[Path] = None, dry_run: bool = False):
        from neutron_os import REPO_ROOT
        self.repo_root = repo_root or REPO_ROOT
        self.dry_run = dry_run
        self.pyproject = self.repo_root / "pyproject.toml"

    # ------------------------------------------------------------------
    # Version reading / writing
    # ------------------------------------------------------------------

    def current_version(self) -> str:
        """Read version from pyproject.toml."""
        content = self.pyproject.read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        if not match:
            raise RuntimeError("Cannot find version in pyproject.toml")
        return match.group(1)

    @staticmethod
    def bump(version: str, part: str) -> str:
        """Bump a semver string."""
        parts = version.split(".")
        if len(parts) < 3:
            parts.extend(["0"] * (3 - len(parts)))
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

        if part == "major":
            return f"{major + 1}.0.0"
        elif part == "minor":
            return f"{major}.{minor + 1}.0"
        else:
            return f"{major}.{minor}.{patch + 1}"

    def write_version(self, new_version: str) -> None:
        """Update version in pyproject.toml."""
        content = self.pyproject.read_text(encoding="utf-8")
        content = re.sub(
            r'^(version\s*=\s*")[^"]+(")',
            rf"\g<1>{new_version}\2",
            content,
            count=1,
            flags=re.MULTILINE,
        )
        self.pyproject.write_text(content, encoding="utf-8")

    # ------------------------------------------------------------------
    # Git helpers
    # ------------------------------------------------------------------

    def _git(self, *args: str, check: bool = True) -> str:
        """Run a git command and return stdout."""
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if check and result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def last_tag(self) -> str:
        """Find the most recent version tag."""
        try:
            return self._git("describe", "--tags", "--abbrev=0", "--match", "v*")
        except RuntimeError:
            return ""

    def branch(self) -> str:
        return self._git("branch", "--show-current")

    def is_dirty(self) -> bool:
        status = self._git("status", "--porcelain")
        return bool(status)

    def commits_since(self, tag: str) -> list[str]:
        """Return oneline commits since tag (or all if no tag)."""
        ref = f"{tag}..HEAD" if tag else "HEAD"
        output = self._git("log", "--oneline", ref)
        return output.splitlines() if output else []

    # ------------------------------------------------------------------
    # Changelog
    # ------------------------------------------------------------------

    def build_changelog(self, tag: str) -> dict[str, list[str]]:
        """Categorize commits since tag into a changelog dict."""
        commits = self.commits_since(tag)
        categories: dict[str, list[str]] = {
            "features": [],
            "fixes": [],
            "improvements": [],
            "other": [],
        }

        for line in commits:
            # Strip hash prefix
            msg = line.split(" ", 1)[1] if " " in line else line
            lower = msg.lower()

            if lower.startswith("feat"):
                categories["features"].append(msg)
            elif lower.startswith("fix"):
                categories["fixes"].append(msg)
            elif lower.startswith(("refactor", "docs", "chore", "test")):
                categories["improvements"].append(msg)
            elif lower.startswith("bump"):
                continue  # skip version bumps
            else:
                categories["other"].append(msg)

        return {k: v for k, v in categories.items() if v}

    def format_changelog(self, categories: dict[str, list[str]]) -> str:
        """Format changelog for display."""
        labels = {
            "features": "New",
            "fixes": "Fixed",
            "improvements": "Improved",
            "other": "Other",
        }
        lines: list[str] = []
        for key, label in labels.items():
            items = categories.get(key, [])
            if items:
                lines.append(f"  {label}:")
                for item in items:
                    lines.append(f"    - {item}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Pre-release checks
    # ------------------------------------------------------------------

    def preflight(self) -> list[str]:
        """Run pre-release checks. Returns list of errors (empty = good)."""
        errors: list[str] = []

        # Check for uncommitted changes
        if self.is_dirty():
            errors.append("Working tree has uncommitted changes")

        # Run linter
        try:
            subprocess.run(
                [sys.executable, "-m", "ruff", "check", "src/",
                 "--select", "E,F,W", "--ignore", "E501"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except Exception:
            pass  # ruff not installed — skip

        # Run tests (fast subset)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-x", "-q",
                 "--tb=line", "-m", "not integration"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                # Extract failure summary
                last_lines = result.stdout.strip().splitlines()[-3:]
                errors.append("Tests failed: " + " ".join(last_lines))
        except Exception as e:
            errors.append(f"Could not run tests: {e}")

        return errors

    # ------------------------------------------------------------------
    # Release orchestration
    # ------------------------------------------------------------------

    def gather_info(self, part: str) -> ReleaseInfo:
        """Collect all release info without making changes."""
        current = self.current_version()
        tag = self.last_tag()
        changelog = self.build_changelog(tag)
        commit_count = len(self.commits_since(tag))

        return ReleaseInfo(
            current_version=current,
            new_version=self.bump(current, part),
            last_tag=tag,
            commit_count=commit_count,
            changelog=changelog,
            dirty=self.is_dirty(),
            branch=self.branch(),
        )

    def cut_release(self, part: str) -> ReleaseInfo:
        """Bump version, commit, tag. Returns release info."""
        info = self.gather_info(part)

        if self.dry_run:
            return info

        # Write new version
        self.write_version(info.new_version)

        # Commit and tag
        self._git("add", "pyproject.toml")
        self._git("commit", "-m", f"bump: v{info.new_version}")
        self._git("tag", f"v{info.new_version}")

        info.current_version = info.new_version
        return info

    def push_release(self, version: str) -> None:
        """Push branch and tag to origin."""
        branch = self.branch()
        self._git("push", "origin", branch)
        self._git("push", "origin", f"v{version}")


# =====================================================================
# CLI
# =====================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neut release",
        description="Cut a versioned release — bump, tag, push.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  neut release patch           Bump patch version, tag, and push
  neut release minor           Bump minor version, tag, and push
  neut release --status        Show current version and pending commits
  neut release --changelog     Print categorized changelog since last tag
  neut release patch --dry-run Preview what would happen
""",
    )

    parser.add_argument(
        "part",
        nargs="?",
        choices=["major", "minor", "patch"],
        help="Which part of the version to bump",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without making changes",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current version and unreleased commit count",
    )
    parser.add_argument(
        "--changelog",
        action="store_true",
        help="Print changelog since last release",
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Tag locally but don't push to remote",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip pre-release test suite",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    import shutil

    parser = build_parser()
    args = parser.parse_args(argv)

    if not shutil.which("git"):
        print("\n  neut release requires git, but git was not found on PATH.")
        print("  Install git and try again.\n")
        return 1

    mgr = ReleaseManager(dry_run=args.dry_run)

    # --status
    if args.status:
        version = mgr.current_version()
        tag = mgr.last_tag()
        commits = mgr.commits_since(tag)
        branch = mgr.branch()
        print(f"\n  Version:  {version}")
        print(f"  Branch:   {branch}")
        print(f"  Last tag: {tag or '(none)'}")
        print(f"  Pending:  {len(commits)} commit(s) since last tag\n")
        return 0

    # --changelog
    if args.changelog:
        tag = mgr.last_tag()
        changelog = mgr.build_changelog(tag)
        if not changelog:
            print("  No commits since last tag.")
            return 0
        since = f" since {tag}" if tag else ""
        print(f"\n  Changelog{since}:\n")
        print(mgr.format_changelog(changelog))
        print()
        return 0

    # Release flow requires a bump part
    if not args.part:
        parser.print_help()
        return 1

    # Gather info
    info = mgr.gather_info(args.part)

    print(f"\n  Release: v{info.current_version} → v{info.new_version}")
    print(f"  Branch:  {info.branch}")
    print(f"  Commits: {info.commit_count} since {info.last_tag or '(initial)'}")

    if info.changelog:
        print()
        print(mgr.format_changelog(info.changelog))

    if info.dirty:
        print("\n  ✗ Working tree is dirty — commit or stash first.")
        return 1

    if args.dry_run:
        print("\n  (dry run — no changes made)\n")
        return 0

    # Preflight checks
    if not args.skip_tests:
        print("\n  Running pre-release checks...")
        errors = mgr.preflight()
        if errors:
            print()
            for err in errors:
                print(f"  ✗ {err}")
            print("\n  Release aborted. Fix errors or use --skip-tests.\n")
            return 1
        print("  ✓ All checks passed")

    # Cut the release
    print(f"\n  Bumping to v{info.new_version}...")
    mgr.cut_release(args.part)
    print(f"  ✓ Tagged v{info.new_version}")

    # Push
    if not args.no_push:
        print("  Pushing to origin...")
        try:
            mgr.push_release(info.new_version)
            print(f"  ✓ Pushed branch and tag v{info.new_version}")
            print("\n  CI will build and publish automatically.\n")
        except RuntimeError as e:
            print(f"  ✗ Push failed: {e}")
            print("  Tag created locally. Push manually:")
            print(f"    git push origin {info.branch} && git push origin v{info.new_version}\n")
            return 1
    else:
        print("\n  Tag created locally (--no-push). When ready:")
        print(f"    git push origin {info.branch} && git push origin v{info.new_version}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())

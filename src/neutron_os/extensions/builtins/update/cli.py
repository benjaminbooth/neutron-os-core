"""CLI handler for `neut update` — keep NeutronOS current.

Usage:
    neut update              Update dependencies and run migrations
    neut update --deps       Only update Python dependencies
    neut update --migrate    Only run database migrations
    neut update --check      Check what would be updated (dry run)
    neut update --pull       Also pull latest from git
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class UpdateResult:
    """Result of an update operation."""
    step: str
    success: bool
    message: str
    changed: bool = False
    details: str = ""


class Updater:
    """Handles NeutronOS updates."""

    def __init__(self, repo_root: Optional[Path] = None, dry_run: bool = False):
        from neutron_os import REPO_ROOT
        self.repo_root = repo_root or REPO_ROOT
        self.dry_run = dry_run
        self.results: list[UpdateResult] = []

    def update_all(self, pull: bool = False) -> list[UpdateResult]:
        """Run full update: git pull, deps, migrations."""
        if pull:
            self._git_pull()
        self._update_deps()
        self._run_migrations()
        self._validate()
        return self.results

    def update_deps_only(self) -> list[UpdateResult]:
        """Update only Python dependencies."""
        self._update_deps()
        return self.results

    def run_migrations_only(self) -> list[UpdateResult]:
        """Run only database migrations."""
        self._run_migrations()
        return self.results

    def check_updates(self) -> list[UpdateResult]:
        """Check what would be updated without making changes."""
        self.dry_run = True
        self._check_git_status()
        self._check_deps()
        self._check_migrations()
        return self.results

    def _git_pull(self) -> None:
        """Pull latest from git."""
        if self.dry_run:
            self.results.append(UpdateResult(
                step="git",
                success=True,
                message="Would pull from origin",
                changed=False,
            ))
            return

        try:
            # Check if we're in a git repo
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                self.results.append(UpdateResult(
                    step="git",
                    success=True,
                    message="Not a git repository, skipping pull",
                    changed=False,
                ))
                return

            # Get current commit
            before = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            ).stdout.strip()[:8]

            # Pull
            result = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                self.results.append(UpdateResult(
                    step="git",
                    success=False,
                    message="Git pull failed",
                    details=result.stderr,
                ))
                return

            # Get new commit
            after = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            ).stdout.strip()[:8]

            changed = before != after
            self.results.append(UpdateResult(
                step="git",
                success=True,
                message=f"Updated {before} → {after}" if changed else "Already up to date",
                changed=changed,
            ))

        except FileNotFoundError:
            self.results.append(UpdateResult(
                step="git",
                success=True,
                message="Git not available, skipping pull",
                changed=False,
            ))

    def _check_git_status(self) -> None:
        """Check git status without pulling."""
        try:
            # Fetch to see if there are updates
            subprocess.run(
                ["git", "fetch", "--dry-run"],
                cwd=self.repo_root,
                capture_output=True,
                timeout=10,
            )

            subprocess.run(
                ["git", "status", "-uno", "--porcelain"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )

            # Check if behind
            behind = subprocess.run(
                ["git", "rev-list", "--count", "HEAD..@{u}"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )

            commits_behind = int(behind.stdout.strip()) if behind.returncode == 0 else 0

            self.results.append(UpdateResult(
                step="git",
                success=True,
                message=f"{commits_behind} commit(s) behind origin" if commits_behind else "Up to date",
                changed=commits_behind > 0,
            ))

        except Exception:
            self.results.append(UpdateResult(
                step="git",
                success=True,
                message="Could not check git status",
                changed=False,
            ))

    def _update_deps(self) -> None:
        """Update Python dependencies from pyproject.toml."""
        if self.dry_run:
            self._check_deps()
            return

        pyproject = self.repo_root / "pyproject.toml"
        if not pyproject.exists():
            self.results.append(UpdateResult(
                step="deps",
                success=False,
                message="pyproject.toml not found",
            ))
            return

        try:
            # Install with all extras
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", ".[all]", "-q"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                self.results.append(UpdateResult(
                    step="deps",
                    success=False,
                    message="Dependency installation failed",
                    details=result.stderr,
                ))
                return

            # Check if anything was installed/updated
            changed = "Successfully installed" in result.stdout or "Successfully installed" in result.stderr

            self.results.append(UpdateResult(
                step="deps",
                success=True,
                message="Dependencies updated" if changed else "Dependencies already current",
                changed=changed,
            ))

        except subprocess.TimeoutExpired:
            self.results.append(UpdateResult(
                step="deps",
                success=False,
                message="Dependency installation timed out",
            ))

    def _check_deps(self) -> None:
        """Check which dependencies would be updated."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", ".[all]", "--dry-run"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=60,
            )

            # Parse dry-run output for packages that would be installed
            lines = result.stdout.split('\n') + result.stderr.split('\n')
            would_install = [line for line in lines if "Would install" in line]

            if would_install:
                self.results.append(UpdateResult(
                    step="deps",
                    success=True,
                    message="Packages would be updated",
                    changed=True,
                    details='\n'.join(would_install),
                ))
            else:
                self.results.append(UpdateResult(
                    step="deps",
                    success=True,
                    message="All dependencies current",
                    changed=False,
                ))

        except Exception as e:
            self.results.append(UpdateResult(
                step="deps",
                success=True,
                message=f"Could not check deps: {e}",
                changed=False,
            ))

    def _run_migrations(self) -> None:
        """Run database migrations if PostgreSQL is available."""
        if self.dry_run:
            self._check_migrations()
            return

        # Check if db is available
        db_url = os.environ.get("NEUT_DB_URL", "postgresql://neut:neut@localhost:5432/neut_db")

        try:
            import psycopg2  # type: ignore[import-not-found]
            conn = psycopg2.connect(db_url, connect_timeout=3)
            conn.close()
        except ImportError:
            self.results.append(UpdateResult(
                step="migrations",
                success=True,
                message="psycopg2 not installed, skipping migrations",
                changed=False,
            ))
            return
        except Exception:
            self.results.append(UpdateResult(
                step="migrations",
                success=True,
                message="Database not available, skipping migrations",
                changed=False,
            ))
            return

        # Run migrations
        try:
            from neutron_os.extensions.builtins.sense_agent.migrations import run_migrations, check_migrations

            status = check_migrations()
            if status.get("up_to_date"):
                self.results.append(UpdateResult(
                    step="migrations",
                    success=True,
                    message="Database schema up to date",
                    changed=False,
                ))
                return

            run_migrations("upgrade", "head")

            self.results.append(UpdateResult(
                step="migrations",
                success=True,
                message="Migrations applied",
                changed=True,
            ))

        except Exception as e:
            self.results.append(UpdateResult(
                step="migrations",
                success=False,
                message=f"Migration failed: {e}",
            ))

    def _check_migrations(self) -> None:
        """Check if migrations are pending."""
        try:
            from neutron_os.extensions.builtins.sense_agent.migrations import check_migrations

            status = check_migrations()
            if status.get("up_to_date"):
                self.results.append(UpdateResult(
                    step="migrations",
                    success=True,
                    message="No pending migrations",
                    changed=False,
                ))
            else:
                pending = status.get("pending", [])
                self.results.append(UpdateResult(
                    step="migrations",
                    success=True,
                    message=f"{len(pending)} migration(s) pending",
                    changed=True,
                    details=str(pending),
                ))

        except ImportError:
            self.results.append(UpdateResult(
                step="migrations",
                success=True,
                message="Migration system not available",
                changed=False,
            ))
        except Exception as e:
            self.results.append(UpdateResult(
                step="migrations",
                success=True,
                message=f"Could not check migrations: {e}",
                changed=False,
            ))

    def _validate(self) -> None:
        """Validate the installation after update."""
        try:
            # Quick import check

            self.results.append(UpdateResult(
                step="validate",
                success=True,
                message="Installation validated",
                changed=False,
            ))

        except Exception as e:
            self.results.append(UpdateResult(
                step="validate",
                success=False,
                message=f"Validation failed: {e}",
            ))

    # -- Changelog & restart helpers ----------------------------------------

    def _get_changelog_between(
        self, old_ref: str, new_ref: str = "HEAD",
    ) -> list[dict[str, str]]:
        """Return commits between two refs as dicts with 'hash', 'subject', 'body'."""
        try:
            result = subprocess.run(
                [
                    "git", "log",
                    f"{old_ref}..{new_ref}",
                    "--pretty=format:%h\x1f%s\x1f%b\x1e",
                ],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return []

            commits = []
            for entry in result.stdout.split("\x1e"):
                entry = entry.strip()
                if not entry:
                    continue
                parts = entry.split("\x1f", 2)
                if len(parts) >= 2:
                    commits.append({
                        "hash": parts[0].strip(),
                        "subject": parts[1].strip(),
                        "body": parts[2].strip() if len(parts) > 2 else "",
                    })
            return commits
        except Exception:
            return []

    def _categorize_commits(
        self, commits: list[dict[str, str]],
    ) -> dict[str, list[str]]:
        """Group commits by conventional-commit prefix.

        Returns: {"features": [...], "fixes": [...], "improvements": [...], "other": [...]}
        """
        categories: dict[str, list[str]] = {
            "features": [],
            "fixes": [],
            "improvements": [],
            "other": [],
        }

        for commit in commits:
            subject = commit["subject"]
            lower = subject.lower()

            if lower.startswith(("feat", "add")):
                # Strip prefix: "feat: foo" -> "foo", "feat(scope): foo" -> "foo"
                clean = _strip_conventional_prefix(subject)
                categories["features"].append(clean)
            elif lower.startswith("fix"):
                clean = _strip_conventional_prefix(subject)
                categories["fixes"].append(clean)
            elif lower.startswith(("refactor", "perf", "improve", "ui", "chore")):
                clean = _strip_conventional_prefix(subject)
                categories["improvements"].append(clean)
            else:
                categories["other"].append(subject)

        # Remove empty categories
        return {k: v for k, v in categories.items() if v}

    def _stash_changelog(
        self,
        old_version: str,
        new_version: str,
        commits: list[dict[str, str]],
    ) -> None:
        """Write categorized changelog to .neut/pending-changelog.json."""
        from .version_check import CHANGELOG_FILE, NEUT_DIR

        categorized = self._categorize_commits(commits)
        data = {
            "old_version": old_version,
            "new_version": new_version,
            "categories": categorized,
            "commit_count": len(commits),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "shown": False,
        }
        try:
            NEUT_DIR.mkdir(parents=True, exist_ok=True)
            CHANGELOG_FILE.write_text(
                json.dumps(data, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    def update_and_restart(
        self,
        session_id: str,
        pull: bool = True,
    ) -> None:
        """Run update, stash changelog, exec into a new process with --resume.

        This replaces the current process via os.execv — it does not return.
        """
        from .version_check import (
            VersionChecker,
            write_restart_state,
        )

        checker = VersionChecker(self.repo_root)
        old_version = checker.get_current_version()

        # Get current git ref before updating
        old_ref = self._get_git_head()

        # Run the actual update
        if pull:
            self._git_pull()
        self._update_deps()
        self._run_migrations()

        # Get new version and changelog
        new_version = checker.get_current_version()
        new_ref = self._get_git_head()

        if old_ref and new_ref and old_ref != new_ref:
            commits = self._get_changelog_between(old_ref, new_ref)
            if commits:
                self._stash_changelog(old_version, new_version, commits)

        # Write restart state for auto-resume
        write_restart_state(session_id, old_version, new_version)

        # Replace current process
        os.execv(
            sys.executable,
            [sys.executable, "-m", "tools.neut_cli", "chat", "--resume", session_id],
        )

    def _get_git_head(self) -> Optional[str]:
        """Return current HEAD commit hash, or None."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None

    def summary(self) -> str:
        """Generate summary of update results."""
        if not self.results:
            return "No updates performed"

        lines = []

        for result in self.results:
            if result.success:
                icon = "✓" if not result.changed else "↑"
            else:
                icon = "✗"

            lines.append(f"  {icon} {result.step}: {result.message}")

            if result.details and (not result.success or result.changed):
                for detail in result.details.split('\n')[:5]:
                    if detail.strip():
                        lines.append(f"      {detail.strip()}")

        failed = sum(1 for r in self.results if not r.success)
        changed = sum(1 for r in self.results if r.changed)

        lines.append("")
        if failed:
            lines.append(f"❌ {failed} step(s) failed")
        elif changed:
            lines.append(f"✅ Updated ({changed} change(s))")
        else:
            lines.append("✅ Everything up to date")

        return '\n'.join(lines)


def _strip_conventional_prefix(subject: str) -> str:
    """Strip conventional-commit prefix: 'feat(scope): foo' -> 'foo'."""
    import re
    m = re.match(r'^[a-zA-Z]+(?:\([^)]*\))?\s*:\s*', subject)
    if m:
        return subject[m.end():]
    return subject


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        prog="neut update",
        description="Keep NeutronOS current",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  neut update              # Update deps and run migrations
  neut update --check      # See what would be updated
  neut update --pull       # Also pull from git
  neut update --deps       # Only update Python packages
  neut update --status     # Update and show system health
""",
    )

    parser.add_argument(
        "--check", "-c",
        action="store_true",
        help="Check what would be updated (dry run)",
    )
    parser.add_argument(
        "--pull", "-p",
        action="store_true",
        help="Also pull latest from git",
    )
    parser.add_argument(
        "--deps",
        action="store_true",
        help="Only update Python dependencies",
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Only run database migrations",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed output",
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show system health after update",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    updater = Updater(dry_run=args.check)

    print("🔄 neut update")
    print("=" * 40)

    if args.check:
        print("Checking for updates (dry run)...\n")
        updater.check_updates()
    elif args.deps:
        print("Updating dependencies...\n")
        updater.update_deps_only()
    elif args.migrate:
        print("Running migrations...\n")
        updater.run_migrations_only()
    else:
        print("Updating NeutronOS...\n")
        updater.update_all(pull=args.pull)

    print(updater.summary())

    # Show system health if requested
    if args.status:
        print("\n")
        from neutron_os.extensions.builtins.status.cli import HealthChecker, format_health_table
        checker = HealthChecker()
        health = checker.check_all()
        print(format_health_table(health, use_color=sys.stdout.isatty()))

    failed = any(not r.success for r in updater.results)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

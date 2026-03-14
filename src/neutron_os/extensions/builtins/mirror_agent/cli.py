"""CLI for neut mirror — AI-powered public mirror gate.

Commands:
    neut mirror review          Scan public content for sensitive data
    neut mirror review --all    Review all public files (not just changed)
    neut mirror push            Review then push to GitHub (human-in-the-loop)
    neut mirror status          Show last review result and mirror state
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from neutron_os.setup.renderer import _c, _Colors

# Sync with scripts/push-public.sh
PUBLIC_PATHS = [
    ".env.example", ".envrc", ".gitignore", ".github/workflows",
    "CLAUDE.md", "CONTRIBUTING.md", "LICENSE", "Makefile", "README.md",
    "conftest.py", "pyproject.toml",
    "scripts/bootstrap.sh", "scripts/install.sh", "scripts/neut",
    "scripts/neut-doctor", "scripts/push-public.sh", "scripts/README.md",
    "src/neutron_os", "tests",
]

EXCLUDE_PATHS = [
    "src/neutron_os/extensions/builtins/web_api",
    "src/neutron_os/extensions/builtins/cost_estimation",
    "src/neutron_os/extensions/builtins/sense_agent/infra",
    "src/neutron_os/infra/subscribers",
    # Meta-documentation reviewed manually when updated; intentionally public.
    "CONTRIBUTING.md",
]

COMMANDS = {
    "review": "Scan public mirror content for sensitive data (LLM-powered)",
    "push":   "Review then push to GitHub mirror (human-in-the-loop)",
    "status": "Show mirror status and last review result",
}


def register(subparsers):
    p = subparsers.add_parser("mirror", help="Public mirror management")
    sub = p.add_subparsers(dest="mirror_cmd")

    r = sub.add_parser("review", help=COMMANDS["review"])
    r.add_argument("--all", action="store_true",
                   help="Review all public files, not just changed ones")
    r.add_argument("--since", metavar="REF",
                   help="Review files changed since this git ref")
    r.add_argument("--ci", action="store_true",
                   help="CI mode: exit 1 if anything flagged, no prompts")

    sub.add_parser("push", help=COMMANDS["push"])
    sub.add_parser("status", help=COMMANDS["status"])

    p.set_defaults(func=_dispatch)


def _dispatch(args):
    cmd = getattr(args, "mirror_cmd", None)
    if cmd == "review":
        _cmd_review(args)
    elif cmd == "push":
        _cmd_push(args)
    elif cmd == "status":
        _cmd_status(args)
    else:
        print("Usage: neut mirror <review|push|status>")
        sys.exit(1)


def _cmd_review(args):
    from neutron_os.infra.gateway import Gateway
    from .reviewer import review_mirror_content

    repo_root = _repo_root()
    gateway = Gateway()

    if not gateway.active_provider:
        print(_c(_Colors.YELLOW, "⚠  No LLM configured — running pattern-only review."))
        print("   Configure an LLM provider for full AI-powered analysis.")
        print("   Run: neut doctor\n")
        _pattern_review(repo_root)
        return

    review_all = getattr(args, "all", False)
    since_ref = getattr(args, "since", None)

    if not review_all and not since_ref:
        # Default: changed since last push to github/main
        since_ref = _last_github_ref(repo_root)

    if since_ref:
        print(f"\n  Reviewing files changed since {_c(_Colors.CYAN, since_ref)}...\n")
    else:
        print(f"\n  Reviewing all {_c(_Colors.CYAN, 'public')} files...\n")

    result = review_mirror_content(
        repo_root=repo_root,
        public_paths=PUBLIC_PATHS,
        exclude_paths=EXCLUDE_PATHS,
        gateway=gateway,
        since_ref=since_ref,
        max_files=50,
    )

    _print_review_result(result)

    if getattr(args, "ci", False) and not result.is_clear:
        sys.exit(1)


def _cmd_push(args):
    """Run review gate, then push if clear (or user confirms)."""
    from neutron_os.infra.gateway import Gateway
    from .reviewer import review_mirror_content

    repo_root = _repo_root()
    push_script = repo_root / "scripts" / "push-public.sh"

    if not push_script.exists():
        print(_c(_Colors.RED, "ERROR: scripts/push-public.sh not found."))
        sys.exit(1)

    gateway = Gateway()

    print(f"\n  {_c(_Colors.BOLD, 'Mirror Push Gate')}\n")

    if gateway.active_provider:
        print("  Step 1/2: AI sensitivity review...\n")
        since_ref = _last_github_ref(repo_root)
        result = review_mirror_content(
            repo_root=repo_root,
            public_paths=PUBLIC_PATHS,
            exclude_paths=EXCLUDE_PATHS,
            gateway=gateway,
            since_ref=since_ref,
            max_files=50,
        )
        _print_review_result(result)

        if not result.is_clear:
            print(_c(_Colors.RED, "\n  ✗ Review flagged issues. Resolve before pushing."))
            print("  Run 'neut mirror review --all' for a full scan.\n")
            sys.exit(1)
        print(_c(_Colors.GREEN, "  ✓ Review passed.\n"))
    else:
        print(_c(_Colors.YELLOW, "  ⚠  No LLM — skipping AI review. Proceeding with allowlist only.\n"))

    print("  Step 2/2: Pushing to GitHub mirror...")
    print(_c(_Colors.DIM, "  This will force-push to the public repository.\n"))

    try:
        confirm = input("  Confirm push? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n  Aborted.")
        sys.exit(0)

    if confirm != "y":
        print("  Aborted.")
        sys.exit(0)

    subprocess.run(["bash", str(push_script), "--push"], check=True)


def _cmd_status(args):
    repo_root = _repo_root()
    last_ref = _last_github_ref(repo_root)

    print(f"\n  {_c(_Colors.BOLD, 'Mirror Status')}\n")

    # Show remote URL
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "github"],
            cwd=repo_root, text=True,
        ).strip()
        print(f"  Remote:      {_c(_Colors.CYAN, url)}")
    except subprocess.CalledProcessError:
        print(f"  Remote:      {_c(_Colors.RED, 'github remote not configured')}")

    # Show sync state
    if last_ref:
        print(f"  Last push:   {_c(_Colors.DIM, last_ref)}")
        try:
            count = subprocess.check_output(
                ["git", "rev-list", "--count", f"{last_ref}..HEAD"],
                cwd=repo_root, text=True,
            ).strip()
            if count == "0":
                print(f"  Unpublished: {_c(_Colors.GREEN, 'up to date')}")
            else:
                print(f"  Unpublished: {_c(_Colors.YELLOW, f'{count} commit(s) ahead')}")
        except subprocess.CalledProcessError:
            pass
    else:
        print(f"  Last push:   {_c(_Colors.DIM, 'unknown')}")

    print(f"\n  Run {_c(_Colors.CYAN, 'neut mirror review')} to scan for sensitive content.")
    print(f"  Run {_c(_Colors.CYAN, 'neut mirror push')} to review and publish.\n")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
        ).strip()
        return Path(root)
    except subprocess.CalledProcessError:
        print(_c(_Colors.RED, "ERROR: Not inside a git repository."))
        sys.exit(1)


def _last_github_ref(repo_root: Path) -> str | None:
    """Get the commit hash of the last push to the github remote."""
    try:
        subprocess.run(
            ["git", "fetch", "github", "--quiet"],
            cwd=repo_root, capture_output=True,
        )
        ref = subprocess.check_output(
            ["git", "rev-parse", "github/main"],
            cwd=repo_root, text=True,
        ).strip()
        return ref
    except subprocess.CalledProcessError:
        return None


def _pattern_review(repo_root: Path) -> None:
    """Fallback: grep for obvious sensitive patterns without LLM."""
    import re

    patterns = {
        "Email addresses": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "Tokens/secrets":  r"(glpat|ghp_|sk-|AKIA)[A-Za-z0-9_\-]{10,}",
        "Internal URLs":   r"https?://[a-z0-9.-]*(tacc|utexas|rsicc)[a-z0-9./%-]*",
        "Dollar amounts":  r"\$[0-9,]+(\.[0-9]{2})?",
    }

    flagged = []
    for p in PUBLIC_PATHS:
        files_out = subprocess.check_output(
            ["git", "ls-files", p], cwd=repo_root, text=True,
        )
        for fname in files_out.splitlines():
            fpath = repo_root / fname.strip()
            excluded = any(fname.startswith(ex) for ex in EXCLUDE_PATHS)
            if excluded or not fpath.is_file():
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
                for label, pat in patterns.items():
                    for match in re.finditer(pat, content):
                        flagged.append((fname, label, match.group()))
            except Exception:
                continue

    if not flagged:
        print(_c(_Colors.GREEN, "  ✓ No obvious sensitive patterns found.\n"))
        return

    print(_c(_Colors.YELLOW, f"  ⚠  {len(flagged)} pattern match(es) found:\n"))
    for fname, label, match in flagged[:20]:
        print(f"  {_c(_Colors.CYAN, fname)}: {label} — {_c(_Colors.DIM, match[:60])}")
    if len(flagged) > 20:
        print(f"  {_c(_Colors.DIM, f'... and {len(flagged) - 20} more')}")
    print()


def main():
    import argparse
    parser = argparse.ArgumentParser(prog="neut mirror", description="Public mirror management")
    sub = parser.add_subparsers(dest="mirror_cmd")

    r = sub.add_parser("review", help=COMMANDS["review"])
    r.add_argument("--all", action="store_true", help="Review all public files, not just changed ones")
    r.add_argument("--since", metavar="REF", help="Review files changed since this git ref")
    r.add_argument("--ci", action="store_true", help="CI mode: exit 1 if anything flagged")

    sub.add_parser("push", help=COMMANDS["push"])
    sub.add_parser("status", help=COMMANDS["status"])

    args = parser.parse_args()
    _dispatch(args)


def _print_review_result(result) -> None:

    total = result.files_reviewed
    flagged = result.files_flagged

    if result.is_clear:
        print(_c(_Colors.GREEN, f"  ✓ {total} file(s) reviewed — nothing flagged.\n"))
        return

    print(_c(_Colors.YELLOW, f"  ⚠  {flagged} of {total} file(s) flagged for review:\n"))
    for r in result.flagged:
        print(f"  {_c(_Colors.CYAN, r.path)}")
        for finding in r.findings:
            print(f"    · {finding}")
        if r.recommendation:
            print(f"    {_c(_Colors.DIM, '→')} {r.recommendation}")
        print()

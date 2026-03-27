#!/usr/bin/env bash
# push-public.sh — Push a stripped copy of main to the public GitHub mirror.
#
# Uses an ALLOWLIST: only explicitly approved paths are published.
# Everything else is private by default — new files don't leak.
#
# To add something to the public mirror, add it to PUBLIC_PATHS below.
#
# Usage:
#   ./scripts/push-public.sh              # dry run (shows what would be published)
#   ./scripts/push-public.sh --push       # actually push to GitHub
#   ./scripts/push-public.sh --push --yes # non-interactive (CI use)
#
# Requires: git-filter-repo (pip install git-filter-repo)

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
GITHUB_REMOTE="github"
BRANCH="main"
DRY_RUN=true
YES=false

for arg in "$@"; do
    case "$arg" in
        --push) DRY_RUN=false ;;
        --yes)  YES=true ;;
    esac
done

# ALLOWLIST — only these paths go to GitHub. Everything else stays internal.
# To publish something new, add it here and get it reviewed.
PUBLIC_PATHS=(
    # Root files
    .env.example
    .envrc
    .gitignore
    .github/workflows
    CLAUDE.md
    CONTRIBUTING.md
    LICENSE
    Makefile
    README.md
    conftest.py
    pyproject.toml

    # Bootstrap scripts (no internal paths or identifiers)
    scripts/bootstrap.sh
    scripts/install.sh
    scripts/neut
    scripts/neut-doctor
    scripts/push-public.sh
    scripts/README.md

    # Platform source (generic, no facility-specific data)
    src/neutron_os

    # Tests
    tests
)

# Paths within src/neutron_os to EXCLUDE even though src/neutron_os is allowed.
# These are subtracted after the allowlist is applied.
EXCLUDE_FROM_SRC=(
    src/neutron_os/extensions/builtins/web_api
    src/neutron_os/extensions/builtins/sense_agent/infra
    src/neutron_os/infra/subscribers
)

echo "==> Checking requirements..."
command -v git-filter-repo >/dev/null 2>&1 || {
    echo "ERROR: git-filter-repo not found. Run: pip install git-filter-repo"
    exit 1
}

if $DRY_RUN; then
    echo ""
    echo "DRY RUN — paths published to public mirror (allowlist):"
    for p in "${PUBLIC_PATHS[@]}"; do
        count=$(git -C "$REPO_ROOT" ls-files "$p" 2>/dev/null | wc -l | tr -d ' ')
        echo "  + $p  ($count files)"
    done
    echo ""
    echo "Excluded from src/neutron_os:"
    for p in "${EXCLUDE_FROM_SRC[@]}"; do
        count=$(git -C "$REPO_ROOT" ls-files "$p" 2>/dev/null | wc -l | tr -d ' ')
        echo "  - $p  ($count files)"
    done
    echo ""
    total=$(git -C "$REPO_ROOT" ls-files | wc -l | tr -d ' ')
    echo "  Total tracked files: $total"
    echo ""
    echo "Run with --push to publish: ./scripts/push-public.sh --push"
    exit 0
fi

echo "==> Creating temporary clone..."
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

git clone --no-local "$REPO_ROOT" "$TMPDIR/public-mirror" --single-branch 2>/dev/null || \
git clone --no-local "$REPO_ROOT" "$TMPDIR/public-mirror"
cd "$TMPDIR/public-mirror"

echo "==> Applying allowlist (keeping only approved paths)..."
FILTER_ARGS=()
for p in "${PUBLIC_PATHS[@]}"; do
    FILTER_ARGS+=(--path "$p")
done
git filter-repo "${FILTER_ARGS[@]}" --force

echo "==> Removing excluded subtrees..."
EXCLUDE_ARGS=()
for p in "${EXCLUDE_FROM_SRC[@]}"; do
    EXCLUDE_ARGS+=(--path "$p")
done
git filter-repo "${EXCLUDE_ARGS[@]}" --invert-paths --force

echo "==> Squashing to a single clean commit (zero history)..."
# Create an orphan branch so the public repo has no internal commit history.
# Every push is a fresh single commit — internal development history stays private.
git checkout --orphan public-release
git add -A
COMMIT_DATE="$(git -C "$REPO_ROOT" log -1 --format="%aI")"
GIT_COMMITTER_DATE="$COMMIT_DATE" git commit \
    --date="$COMMIT_DATE" \
    -m "Initial release"

echo "==> Adding GitHub remote..."
# In CI, the github remote is pre-configured by the job before calling this script.
# Locally, we look it up from the developer's repo config.
if ! git remote get-url github >/dev/null 2>&1; then
    git remote add github "$(git -C "$REPO_ROOT" remote get-url $GITHUB_REMOTE)"
fi

echo "==> Pushing to GitHub (force — single orphan commit)..."
git push github "public-release:$BRANCH" --force

echo ""
echo "Done. Public mirror updated: $(git remote get-url github)"

#!/usr/bin/env bash
# push-public.sh — Push a stripped copy of main to the public GitHub mirror.
#
# Removes internal-only paths before pushing:
#   docs/        design intent, research, grant proposals, ADRs, PRDs, OKRs
#   infra/       Terraform/Helm — infrastructure topology
#   data/        schemas and seed data
#   spikes/      experimental/unreviewed code
#   archive/     retired code
#   runtime/     facility config examples
#   .neut/       local extension state
#   .claude.example/  internal AI assistant context templates
#   .gitlab-ci.yml    CI internals
#   .mcp.json         internal MCP config
#
# Usage:
#   ./scripts/push-public.sh              # dry run (shows what would be removed)
#   ./scripts/push-public.sh --push       # actually push to GitHub
#
# Requires: git-filter-repo (pip install git-filter-repo)

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
GITHUB_REMOTE="github"
BRANCH="main"
DRY_RUN=true

if [[ "${1:-}" == "--push" ]]; then
    DRY_RUN=false
fi

# Paths to strip from the public mirror
INTERNAL_PATHS=(
    docs
    infra
    data
    spikes
    archive
    runtime
    .neut
    ".claude.example"
    .gitlab-ci.yml
    .mcp.json
)

echo "==> Checking requirements..."
command -v git-filter-repo >/dev/null 2>&1 || {
    echo "ERROR: git-filter-repo not found. Run: pip install git-filter-repo"
    exit 1
}

if $DRY_RUN; then
    echo ""
    echo "DRY RUN — paths that would be stripped from public mirror:"
    for p in "${INTERNAL_PATHS[@]}"; do
        count=$(git -C "$REPO_ROOT" ls-files "$p" 2>/dev/null | wc -l | tr -d ' ')
        echo "  $p  ($count files)"
    done
    echo ""
    echo "Run with --push to publish: ./scripts/push-public.sh --push"
    exit 0
fi

echo "==> Creating temporary clone..."
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

git clone --no-local "$REPO_ROOT" "$TMPDIR/public-mirror" --branch "$BRANCH" --single-branch
cd "$TMPDIR/public-mirror"

echo "==> Stripping internal paths..."
FILTER_ARGS=()
for p in "${INTERNAL_PATHS[@]}"; do
    FILTER_ARGS+=(--path "$p")
done
git filter-repo "${FILTER_ARGS[@]}" --invert-paths --force

echo "==> Adding GitHub remote..."
git remote add github "$(git -C "$REPO_ROOT" remote get-url $GITHUB_REMOTE)"

echo "==> Pushing to GitHub (force)..."
git push github "$BRANCH" --force --tags

echo ""
echo "Done. Public mirror updated: $(git -C "$REPO_ROOT" remote get-url $GITHUB_REMOTE)"

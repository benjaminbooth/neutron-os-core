#!/bin/bash
# Codebase Split Script: neutron-os → axiom + neutron-os
# 
# This script helps automate the extraction of generic code to axiom.
# Run phases individually and review output before proceeding.
#
# Usage:
#   ./scripts/split-codebase.sh phase1  # Prepare (in-place refactoring)
#   ./scripts/split-codebase.sh phase2  # Create axiom repo
#   ./scripts/split-codebase.sh phase3  # Update neutron-os
#   ./scripts/split-codebase.sh verify  # Verify no nuclear keywords in axiom

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
AXIOM_TEMP="${PROJECT_ROOT}/../axiom-temp"
AXIOM_REPO="git@github.com:benjaminbooth/axiom.git"

# Files that should be in axiom (generic platform)
AXIOM_PATHS=(
    "src/neutron_os/__init__.py"
    "src/neutron_os/neut_cli.py"
    "src/neutron_os/cli_registry.py"
    "src/neutron_os/infra/__init__.py"
    "src/neutron_os/infra/audit_log.py"
    "src/neutron_os/infra/auth"
    "src/neutron_os/infra/cli_format.py"
    "src/neutron_os/infra/config_loader.py"
    "src/neutron_os/infra/connections.py"
    "src/neutron_os/infra/gateway.py"
    "src/neutron_os/infra/git.py"
    "src/neutron_os/infra/hash_utils.py"
    "src/neutron_os/infra/log_sinks.py"
    "src/neutron_os/infra/neut_logging.py"
    "src/neutron_os/infra/nudges.py"
    "src/neutron_os/infra/orchestrator"
    "src/neutron_os/infra/prompt_registry.py"
    "src/neutron_os/infra/provider_base.py"
    "src/neutron_os/infra/publication_registry.py"
    "src/neutron_os/infra/raci.py"
    "src/neutron_os/infra/rate_limiter.py"
    "src/neutron_os/infra/retry.py"
    "src/neutron_os/infra/router.py"
    "src/neutron_os/infra/routing_audit.py"
    "src/neutron_os/infra/security_log.py"
    "src/neutron_os/infra/self_heal.py"
    "src/neutron_os/infra/services.py"
    "src/neutron_os/infra/state.py"
    "src/neutron_os/infra/state_pg.py"
    "src/neutron_os/infra/subscribers"
    "src/neutron_os/infra/time_utils.py"
    "src/neutron_os/infra/toml_compat.py"
    "src/neutron_os/infra/trace.py"
    "src/neutron_os/extensions/__init__.py"
    "src/neutron_os/extensions/cli.py"
    "src/neutron_os/extensions/contracts.py"
    "src/neutron_os/extensions/discovery.py"
    "src/neutron_os/extensions/scaffold.py"
    # Note: builtins/demo stays in neutron-os (TRIGA-specific demo scenario)
    "src/neutron_os/extensions/builtins/__init__.py"
    "src/neutron_os/extensions/builtins/README.md"
    "src/neutron_os/extensions/builtins/connect"
    "src/neutron_os/extensions/builtins/db"
    "src/neutron_os/extensions/builtins/dfib_agent"
    "src/neutron_os/extensions/builtins/eve_agent"
    "src/neutron_os/extensions/builtins/install"
    "src/neutron_os/extensions/builtins/log"
    "src/neutron_os/extensions/builtins/mirror_agent"
    "src/neutron_os/extensions/builtins/mo_agent"
    "src/neutron_os/extensions/builtins/neut_agent"
    "src/neutron_os/extensions/builtins/note"
    "src/neutron_os/extensions/builtins/prt_agent"
    "src/neutron_os/extensions/builtins/rag"
    "src/neutron_os/extensions/builtins/release"
    "src/neutron_os/extensions/builtins/repo"
    "src/neutron_os/extensions/builtins/settings"
    "src/neutron_os/extensions/builtins/status"
    "src/neutron_os/extensions/builtins/test"
    "src/neutron_os/extensions/builtins/update"
    "src/neutron_os/extensions/builtins/web_api"
    "src/neutron_os/rag"
    "src/neutron_os/review"
    "src/neutron_os/setup"
    "infra/db"
    "infra/systemd"
    "infra/terraform/modules"
    "runtime/config.example/llm-providers.toml"
    "runtime/config.example/settings.toml"
    "runtime/config.example/logging.toml"
    "runtime/config.example/models.toml"
    "runtime/config.example/install.toml"
    "runtime/config.example/retention.yaml"
    "runtime/config.example/routing_allowlist.txt"
    "runtime/config.example/injection_patterns.txt"
    "runtime/config.example/mirror_scrub_terms.txt"
    "runtime/config.example/stt_glossary.json"
    "runtime/config.example/templates"
    "runtime/config.example/heartbeat.md"
    "runtime/config.example/initiatives.md"
    "runtime/config.example/people.md"
    "tests"
    "Dockerfile"
    "Makefile"
    "conftest.py"
)

# Nuclear keywords to check for (word boundaries to avoid false positives like "heuristic")
# Note: SCALE removed - causes false positives with CSS "initial-scale" and similar
NUCLEAR_KEYWORDS="\bTRIGA\b|\bMCNP\b|\bHEU\b|\bLEU\b|\breactor\b|\b10 CFR\b|\bNETL\b|\bTACC\b|\bnuclear\b"

# Files/folders that are intentionally nuclear-specific (stay in neutron-os layer)
# These are excluded from verify-local checks using grep --exclude-dir
NUCLEAR_SPECIFIC_DIRS=(
    "docs"  # Internal docs folders (PRDs/specs with nuclear-specific content)
)

phase1_prepare() {
    echo "=== Phase 1: In-Place Refactoring ==="
    echo ""
    echo "This phase identifies nuclear content in generic files."
    echo "Review and manually refactor before proceeding."
    echo ""
    
    cd "$PROJECT_ROOT"
    
    echo "Files with nuclear keywords that need refactoring:"
    echo "=================================================="
    
    # Check each axiom file for nuclear keywords
    for path in "${AXIOM_PATHS[@]}"; do
        if [[ -e "$path" ]]; then
            matches=$(grep -riE "$NUCLEAR_KEYWORDS" "$path" 2>/dev/null || true)
            if [[ -n "$matches" ]]; then
                echo ""
                echo "📁 $path"
                echo "$matches" | head -10
                if [[ $(echo "$matches" | wc -l) -gt 10 ]]; then
                    echo "  ... and more"
                fi
            fi
        fi
    done
    
    echo ""
    echo "=== Manual Refactoring Required ==="
    echo ""
    echo "1. router.py: Extract NUCLEAR_CLASSIFIER_PROMPT to config"
    echo "2. scaffold.py: Replace reactor_logs/reactor_query examples"
    echo "3. gateway.py: Change 'mcnp' comment to 'domain-tag'"
    echo "4. nudges.py: Change 'triga-tools' to 'example-tools'"
    echo "5. state.py: Parameterize 'Reactor Ops Log' docstring"
    echo ""
    echo "After refactoring, run: $0 verify-local"
}

phase1_verify_local() {
    echo "=== Verifying no nuclear keywords in axiom files ==="
    
    cd "$PROJECT_ROOT"
    found=0
    
    # Build exclude patterns for grep
    exclude_args=""
    for dir in "${NUCLEAR_SPECIFIC_DIRS[@]}"; do
        exclude_args="$exclude_args --exclude-dir=$dir"
    done
    
    for path in "${AXIOM_PATHS[@]}"; do
        if [[ -e "$path" ]]; then
            # shellcheck disable=SC2086
            if grep -qriE --binary-files=without-match $exclude_args "$NUCLEAR_KEYWORDS" "$path" 2>/dev/null; then
                echo "❌ Nuclear keyword found in: $path"
                # shellcheck disable=SC2086
                grep -riE --binary-files=without-match $exclude_args "$NUCLEAR_KEYWORDS" "$path" | head -5
                found=1
            fi
        fi
    done
    
    if [[ $found -eq 0 ]]; then
        echo "✅ No nuclear keywords found in axiom files"
        echo "Ready for Phase 2"
    else
        echo ""
        echo "⚠️  Nuclear keywords still present. Refactor before Phase 2."
    fi
}

phase2_create_axiom() {
    echo "=== Phase 2: Create axiom Repository ==="
    echo ""
    
    # Check if axiom repo exists on GitHub
    echo "Checking if axiom repo exists..."
    if ! gh repo view benjaminbooth/axiom &>/dev/null; then
        echo "Creating benjaminbooth/axiom on GitHub..."
        gh repo create benjaminbooth/axiom --public \
            --description "Generic LLM/RAG platform framework" \
            --license MIT
    else
        echo "benjaminbooth/axiom already exists"
    fi
    
    # Create temp directory for extraction
    echo ""
    echo "Creating temporary extraction directory..."
    rm -rf "$AXIOM_TEMP"
    mkdir -p "$AXIOM_TEMP"
    
    # Clone current repo
    echo "Cloning current repo..."
    git clone "$PROJECT_ROOT" "$AXIOM_TEMP/neutron-os-clone"
    cd "$AXIOM_TEMP/neutron-os-clone"
    
    # Create paths file for git-filter-repo
    echo "Creating paths file..."
    printf '%s\n' "${AXIOM_PATHS[@]}" > "$AXIOM_TEMP/axiom-paths.txt"
    
    # Check if git-filter-repo is installed
    if ! command -v git-filter-repo &>/dev/null; then
        echo ""
        echo "⚠️  git-filter-repo not installed"
        echo "Install with: brew install git-filter-repo"
        echo ""
        echo "Manual alternative:"
        echo "1. Create fresh axiom repo"
        echo "2. Copy axiom files manually"
        echo "3. Rename neutron_os → axiom"
        exit 1
    fi
    
    echo "Running git-filter-repo..."
    git filter-repo --paths-from-file "$AXIOM_TEMP/axiom-paths.txt" --force
    
    echo ""
    echo "Renaming package: neutron_os → axiom"
    
    # Rename directory
    if [[ -d "src/neutron_os" ]]; then
        mv src/neutron_os src/axiom
    fi
    
    # Update imports in Python files
    find . -name "*.py" -type f -exec sed -i '' \
        -e 's/from neutron_os/from axiom/g' \
        -e 's/import neutron_os/import axiom/g' \
        -e 's/neutron_os\./axiom./g' \
        -e 's/"neutron_os"/"axiom"/g' \
        {} +

    # Update TOML config files (pyproject.toml, neut-extension.toml, etc.)
    find . -name "*.toml" -type f -exec sed -i '' \
        -e 's/neutron-os/axiom/g' \
        -e 's/neutron_os/axiom/g' \
        {} +

    # Update YAML files
    find . -name "*.yaml" -name "*.yml" -type f -exec sed -i '' \
        -e 's/neutron_os/axiom/g' \
        {} +
    
    echo ""
    echo "Creating axiom pyproject.toml..."
    cat > pyproject.toml << 'EOF'
[project]
name = "axiom"
version = "0.1.0"
description = "Generic LLM/RAG platform framework"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"

dependencies = [
    "pyyaml>=6.0",
    "argcomplete>=3.0",
    "tomlkit>=0.13",
]

[project.optional-dependencies]
publisher = ["python-docx>=1.1"]
rag = [
    "psycopg2-binary>=2.9",
    "requests>=2.28",
    "watchdog>=3.0",
]
signal = [
    "psycopg2-binary>=2.9",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "pgvector>=0.2",
]
repos = [
    "PyGithub>=2.0",
    "python-gitlab>=4.0",
]
browser = ["playwright>=1.40"]
chat = [
    "rich>=13.0",
    "prompt-toolkit>=3.0",
    "pygments>=2.17",
]
mcp = ["mcp>=1.0"]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.0",
    "ruff>=0.4",
    "pyright>=1.1",
]
all = [
    "axiom[publisher,rag,signal,repos,chat,mcp,dev]",
]

[project.scripts]
axiom = "axiom.neut_cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/axiom"]

[tool.pytest.ini_options]
testpaths = ["tests", "src/axiom/extensions/builtins"]
pythonpath = ["src"]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]
ignore = [
    "E501", "SIM108", "SIM105", "SIM102", "SIM117", "SIM115",
    "UP042", "B904", "B027", "B007", "B905", "B023", "SIM103",
]

[tool.ruff.lint.isort]
known-first-party = ["axiom"]

[tool.pyright]
pythonVersion = "3.11"
pythonPlatform = "All"
typeCheckingMode = "standard"
reportMissingImports = "warning"
reportMissingModuleSource = false
EOF
    
    echo ""
    echo "Creating axiom README.md..."
    cat > README.md << 'EOF'
# axiom

A generic LLM/RAG platform framework for building AI-powered applications.

## Features

- LLM gateway with multi-provider routing and fallback
- RAG (Retrieval Augmented Generation) with pgvector
- CLI framework with extension discovery
- State management with atomic writes and PostgreSQL backend
- Audit logging with HMAC tamper detection
- Human-in-the-loop approval workflows (RACI framework)
- Document publishing pipeline
- Interactive review system

## Installation

```bash
pip install axiom
# or
pip install git+https://github.com/benjaminbooth/axiom.git
```

## Usage

```bash
axiom --help
```

## License

MIT License - see LICENSE file.

## Acknowledgments

This software was developed at The University of Texas at Austin.
Released as open source under the MIT License with approval from
UT Austin Discovery to Impact.
EOF
    
    # Commit changes
    git add -A
    git commit -m "Rename package: neutron_os → axiom" || true
    
    echo ""
    echo "=== axiom repository prepared at: $AXIOM_TEMP/neutron-os-clone ==="
    echo ""
    echo "Next steps:"
    echo "1. Review the extracted repo"
    echo "2. Run: cd $AXIOM_TEMP/neutron-os-clone && git remote set-url origin $AXIOM_REPO"
    echo "3. Run: git push -u origin main"
}

phase3_update_neutronos() {
    echo "=== Phase 3: Update neutron-os Repository ==="
    echo ""
    echo "This phase removes axiom files from neutron-os and adds axiom dependency."
    echo ""
    
    cd "$PROJECT_ROOT"
    
    echo "Files to remove from neutron-os (now in axiom):"
    for path in "${AXIOM_PATHS[@]}"; do
        if [[ -e "$path" ]]; then
            echo "  - $path"
        fi
    done
    
    echo ""
    echo "⚠️  This is destructive. Run with --execute to perform removal."
    echo "    $0 phase3 --execute"
    
    if [[ "${1:-}" == "--execute" ]]; then
        echo ""
        echo "Removing axiom files..."
        for path in "${AXIOM_PATHS[@]}"; do
            if [[ -e "$path" ]]; then
                git rm -rf "$path" 2>/dev/null || rm -rf "$path"
                echo "  Removed: $path"
            fi
        done
        
        echo ""
        echo "Updating pyproject.toml..."
        # Add axiom dependency
        if grep -q "dependencies" pyproject.toml; then
            sed -i '' '/dependencies = \[/a\
    "axiom @ git+https://github.com/benjaminbooth/axiom.git",
' pyproject.toml
        fi
        
        echo ""
        echo "✅ neutron-os updated"
        echo "Commit and push changes to GitLab"
    fi
}

phase4_mirroring() {
    echo "=== Phase 4: Configure Mirroring ==="
    echo ""
    echo "Manual steps required:"
    echo ""
    echo "1. TACC GitLab - Create axiom mirror:"
    echo "   a. Go to rsicc-gitlab.tacc.utexas.edu"
    echo "   b. Create new project: axiom"
    echo "   c. Settings → Repository → Mirroring repositories"
    echo "   d. Add: https://github.com/benjaminbooth/axiom.git"
    echo "   e. Direction: Pull"
    echo "   f. Authentication: None (public repo)"
    echo ""
    echo "2. Verify neutron-os mirror (existing):"
    echo "   a. Check rsicc-gitlab/neutron-os-core settings"
    echo "   b. Confirm push mirror to GitHub is active"
    echo ""
    echo "3. Test both directions:"
    echo "   a. Push to GitHub axiom → verify GitLab syncs"
    echo "   b. Push to GitLab neutron-os → verify GitHub syncs"
}

verify() {
    echo "=== Verification ==="
    echo ""
    
    if [[ -d "$AXIOM_TEMP/neutron-os-clone" ]]; then
        echo "Checking axiom repo for nuclear keywords..."
        cd "$AXIOM_TEMP/neutron-os-clone"
        
        matches=$(grep -riE "$NUCLEAR_KEYWORDS" . \
            --include="*.py" \
            --include="*.toml" \
            --include="*.md" \
            --exclude-dir=".git" 2>/dev/null || true)
        
        if [[ -n "$matches" ]]; then
            echo "❌ Nuclear keywords found in axiom:"
            echo "$matches"
        else
            echo "✅ No nuclear keywords in axiom repo"
        fi
    else
        echo "axiom temp repo not found. Run phase2 first."
    fi
}

# Main
case "${1:-help}" in
    phase1)
        phase1_prepare
        ;;
    verify-local)
        phase1_verify_local
        ;;
    phase2)
        phase2_create_axiom
        ;;
    phase3)
        phase3_update_neutronos "${2:-}"
        ;;
    phase4)
        phase4_mirroring
        ;;
    verify)
        verify
        ;;
    help|*)
        echo "Codebase Split Script"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  phase1       Identify nuclear content in generic files"
        echo "  verify-local Verify axiom files are clean before extraction"
        echo "  phase2       Create axiom repo and extract generic code"
        echo "  phase3       Update neutron-os (remove axiom files)"
        echo "  phase4       Configure GitLab mirroring (instructions)"
        echo "  verify       Verify axiom repo has no nuclear keywords"
        ;;
esac

#!/usr/bin/env bash
# NeutronOS Bootstrap Script
# Run this once after cloning to set up your development environment.
#
# Usage: source ./scripts/bootstrap.sh
#        (or: . ./scripts/bootstrap.sh)
#
# This script:
# 1. Creates/updates the Python virtual environment
# 2. Installs the neut package in editable mode
# 3. Installs direnv for auto-activation (if not present)
#
# After running, `neut` commands will "just work" in this directory.

# Strict mode: only when executed as a subprocess (./scripts/bootstrap.sh).
# When sourced, set -e / -o pipefail corrupt zsh completion widgets — any
# internal function that returns non-zero silently breaks the completion
# system in ways compinit cannot repair.  So we skip strict mode entirely
# for the sourced path.

_BOOTSTRAP_SOURCED=false   # default; overwritten below per-shell

# Helper to restore shell options (call before early returns when sourced)
_bootstrap_cleanup() {
    unset _BOOTSTRAP_SOURCED _SCRIPT_PATH _CURRENT_SHELL 2>/dev/null || true
}

# Detect shell and whether script is being sourced
# This must work in bash, zsh, ksh, dash, and other POSIX shells
_BOOTSTRAP_SOURCED=false
_SCRIPT_PATH=""

# Detect current shell
_CURRENT_SHELL=""
if [ -n "${BASH_VERSION:-}" ]; then
    _CURRENT_SHELL="bash"
elif [ -n "${ZSH_VERSION:-}" ]; then
    _CURRENT_SHELL="zsh"
elif [ -n "${KSH_VERSION:-}" ]; then
    _CURRENT_SHELL="ksh"
else
    _CURRENT_SHELL="sh"
fi

# Determine script path and whether sourced (shell-specific)
case "$_CURRENT_SHELL" in
    bash)
        _SCRIPT_PATH="${BASH_SOURCE[0]}"
        if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
            _BOOTSTRAP_SOURCED=true
        fi
        ;;
    zsh)
        # In zsh, use ZSH_EVAL_CONTEXT to detect sourcing
        # "file" = sourced, "toplevel:file" = also sourced
        if [[ "${ZSH_EVAL_CONTEXT:-}" == *:file* ]] || [[ "${ZSH_EVAL_CONTEXT:-}" == file ]]; then
            _BOOTSTRAP_SOURCED=true
        fi
        # In zsh, $0 is the script path when sourced or executed
        _SCRIPT_PATH="${0}"
        ;;
    ksh)
        # ksh doesn't have a reliable way to detect sourcing; assume executed
        # Note: ksh93's .sh.file can't be used here (syntax invalid in bash/zsh)
        _SCRIPT_PATH="$0"
        ;;
    *)
        # POSIX sh - no reliable source detection
        _SCRIPT_PATH="$0"
        ;;
esac

# Handle case where _SCRIPT_PATH is empty or just a name without path
if [[ -z "$_SCRIPT_PATH" ]] || [[ "$_SCRIPT_PATH" == "bash" ]] || [[ "$_SCRIPT_PATH" == "zsh" ]] || [[ "$_SCRIPT_PATH" == "-bash" ]] || [[ "$_SCRIPT_PATH" == "-zsh" ]]; then
    # Fallback: try to find bootstrap.sh relative to current dir
    if [[ -f "./scripts/bootstrap.sh" ]]; then
        _SCRIPT_PATH="./scripts/bootstrap.sh"
    elif [[ -f "./bootstrap.sh" ]]; then
        _SCRIPT_PATH="./bootstrap.sh"
    else
        echo "⚠️  Could not determine script location. Run from Neutron_OS directory." >&2
        if [[ "$_BOOTSTRAP_SOURCED" == true ]]; then
            _bootstrap_cleanup
            return 1
        else
            exit 1
        fi
    fi
fi

SCRIPT_DIR="$(cd "$(dirname "$_SCRIPT_PATH")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Use parent .venv if it already exists (shared workspace layout),
# otherwise create .venv inside the project root (standalone clone).
if [[ -d "${PROJECT_ROOT}/../.venv" ]]; then
    VENV_PATH="${PROJECT_ROOT}/../.venv"
else
    VENV_PATH="${PROJECT_ROOT}/.venv"
fi

# Parse args
for arg in "$@"; do
    case $arg in
        -h|--help)
            echo "Usage: source ./scripts/bootstrap.sh"
            echo ""
            echo "Sets up Python venv, installs neut, and configures direnv."
            echo "Using 'source' ensures 'neut' works immediately."
            if [[ "$_BOOTSTRAP_SOURCED" == true ]]; then
                _bootstrap_cleanup
                return 0
            else
                exit 0
            fi
            ;;
    esac
done

# Enable strict mode only when executed (not sourced) — see comment at top.
if [[ "$_BOOTSTRAP_SOURCED" != true ]]; then
    set -eo pipefail
fi

echo "🔧 NeutronOS Bootstrap"
echo "======================"

# ═══════════════════════════════════════════════════════════════════════════
# 1. Python Virtual Environment
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo "Step 1: Python Environment"
echo "--------------------------"

if [[ ! -d "$VENV_PATH" ]]; then
    echo "Creating virtual environment at $VENV_PATH..."
    python3 -m venv "$VENV_PATH"
else
    echo "Virtual environment exists at $VENV_PATH"
fi

# Activate venv
source "$VENV_PATH/bin/activate"

# Upgrade pip quietly
pip install -q --upgrade pip

# ═══════════════════════════════════════════════════════════════════════════
# 2. Install Package
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo "Step 2: Installing neut package"
echo "--------------------------------"

cd "$PROJECT_ROOT"

# Install package with dependencies
pip install -q -e ".[all]"

# Clear shell hash table (fixes stale command caching)
hash -r 2>/dev/null || true

# IMPORTANT: Replace pip's entry point with our self-healing shell wrapper
# This ensures `neut` always works, even if pip entry points get stale
NEUT_SCRIPT="$VENV_PATH/bin/neut"
SHELL_WRAPPER="$SCRIPT_DIR/neut"

if [[ -f "$SHELL_WRAPPER" ]]; then
    # Copy our reliable shell wrapper over pip's entry point
    cp "$SHELL_WRAPPER" "$NEUT_SCRIPT"
    chmod +x "$NEUT_SCRIPT"
    echo "✓ neut command installed (self-healing shell wrapper)"
else
    # Fallback: validate pip entry point if wrapper doesn't exist
    if [[ -f "$NEUT_SCRIPT" ]]; then
        if grep -q "from tools.neut_cli import main" "$NEUT_SCRIPT"; then
            echo "✓ neut command installed (pip entry point)"
        else
            echo "⚠ neut entry point may be stale. Run: pip install --force-reinstall -e ."
        fi
    else
        echo "⚠ neut script not created. Run: pip install -e ."
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════
# 2.5. Shell Tab Completion
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo "Step 2.5: Tab Completion"
echo "------------------------"

_COMPLETION_DIR="$HOME/.config/neut"
_COMPLETION_FILE="$_COMPLETION_DIR/neut-completion.zsh"

if command -v register-python-argcomplete &>/dev/null; then
    # Generate static completion file (no venv dependency at shell startup)
    # Activated at end of bootstrap after cleanup restores clean shell state
    mkdir -p "$_COMPLETION_DIR"
    register-python-argcomplete neut > "$_COMPLETION_FILE" 2>/dev/null || true
    echo "✓ Tab completion generated at $_COMPLETION_FILE"

    # Persist sourcing in shell config
    shell_config=""
    case "${_CURRENT_SHELL:-}" in
        zsh)  shell_config="$HOME/.zshrc" ;;
        bash)
            if [[ -f "$HOME/.bash_profile" ]] && [[ "$(uname)" == "Darwin" ]]; then
                shell_config="$HOME/.bash_profile"
            else
                shell_config="$HOME/.bashrc"
            fi
            ;;
    esac

    if [[ -n "$shell_config" ]] && [[ -f "$shell_config" ]]; then
        # Remove old-style argcomplete lines (eval-based)
        if grep -q 'register-python-argcomplete neut' "$shell_config" 2>/dev/null; then
            sed -i '' '/register-python-argcomplete neut/d' "$shell_config"
            sed -i '' '/# neut CLI tab completion/d' "$shell_config"
        fi

        # Write static source line if not already present
        if ! grep -q 'neut-completion.zsh' "$shell_config" 2>/dev/null; then
            echo '' >> "$shell_config"
            echo '# neut CLI tab completion (generated by bootstrap.sh)' >> "$shell_config"
            echo '[[ -f ~/.config/neut/neut-completion.zsh ]] && source ~/.config/neut/neut-completion.zsh' >> "$shell_config"
            echo "✓ Tab completion added to $shell_config"
        else
            echo "✓ Tab completion already in $shell_config"
        fi
    fi
else
    echo "○ argcomplete not found (tab completion unavailable)"
    echo "  Run: pip install argcomplete"
fi

# ═══════════════════════════════════════════════════════════════════════════
# 3. direnv Setup (makes neut "just work")
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo "Step 3: direnv Auto-Activation"
echo "------------------------------"

setup_direnv() {
    local shell_config=""
    local shell_name=""
    local hook_cmd=""
    
    # Detect shell from running shell first, then default shell
    case "${_CURRENT_SHELL:-}" in
        zsh)
            shell_config="$HOME/.zshrc"
            shell_name="zsh"
            hook_cmd='eval "$(direnv hook zsh)"'
            ;;
        bash)
            # macOS: .bash_profile is more common; Linux: .bashrc
            if [[ -f "$HOME/.bash_profile" ]] && [[ "$(uname)" == "Darwin" ]]; then
                shell_config="$HOME/.bash_profile"
            else
                shell_config="$HOME/.bashrc"
            fi
            shell_name="bash"
            hook_cmd='eval "$(direnv hook bash)"'
            ;;
        ksh)
            shell_config="$HOME/.kshrc"
            shell_name="ksh"
            hook_cmd='eval "$(direnv hook ksh)"'
            ;;
        *)
            # Fallback to SHELL env var
            case "$SHELL" in
                */zsh)
                    shell_config="$HOME/.zshrc"
                    shell_name="zsh"
                    hook_cmd='eval "$(direnv hook zsh)"'
                    ;;
                */bash)
                    if [[ -f "$HOME/.bash_profile" ]] && [[ "$(uname)" == "Darwin" ]]; then
                        shell_config="$HOME/.bash_profile"
                    else
                        shell_config="$HOME/.bashrc"
                    fi
                    shell_name="bash"
                    hook_cmd='eval "$(direnv hook bash)"'
                    ;;
                */fish)
                    shell_config="$HOME/.config/fish/config.fish"
                    shell_name="fish"
                    hook_cmd='direnv hook fish | source'
                    ;;
                */ksh*)
                    shell_config="$HOME/.kshrc"
                    shell_name="ksh"
                    hook_cmd='eval "$(direnv hook ksh)"'
                    ;;
                *)
                    echo "⚠ Could not detect shell config file for: $SHELL"
                    echo "  See https://direnv.net/docs/hook.html for manual setup"
                    return 1
                    ;;
            esac
            ;;
    esac
    
    if [[ -z "$shell_config" ]]; then
        echo "⚠ Could not detect shell config file"
        return 1
    fi
    
    # Create config file if it doesn't exist
    if [[ ! -f "$shell_config" ]]; then
        mkdir -p "$(dirname "$shell_config")"
        touch "$shell_config"
    fi
    
    # Silence direnv output persistently
    if ! grep -q 'DIRENV_LOG_FORMAT=""' "$shell_config" 2>/dev/null; then
        # Insert before the direnv hook if it exists, otherwise add both together
        if grep -q 'direnv hook' "$shell_config" 2>/dev/null; then
            sed -i '' '/direnv hook/i\
export DIRENV_LOG_FORMAT=""' "$shell_config"
            echo "✓ Added DIRENV_LOG_FORMAT silencing to $shell_config"
        fi
    fi

    # Check if direnv hook already configured
    if grep -q 'direnv hook' "$shell_config" 2>/dev/null; then
        echo "✓ direnv hook already in $shell_config"
    else
        echo "Adding direnv hook to $shell_config..."
        echo '' >> "$shell_config"
        echo '# direnv for auto-activating project environments' >> "$shell_config"
        echo 'export DIRENV_LOG_FORMAT=""' >> "$shell_config"
        echo "$hook_cmd" >> "$shell_config"
        echo "✓ Added direnv hook to $shell_config"
        echo "  (Run 'source $shell_config' or open a new terminal)"
    fi
}

if command -v direnv &>/dev/null; then
    echo "✓ direnv already installed"
elif command -v brew &>/dev/null; then
    echo "Installing direnv via Homebrew..."
    brew install direnv
elif command -v apt-get &>/dev/null; then
    echo "Installing direnv via apt..."
    sudo apt-get update && sudo apt-get install -y direnv
else
    echo "⚠ direnv not installed (no brew/apt found)"
    echo "  Install manually: https://direnv.net/docs/installation.html"
fi

# Configure direnv if available
if command -v direnv &>/dev/null; then
    setup_direnv

    # Whitelist the project so future .envrc changes are auto-trusted
    # (prevents "direnv: .envrc is blocked" after git pull)
    direnv_toml="$HOME/.config/direnv/direnv.toml"
    if [[ ! -f "$direnv_toml" ]] || ! grep -q "$PROJECT_ROOT" "$direnv_toml" 2>/dev/null; then
        mkdir -p "$(dirname "$direnv_toml")"
        if [[ ! -f "$direnv_toml" ]]; then
            cat > "$direnv_toml" <<TOML
[whitelist]
prefix = ["$PROJECT_ROOT"]
TOML
            echo "✓ Created direnv whitelist for $PROJECT_ROOT"
        else
            # Append project to existing whitelist (or create section)
            if grep -q '\[whitelist\]' "$direnv_toml" 2>/dev/null; then
                # Add to existing prefix array
                sed -i '' "/^prefix = \[/s|\]|, \"$PROJECT_ROOT\"\]|" "$direnv_toml"
            else
                echo '' >> "$direnv_toml"
                echo '[whitelist]' >> "$direnv_toml"
                echo "prefix = [\"$PROJECT_ROOT\"]" >> "$direnv_toml"
            fi
            echo "✓ Added $PROJECT_ROOT to direnv whitelist"
        fi
    fi

    if [[ -f "$PROJECT_ROOT/.envrc" ]]; then
        DIRENV_LOG_FORMAT="" direnv allow "$PROJECT_ROOT" 2>/dev/null || true
        echo "✓ .envrc allowed (environment will auto-activate)"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════
# 4. Optional Dev Dependencies
# ═══════════════════════════════════════════════════════════════════════════
if [[ -f "$PROJECT_ROOT/requirements-dev.txt" ]]; then
    echo ""
    echo "Step 4: Dev dependencies"
    echo "------------------------"
    pip install -q -r "$PROJECT_ROOT/requirements-dev.txt"
    echo "✓ Dev dependencies installed"
fi

# ═══════════════════════════════════════════════════════════════════════════
# 5. Infrastructure (Docker, K3D, PostgreSQL)
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo "Step 5: Infrastructure"
echo "----------------------"

# Check if Docker is available
if command -v docker &>/dev/null; then
    # Check if Docker daemon is running
    if docker info &>/dev/null 2>&1; then
        echo "✓ Docker running"
        
        # Check K3D
        if command -v k3d &>/dev/null; then
            echo "✓ K3D installed"
            
            # Check if neut-local cluster exists and is running
            if k3d cluster list -o json 2>/dev/null | grep -q '"neut-local"'; then
                if k3d cluster list -o json 2>/dev/null | grep -A5 '"neut-local"' | grep -q '"serversRunning":1'; then
                    echo "✓ neut-local cluster running"
                else
                    echo "○ neut-local cluster stopped, starting..."
                    k3d cluster start neut-local 2>/dev/null || true
                fi
            else
                echo "○ Creating neut-local cluster with PostgreSQL..."
                # Run neut infra to set up the cluster
                neut infra --no-cluster 2>/dev/null || {
                    echo "  (Run 'neut infra' to complete setup)"
                }
            fi
        else
            echo "○ K3D not installed, installing..."
            if command -v brew &>/dev/null; then
                brew install k3d 2>/dev/null && echo "✓ K3D installed" || echo "  (Run 'neut infra' to install)"
            else
                curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash 2>/dev/null && echo "✓ K3D installed" || echo "  (Run 'neut infra' to install)"
            fi
        fi
    else
        echo "○ Docker not running"
        echo "  Starting Docker Desktop..."
        if [[ "$(uname)" == "Darwin" ]]; then
            open -a Docker 2>/dev/null || true
            echo "  (Waiting for Docker to start, then run bootstrap again)"
        else
            echo "  (Start Docker, then run bootstrap again)"
        fi
    fi
else
    echo "○ Docker not installed"
    echo "  Docker Desktop is required for local PostgreSQL."
    echo "  Download: https://www.docker.com/products/docker-desktop/"
    if [[ "$(uname)" == "Darwin" ]]; then
        read -r -p "  Open download page? [Y/n] " response
        if [[ "$response" =~ ^[Yy]?$ ]]; then
            open "https://www.docker.com/products/docker-desktop/" 2>/dev/null || true
        fi
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════
# 6. Summary
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "✅ Bootstrap Complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Try:"
echo "  neut status                 # Check system health"
echo "  neut sense brief            # Catch up on what happened"
echo "  neut chat                   # Interactive agent"
echo ""

# Clear shell command cache so 'neut' resolves to the new script
if [[ "$_BOOTSTRAP_SOURCED" == true ]]; then
    # Different shells have different cache clearing commands
    case "$_CURRENT_SHELL" in
        zsh)
            rehash 2>/dev/null || hash -r 2>/dev/null || true
            ;;
        bash|ksh|*)
            hash -r 2>/dev/null || true
            ;;
    esac
else
    # Script was executed, not sourced — cache clear won't help the parent shell
    echo "💡 Tip: The script was executed (not sourced)."
    case "$_CURRENT_SHELL" in
        zsh)
            echo "   Run 'rehash' or open a new terminal if 'neut' doesn't work."
            ;;
        *)
            echo "   Run 'hash -r' or open a new terminal if 'neut' doesn't work."
            ;;
    esac
    echo ""
fi

# ═══════════════════════════════════════════════════════════════════════════
# Cleanup: Restore zsh completion state (critical when sourced!)
# ═══════════════════════════════════════════════════════════════════════════

if [[ "$_BOOTSTRAP_SOURCED" == true ]]; then
    # Rehash so zsh finds the newly installed neut command.
    rehash 2>/dev/null || hash -r 2>/dev/null || true

    # Rebuild zsh completion system.  A previous sourcing of this script
    # (or set -e leaking from an older version) may have corrupted widget
    # state, so we do a full compinit + explicit Tab rebind.
    if [[ -n "${ZSH_VERSION:-}" ]]; then
        autoload -Uz compinit && compinit 2>/dev/null
        bindkey '^I' expand-or-complete 2>/dev/null
        [[ -f "$HOME/.config/neut/neut-completion.zsh" ]] && \
            source "$HOME/.config/neut/neut-completion.zsh" 2>/dev/null || true
    fi

    _bootstrap_cleanup
fi
unset -f _bootstrap_cleanup 2>/dev/null || true

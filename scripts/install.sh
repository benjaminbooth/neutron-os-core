#!/usr/bin/env bash
# Neutron OS — One-Line Installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/benjaminbooth/neutron-os-core/main/scripts/install.sh | bash
#
# What this does:
#   1. Installs the `neut` CLI via pipx (manages its own isolated venv)
#   2. Falls back to pip --user if pipx is unavailable
#   3. Adds the install location to your PATH if needed
#   4. Verifies the installation
#
# Requirements:
#   - Python 3.10+
#   - git
#   - pipx (recommended) or pip
#
# To update later:
#   pipx upgrade neutron-os
#   # or: pipx install --force "git+https://github.com/benjaminbooth/neutron-os-core.git"

set -euo pipefail

# --- Configuration -----------------------------------------------------------

GITHUB_REPO="https://github.com/benjaminbooth/neutron-os-core.git"
PACKAGE_NAME="neutron-os"
INSTALL_DIR="${HOME}/.local/bin"

# --- Colors (if terminal supports them) --------------------------------------

if [ -t 1 ]; then
    BOLD="\033[1m"
    DIM="\033[2m"
    CYAN="\033[36m"
    GREEN="\033[32m"
    RED="\033[31m"
    YELLOW="\033[33m"
    RESET="\033[0m"
else
    BOLD="" DIM="" CYAN="" GREEN="" RED="" YELLOW="" RESET=""
fi

info()  { echo -e "  ${CYAN}>${RESET} $*"; }
ok()    { echo -e "  ${GREEN}✓${RESET} $*"; }
warn()  { echo -e "  ${YELLOW}!${RESET} $*"; }
err()   { echo -e "  ${RED}✗${RESET} $*" >&2; }
dim()   { echo -e "  ${DIM}$*${RESET}"; }

# --- Preflight ---------------------------------------------------------------

echo
echo -e "  ${BOLD}Neutron OS Installer${RESET}"
echo -e "  ${DIM}────────────────────${RESET}"
echo

# Check Python
if ! command -v python3 &>/dev/null; then
    err "Python 3 not found. Install Python 3.10+ first."
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    err "Python 3.10+ required (found $PY_VERSION)"
    exit 1
fi
ok "Python $PY_VERSION"

# Check git
if ! command -v git &>/dev/null; then
    err "git not found. Install git first (brew install git)."
    exit 1
fi
ok "git available"

# --- Install -----------------------------------------------------------------

if command -v pipx &>/dev/null; then
    ok "pipx available"
    echo
    info "Installing ${PACKAGE_NAME} via pipx..."
    echo
    pipx install "git+${GITHUB_REPO}" \
        2>&1 | while IFS= read -r line; do dim "$line"; done
    INSTALL_DIR="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "${HOME}/.local/bin")"
else
    warn "pipx not found — falling back to pip install --user"
    warn "For a cleaner setup, install pipx first: brew install pipx"
    echo

    if ! python3 -m pip --version &>/dev/null; then
        err "pip not found either. Install pipx: brew install pipx"
        exit 1
    fi

    info "Installing ${PACKAGE_NAME} via pip..."
    echo
    python3 -m pip install --user --upgrade \
        "git+${GITHUB_REPO}" \
        2>&1 | while IFS= read -r line; do dim "$line"; done

    # Resolve actual user scripts dir (may differ from ~/.local/bin on macOS)
    USER_BIN=$(python3 -c "import sysconfig; print(sysconfig.get_path('scripts', 'posix_user'))" 2>/dev/null || echo "${HOME}/.local/bin")
    INSTALL_DIR="$USER_BIN"
fi

echo
ok "Package installed"

# --- PATH setup --------------------------------------------------------------

NEEDS_PATH=false
if ! echo "$PATH" | tr ':' '\n' | grep -qx "${INSTALL_DIR}"; then
    NEEDS_PATH=true
fi

if $NEEDS_PATH; then
    SHELL_NAME=$(basename "${SHELL:-/bin/bash}")
    case "$SHELL_NAME" in
        zsh)  RC_FILE="$HOME/.zshrc" ;;
        bash) RC_FILE="$HOME/.bashrc" ;;
        fish) RC_FILE="$HOME/.config/fish/config.fish" ;;
        *)    RC_FILE="$HOME/.profile" ;;
    esac

    PATH_LINE="export PATH=\"${INSTALL_DIR}:\$PATH\""
    if [ "$SHELL_NAME" = "fish" ]; then
        PATH_LINE="set -gx PATH ${INSTALL_DIR} \$PATH"
    fi

    if ! grep -qF "${INSTALL_DIR}" "$RC_FILE" 2>/dev/null; then
        echo "" >> "$RC_FILE"
        echo "# Neutron OS CLI" >> "$RC_FILE"
        echo "$PATH_LINE" >> "$RC_FILE"
        ok "Added ${INSTALL_DIR} to PATH in ${RC_FILE}"
    else
        ok "PATH already configured in ${RC_FILE}"
    fi

    export PATH="${INSTALL_DIR}:$PATH"
    info "Run: ${CYAN}source ${RC_FILE}${RESET}  (or open a new terminal)"
else
    ok "PATH already includes ${INSTALL_DIR}"
fi

# --- Verify ------------------------------------------------------------------

echo
if command -v neut &>/dev/null; then
    NEUT_VERSION=$(neut --version 2>/dev/null || echo "unknown")
    ok "neut ${NEUT_VERSION} installed successfully"
    echo
    dim "Try it:"
    dim "  neut --help"
    dim "  neut chat"
    dim "  neut sense status"
else
    if [ -f "${INSTALL_DIR}/neut" ]; then
        ok "neut installed to ${INSTALL_DIR}/neut"
        info "Open a new terminal or run: source ${RC_FILE:-~/.zshrc}"
    else
        err "Installation completed but 'neut' not found on PATH"
        dim "Check: python3 -m pip show ${PACKAGE_NAME}"
        dim "Source: ${GITHUB_REPO}"
    fi
fi
echo

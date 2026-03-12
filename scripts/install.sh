#!/usr/bin/env bash
# Neutron OS — One-Line Installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/benjaminbooth/neutron-os-core/main/scripts/install.sh | bash
#
# What this does:
#   1. Installs the `neut` CLI from PyPI
#   2. Adds ~/.local/bin to your PATH (if not already there)
#   3. Verifies the installation
#
# Requirements:
#   - Python 3.10+
#   - pip (usually bundled with Python)
#
# To update later:
#   neut self-update    (or: pip install --upgrade neutron-os --index-url ...)

set -euo pipefail

# --- Configuration -----------------------------------------------------------


# Install from PyPI — no project ID needed
PACKAGE_INDEX="https://pypi.org/simple"
PACKAGE_NAME="neutron-os"
INSTALL_DIR="${HOME}/.local/bin"

# --- Colors (if terminal supports them) --------------------------------------

if [ -t 1 ]; then
    BOLD="\033[1m"
    DIM="\033[2m"
    CYAN="\033[36m"
    GREEN="\033[32m"
    RED="\033[31m"
    RESET="\033[0m"
else
    BOLD="" DIM="" CYAN="" GREEN="" RED="" RESET=""
fi

info()  { echo -e "  ${CYAN}>${RESET} $*"; }
ok()    { echo -e "  ${GREEN}v${RESET} $*"; }
err()   { echo -e "  ${RED}x${RESET} $*" >&2; }
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

# Check pip
if ! python3 -m pip --version &>/dev/null; then
    err "pip not found. Install pip first: python3 -m ensurepip"
    exit 1
fi
ok "pip available"

# --- Install -----------------------------------------------------------------

info "Installing ${PACKAGE_NAME} from PyPI..."
echo

python3 -m pip install --user --upgrade \
    --index-url "${PACKAGE_INDEX}" \

    "${PACKAGE_NAME}" \
    2>&1 | while IFS= read -r line; do dim "  $line"; done

echo
ok "Package installed"

# --- PATH setup --------------------------------------------------------------

NEEDS_PATH=false
if ! echo "$PATH" | tr ':' '\n' | grep -qx "${INSTALL_DIR}"; then
    NEEDS_PATH=true
fi

# Also check Python's user base bin (may differ from ~/.local/bin)
USER_BIN=$(python3 -c "import sysconfig; print(sysconfig.get_path('scripts', 'posix_user'))" 2>/dev/null || echo "")
if [ -n "$USER_BIN" ] && [ "$USER_BIN" != "$INSTALL_DIR" ]; then
    if ! echo "$PATH" | tr ':' '\n' | grep -qx "${USER_BIN}"; then
        INSTALL_DIR="$USER_BIN"
        NEEDS_PATH=true
    fi
fi

if $NEEDS_PATH; then
    # Detect shell config file
    SHELL_NAME=$(basename "${SHELL:-/bin/bash}")
    case "$SHELL_NAME" in
        zsh)  RC_FILE="$HOME/.zshrc" ;;
        bash) RC_FILE="$HOME/.bashrc" ;;
        fish) RC_FILE="$HOME/.config/fish/config.fish" ;;
        *)    RC_FILE="$HOME/.profile" ;;
    esac

    # Check if PATH line already exists in rc file
    PATH_LINE="export PATH=\"${INSTALL_DIR}:\$PATH\""
    if [ "$SHELL_NAME" = "fish" ]; then
        PATH_LINE="set -gx PATH ${INSTALL_DIR} \$PATH"
    fi

    if ! grep -qF "${INSTALL_DIR}" "$RC_FILE" 2>/dev/null; then
        echo "" >> "$RC_FILE"
        echo "# Neutron OS CLI" >> "$RC_FILE"
        echo "$PATH_LINE" >> "$RC_FILE"
        ok "Added ${INSTALL_DIR} to PATH in ${RC_FILE}"
        info "Run: ${CYAN}source ${RC_FILE}${RESET}  (or open a new terminal)"
    else
        ok "PATH already configured in ${RC_FILE}"
    fi

    # Make it available in this session too
    export PATH="${INSTALL_DIR}:$PATH"
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
    # Binary might not be on PATH yet in this shell session
    if [ -f "${INSTALL_DIR}/neut" ]; then
        ok "neut installed to ${INSTALL_DIR}/neut"
        info "Open a new terminal or run: source ${RC_FILE:-~/.zshrc}"
    else
        err "Installation completed but 'neut' not found on PATH"
        dim "Check: python3 -m pip show ${PACKAGE_NAME}"
    fi
fi
echo

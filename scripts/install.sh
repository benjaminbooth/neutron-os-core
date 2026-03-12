#!/usr/bin/env bash
# Neutron OS — One-Line Installer
#
# Install:
#   curl -fsSL https://raw.githubusercontent.com/benjaminbooth/neutron-os-core/main/scripts/install.sh | bash
#
# Uninstall:
#   curl -fsSL https://raw.githubusercontent.com/benjaminbooth/neutron-os-core/main/scripts/install.sh | bash -s -- --uninstall
#
# Update:
#   curl -fsSL https://raw.githubusercontent.com/benjaminbooth/neutron-os-core/main/scripts/install.sh | bash
#
# What this does:
#   1. Creates an isolated venv at ~/.neut/venv
#   2. Installs neut into it from the public GitHub mirror
#   3. Symlinks the neut binary to ~/.local/bin
#   4. Adds ~/.local/bin to your PATH if needed
#
# Requirements:
#   - Python 3.10+
#   - git

set -euo pipefail

# --- Configuration -----------------------------------------------------------

GITHUB_REPO="https://github.com/benjaminbooth/neutron-os-core.git"
VENV_DIR="${HOME}/.neut/venv"
BIN_DIR="${HOME}/.local/bin"
UNINSTALL=false
for arg in "$@"; do [ "$arg" = "--uninstall" ] && UNINSTALL=true; done

# --- Colors ------------------------------------------------------------------

if [ -t 1 ]; then
    BOLD="\033[1m"; DIM="\033[2m"; CYAN="\033[36m"
    GREEN="\033[32m"; RED="\033[31m"; RESET="\033[0m"
else
    BOLD=""; DIM=""; CYAN=""; GREEN=""; RED=""; RESET=""
fi

info() { echo -e "  ${CYAN}>${RESET} $*"; }
ok()   { echo -e "  ${GREEN}✓${RESET} $*"; }
err()  { echo -e "  ${RED}✗${RESET} $*" >&2; }
dim()  { echo -e "  ${DIM}$*${RESET}"; }

# --- Uninstall ---------------------------------------------------------------

if $UNINSTALL; then
    echo
    echo -e "  ${BOLD}Neutron OS Uninstaller${RESET}"
    echo -e "  ${DIM}──────────────────────${RESET}"
    echo
    rm -rf "$VENV_DIR"  && ok "Removed ${VENV_DIR}"
    rm -f "${BIN_DIR}/neut" && ok "Removed ${BIN_DIR}/neut"
    echo
    dim "PATH entries in your shell rc file were left in place (harmless)."
    dim "To remove: delete the '# Neutron OS CLI' block from ~/.zshrc (or ~/.bashrc)"
    echo
    exit 0
fi

# --- Preflight ---------------------------------------------------------------

echo
echo -e "  ${BOLD}Neutron OS Installer${RESET}"
echo -e "  ${DIM}────────────────────${RESET}"
echo

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

if ! command -v git &>/dev/null; then
    err "git not found. Install git first."
    exit 1
fi
ok "git available"

# --- Create isolated venv ----------------------------------------------------

info "Creating isolated environment at ${VENV_DIR}..."
mkdir -p "$(dirname "$VENV_DIR")"
python3 -m venv "$VENV_DIR"
ok "Environment ready"

# --- Install -----------------------------------------------------------------

info "Installing neut from GitHub..."
echo

"${VENV_DIR}/bin/pip" install --quiet --upgrade pip
"${VENV_DIR}/bin/pip" install "git+${GITHUB_REPO}" \
    2>&1 | while IFS= read -r line; do dim "$line"; done

echo
ok "Package installed"

# --- Symlink binary ----------------------------------------------------------

mkdir -p "$BIN_DIR"
ln -sf "${VENV_DIR}/bin/neut" "${BIN_DIR}/neut"
ok "Linked neut → ${BIN_DIR}/neut"

# --- PATH setup --------------------------------------------------------------

SHELL_NAME=$(basename "${SHELL:-/bin/bash}")
case "$SHELL_NAME" in
    zsh)  RC_FILE="$HOME/.zshrc" ;;
    bash) RC_FILE="$HOME/.bashrc" ;;
    fish) RC_FILE="$HOME/.config/fish/config.fish" ;;
    *)    RC_FILE="$HOME/.profile" ;;
esac

PATH_LINE="export PATH=\"${BIN_DIR}:\$PATH\""
[ "$SHELL_NAME" = "fish" ] && PATH_LINE="set -gx PATH ${BIN_DIR} \$PATH"

if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
    if ! grep -qF "$BIN_DIR" "$RC_FILE" 2>/dev/null; then
        { echo ""; echo "# Neutron OS CLI"; echo "$PATH_LINE"; } >> "$RC_FILE"
    fi
    export PATH="${BIN_DIR}:$PATH"
    ok "Added ${BIN_DIR} to PATH in ${RC_FILE}"
else
    ok "PATH already includes ${BIN_DIR}"
fi

# --- Verify ------------------------------------------------------------------

echo
if command -v neut &>/dev/null; then
    NEUT_VERSION=$(neut --version 2>/dev/null || echo "unknown")
    ok "neut ${NEUT_VERSION} ready"
    echo
    dim "Try it:  neut --help"
else
    ok "neut installed — open a new terminal or run: source ${RC_FILE}"
fi
echo

#!/usr/bin/env bash
# Install neut-serve as a systemd service so it survives reboots.
#
# This script is self-contained: it creates the .venv, installs the neut CLI,
# and sets up the systemd service in one step. No prior bootstrap required.
#
# Usage:
#   sudo ./scripts/install-service.sh          # auto-detects from script location
#   sudo NEUTRON_OS_ROOT=/opt/neutron ./scripts/install-service.sh  # explicit path
#
# Prerequisites:
#   - Python 3.12+ installed
#   - systemd-based Linux
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NEUTRON_OS_ROOT="${NEUTRON_OS_ROOT:-$(dirname "$SCRIPT_DIR")}"
SERVICE_USER="${SERVICE_USER:-$(stat -c '%U' "$NEUTRON_OS_ROOT" 2>/dev/null || ls -ld "$NEUTRON_OS_ROOT" | awk '{print $3}')}"
TEMPLATE="$NEUTRON_OS_ROOT/infra/systemd/neut-serve.service.template"
SERVICE_NAME="neut-serve"

# --- Preflight checks ---

if [[ ! -f "$TEMPLATE" ]]; then
    echo "Error: Template not found at $TEMPLATE" >&2
    exit 1
fi

if ! command -v systemctl &>/dev/null; then
    echo "Error: systemd not available on this system" >&2
    exit 1
fi

if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (use sudo)" >&2
    exit 1
fi

# --- Ensure Python venv and neut CLI are installed ---

VENV_PATH="$NEUTRON_OS_ROOT/.venv"
VENV_PYTHON="$VENV_PATH/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "Creating virtual environment at $VENV_PATH..."

    # Find a suitable python3 (prefer 3.12+ to match Dockerfile)
    PYTHON_BIN=""
    for candidate in python3.14 python3.13 python3.12 python3; do
        if command -v "$candidate" &>/dev/null; then
            PYTHON_BIN="$candidate"
            break
        fi
    done
    if [[ -z "$PYTHON_BIN" ]]; then
        echo "Error: No python3 found. Install Python 3.12+ first." >&2
        exit 1
    fi

    # Create venv as the service user (not root) so ownership is correct
    sudo -u "$SERVICE_USER" "$PYTHON_BIN" -m venv "$VENV_PATH"
fi

echo "Installing neut CLI into $VENV_PATH..."
sudo -u "$SERVICE_USER" "$VENV_PYTHON" -m pip install -q --upgrade pip
sudo -u "$SERVICE_USER" "$VENV_PYTHON" -m pip install -q -e "$NEUTRON_OS_ROOT[all]"

# Verify neut is importable
if ! "$VENV_PYTHON" -c "import neutron_os" 2>/dev/null; then
    echo "Error: neutron_os package failed to install" >&2
    exit 1
fi
echo "neut CLI installed successfully"

# --- Generate and install service ---

echo "Installing $SERVICE_NAME systemd service"
echo "  NEUTRON_OS_ROOT: $NEUTRON_OS_ROOT"
echo "  SERVICE_USER:    $SERVICE_USER"
echo "  VENV_PYTHON:     $VENV_PYTHON"
echo ""

sed -e "s|{{USER}}|$SERVICE_USER|g" \
    -e "s|{{NEUTRON_OS_ROOT}}|$NEUTRON_OS_ROOT|g" \
    "$TEMPLATE" > "/etc/systemd/system/${SERVICE_NAME}.service"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME" 2>/dev/null || systemctl start "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

echo ""
echo "Done. Service status:"
systemctl status "$SERVICE_NAME" --no-pager
echo ""
echo "Useful commands:"
echo "  sudo systemctl status $SERVICE_NAME    # check status"
echo "  sudo journalctl -u $SERVICE_NAME -f    # follow logs"
echo "  sudo systemctl restart $SERVICE_NAME   # restart after code changes"

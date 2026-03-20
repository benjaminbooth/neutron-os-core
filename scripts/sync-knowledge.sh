#!/usr/bin/env bash
# sync-knowledge.sh — Sync local knowledge sources to Rascal (or any remote)
#
# Usage:
#   ./sync-knowledge.sh                     # Sync to Rascal (default)
#   ./sync-knowledge.sh user@host           # Sync to custom remote
#   REMOTE_PATH=/opt/neutron ./sync-knowledge.sh  # Custom remote path
#
# This script mirrors runtime/knowledge/ to the remote server.
# On AWS, this gets replaced by an S3 sync or Box connector Lambda.
set -euo pipefail

REMOTE="${1:-rascal}"
LOCAL_KNOWLEDGE="$(cd "$(dirname "$0")/.." && pwd)/runtime/knowledge"
REMOTE_PATH="${REMOTE_PATH:-Projects/UT_Computational_NE/Neutron_OS/runtime/knowledge}"

if [[ ! -d "${LOCAL_KNOWLEDGE}" ]]; then
    echo "[ERROR] Local knowledge dir not found: ${LOCAL_KNOWLEDGE}"
    exit 1
fi

echo "Syncing knowledge to ${REMOTE}:~/${REMOTE_PATH}/"
echo "  Local:  ${LOCAL_KNOWLEDGE}"
echo "  Remote: ${REMOTE}:~/${REMOTE_PATH}/"
echo ""

# Create remote dir
ssh "${REMOTE}" "mkdir -p ~/${REMOTE_PATH}"

# rsync with compression, skip __MACOSX and .DS_Store
rsync -avz --progress \
    --exclude="__MACOSX" \
    --exclude=".DS_Store" \
    --exclude="*.tmp" \
    "${LOCAL_KNOWLEDGE}/" \
    "${REMOTE}:~/${REMOTE_PATH}/"

echo ""
echo "Sync complete. Run 'python -m neutron_os.rag ingest' on ${REMOTE} to index."

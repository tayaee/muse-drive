#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find muse-drive executable
if [ -f "${SCRIPT_DIR}/.venv/bin/muse-drive" ]; then
    MUSE_CMD="${SCRIPT_DIR}/.venv/bin/muse-drive"
elif command -v muse-drive >/dev/null 2>&1; then
    MUSE_CMD="muse-drive"
elif [ -f "${HOME}/.local/bin/muse-drive" ]; then
    MUSE_CMD="${HOME}/.local/bin/muse-drive"
else
    MUSE_CMD="uv run --directory ${SCRIPT_DIR} muse-drive"
fi

TARGET="${HOME}/muse-workspace"
LABEL="Muse Drive"
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --drive|-d|--target|-t)
            TARGET="$2"
            shift 2
            ;;
        --label|-l)
            LABEL="$2"
            shift 2
            ;;
        --help|-h)
            ${MUSE_CMD} mount --help
            exit 0
            ;;
        -*)
            EXTRA_ARGS+=("$1")
            shift
            ;;
        *)
            TARGET="$1"
            shift
            ;;
    esac
done

# If already mounted, unmount first
if ${MUSE_CMD} status 2>/dev/null | grep -q "Mounted"; then
    echo "An existing mount was detected. Stopping it first..."
    echo "+ ${MUSE_CMD} umount"
    ${MUSE_CMD} umount >/dev/null 2>&1 || true
    sleep 1
fi

echo "+ ${MUSE_CMD} mount \"${TARGET}\" --label \"${LABEL}\" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"
${MUSE_CMD} mount "${TARGET}" --label "${LABEL}" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}

echo "Waiting for ${TARGET} to be mounted..."
ATTEMPTS=0
while [ $ATTEMPTS -lt 30 ]; do
    sleep 1
    ATTEMPTS=$((ATTEMPTS + 1))
    if mountpoint -q "${TARGET}" 2>/dev/null || mount | grep -Fq "${TARGET}" 2>/dev/null; then
        echo "Workspace mounted successfully at: ${TARGET}"
        exit 0
    fi
    if ${MUSE_CMD} status 2>/dev/null | grep -q "Mounted and Running"; then
        echo "Workspace mounted successfully at: ${TARGET}"
        exit 0
    fi
done

echo "Warning: Mount check timed out after 30 seconds."
exit 1

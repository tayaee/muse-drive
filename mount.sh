#!/usr/bin/env bash
set -euo pipefail

# Find muse-drive executable
if command -v muse-drive >/dev/null 2>&1; then
    MUSE_CMD="muse-drive"
elif [ -f "${HOME}/.local/bin/muse-drive" ]; then
    MUSE_CMD="${HOME}/.local/bin/muse-drive"
else
    MUSE_CMD="uv tool run muse-drive"
fi

TARGET="${HOME}/muse/workspace"
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
            echo "Usage: ./mount.sh [TARGET] [--label LABEL] [--port PORT]"
            echo ""
            echo "Options:"
            echo "  TARGET / --drive, -d, --target, -t  Mount target path (default: ~/muse/workspace)"
            echo "  --label, -l                         Display label (default: \"Muse Drive\")"
            echo "  --port, -p                          Custom WebDAV port (default: auto-scan 18844..18853)"
            echo "  --help, -h                          Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./mount.sh"
            echo "  ./mount.sh ~/my-workspace"
            echo "  ./mount.sh --drive ~/my-workspace --label \"Muse Drive\""
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

echo "+ ${MUSE_CMD} mount \"${TARGET}\" --label \"${LABEL}\" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"
${MUSE_CMD} mount "${TARGET}" --label "${LABEL}" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}

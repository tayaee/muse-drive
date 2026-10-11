#!/usr/bin/env bash
set -euo pipefail

if command -v muse-drive >/dev/null 2>&1; then
    MUSE_CMD="muse-drive"
elif [ -f "${HOME}/.local/bin/muse-drive" ]; then
    MUSE_CMD="${HOME}/.local/bin/muse-drive"
else
    MUSE_CMD="uv tool run muse-drive"
fi

TARGET=""
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --drive|-d|--target|-t)
            TARGET="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: ./umount.sh [TARGET]"
            echo ""
            echo "Options:"
            echo "  TARGET / --drive, -d, --target, -t  Mount target to disconnect (optional, defaults to active mount)"
            echo "  --help, -h                          Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./umount.sh"
            echo "  ./umount.sh ~/muse/workspace"
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

if [ -n "${TARGET}" ]; then
    echo "+ ${MUSE_CMD} umount \"${TARGET}\" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"
    ${MUSE_CMD} umount "${TARGET}" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
else
    echo "+ ${MUSE_CMD} umount ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"
    ${MUSE_CMD} umount ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
fi

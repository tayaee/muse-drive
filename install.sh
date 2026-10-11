#!/usr/bin/env bash
set -euo pipefail

# Determine script directory (repository root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Installing muse-drive via uv tool ==="

# Check if uv is installed
if ! command -v uv >/dev/null 2>&1; then
    echo "Warning: 'uv' is not installed or not in PATH."
    echo "Attempting to install uv automatically..."
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"
    else
        echo "Error: curl is required to install uv automatically." >&2
        echo "Please install uv manually: https://docs.astral.sh/uv/getting-started/installation/" >&2
        exit 1
    fi
fi

# Ensure uv is now available
if ! command -v uv >/dev/null 2>&1; then
    echo "Error: uv was installed but is not found in PATH." >&2
    echo "Please reload your shell or add ~/.local/bin to your PATH, then rerun this script." >&2
    exit 1
fi

echo "Installing muse-drive tool..."
uv tool install "${SCRIPT_DIR}" --force

# Ensure PATH includes ~/.local/bin for current script execution
export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"
uv tool update-shell >/dev/null 2>&1 || true

echo ""
echo "=== Mounting Workspace to ~/muse/workspace ==="
# Attempt automatic mount
if command -v muse-drive >/dev/null 2>&1; then
    MUSE_CMD="muse-drive"
else
    MUSE_CMD="uv tool run muse-drive"
fi

if ${MUSE_CMD} mount; then
    echo ""
    echo "=== Installation & Mount Successful! ==="
    echo "Workspace is mounted at: ~/muse/workspace"
else
    echo ""
    echo "=== Installation Completed ==="
    echo "Note: Could not mount automatically (session cookies may be required)."
    echo "Please ensure session cookies exist at ~/.config/muse-cli/cookies.txt"
    echo "and then run:"
    echo "  muse-drive mount"
fi

echo ""
echo "Commands:"
echo "  muse-drive status     # Check mount status"
echo "  muse-drive umount     # Unmount workspace"
echo "  muse-drive --help"

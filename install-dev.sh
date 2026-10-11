#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Setting up muse-drive Development Environment ==="

# Check if uv is installed
if ! command -v uv >/dev/null 2>&1; then
    echo "Warning: 'uv' is not installed or not in PATH."
    echo "Attempting to install uv automatically..."
    if command -v curl >/dev/null 2>&1; then
        echo "+ curl -LsSf https://astral.sh/uv/install.sh | sh"
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

cd "${SCRIPT_DIR}"

echo "Syncing virtual environment and dependencies (.venv)..."
echo "+ uv sync"
uv sync

echo ""
echo "=== Development Setup Complete! ==="
echo "Virtual environment is ready at: ${SCRIPT_DIR}/.venv"
echo ""
echo "To run during development without activating:"
echo "  uv run muse-drive --help"
echo "  uv run muse-drive mount"
echo ""
echo "Or activate the virtual environment directly:"
echo "  source .venv/bin/activate"
echo "  muse-drive --help"
echo ""

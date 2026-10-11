#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Installing muse-drive via uv tool ==="

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

export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"

# On Linux, ensure rclone is available for local FUSE mounting
if [[ "$(uname -s)" == "Linux" ]] && ! command -v rclone >/dev/null 2>&1 && [ ! -f "${HOME}/.local/bin/rclone" ]; then
    echo "Setting up rclone for Linux FUSE mounting..."
    python3 -c "
import urllib.request, zipfile, io, os, stat
req = urllib.request.Request('https://downloads.rclone.org/rclone-current-linux-amd64.zip', headers={'User-Agent': 'curl/7.88.1'})
try:
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            if name.endswith('/rclone'):
                target = os.path.expanduser('~/.local/bin/rclone')
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, 'wb') as f:
                    f.write(z.read(name))
                os.chmod(target, os.stat(target).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
                break
except Exception as e:
    print('Notice: Could not automatically download rclone:', e)
" || true
fi

echo "Installing muse-drive tool from git..."
echo "+ uv tool install git+https://github.com/tayaee/muse-drive.git --force"
uv tool install git+https://github.com/tayaee/muse-drive.git --force

uv tool update-shell >/dev/null 2>&1 || true

echo ""
echo "========================================"
echo "  muse-drive installation complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  ./mount.sh            # Mount workspace to ~/muse/workspace"
echo "  ./umount.sh           # Unmount workspace"
echo ""
echo "To mount now, please run:"
echo "  ./mount.sh"
echo ""

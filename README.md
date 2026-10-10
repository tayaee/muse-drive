# muse-workspace-as-windows-drive (`muse-drive`)

Mount your Muse AI cloud Workspace directly as a Windows network drive (e.g. `M:`) using a lightweight local WebDAV proxy.

No third-party kernel filesystem drivers (like WinFsp or Dokany) are required. Works out-of-the-box on standard Windows!

---

## Architecture & How It Works

```
[Windows File Explorer]
         │
    (WebDAV / HTTP)
         ▼
[Local WebDAV Server (127.0.0.1:8080)]
    - Powered by WsgiDAV & cheroot
    - Metadata & directory list caching
         │
    (Direct WebSocket + Noise-XX transport)
         ▼
[Muse AI Cloud Gateway (hatch.metaaivm.com)]
```

- **Zero-Binary Dependency:** Communicates directly with the Muse gateway via WebSocket & Noise-XX encryption without calling `muse-cli.exe`.
- **Shared Authentication:** Automatically reuses session cookies from `%USERPROFILE%\.config\muse-cli\cookies.txt` (or `~/.config/muse-cli/cookies.txt` on Linux/macOS).
- **Native Explorer Experience:** Mapped via Windows' native `net use M: http://127.0.0.1:8080/ /persistent:no`. Browse, open files, or drag-and-drop directly from Windows File Explorer.

---

## Quick Installation

Install `muse-drive` via [`uv`](https://github.com/astral-sh/uv):

```bash
# Clone the repository
git clone https://github.com/tayaee/muse-workspace-as-windows-drive.git
cd muse-workspace-as-windows-drive

# Install tool into your environment
uv tool install . --force
```

Or run directly without installation:
```bash
uv run muse-drive --help
```

---

## Usage

### 1) Mount Workspace to `M:` Drive

```bash
# Mount to default M: drive
uv run muse-drive mount --drive M:

# Or specify a different drive letter and port
uv run muse-drive mount --drive Z: --port 8088
```

*Example Output:*
```text
Connecting Windows drive M: -> http://127.0.0.1:8080/ ...
Mounted successfully:
  Drive:       M: [Muse Workspace]
  WebDAV URL:  http://127.0.0.1:8080/
  PID:         12345
```

Now open **Windows File Explorer** $\rightarrow$ **This PC**, and access your workspace under `M:\`!

### 2) Check Mount Status

```bash
uv run muse-drive status
```

*Example Output:*
```text
Status: Mounted and Running
  Drive:      M:
  WebDAV URL: http://127.0.0.1:8080/
  PID:        12345
```

### 3) Unmount Workspace

```bash
# Unmount default M: drive and stop daemon
uv run muse-drive umount

# Or specify drive letter explicitly
uv run muse-drive umount --drive M:
```

*Example Output:*
```text
Disconnecting Windows drive M: ...
Drive M: disconnected.
Stopping muse-drive daemon (PID: 12345) ...
Daemon stopped.
```

---

## Requirements & Authentication

1. **Python 3.10+** (managed automatically by `uv`)
2. **Session Cookies:** Requires `%USERPROFILE%\.config\muse-cli\cookies.txt` (or custom path via `MUSE_COOKIES_PATH` environment variable).

# muse-drive

Mount your Muse AI cloud Workspace directly as a Windows network drive (e.g. `M:`) using a lightweight local WebDAV proxy.

No third-party kernel filesystem drivers (like WinFsp or Dokany) are required. Works out-of-the-box on standard Windows!

---

## Installation

Install `muse-drive` using [`uv`](https://github.com/astral-sh/uv) in either of the following two ways:

### 1. Install directly from Git URL (Recommended)

Install directly without cloning the repository:

```bash
uv tool install git+https://github.com/tayaee/muse-drive.git --force
```

### 2. Clone repository and install

```bash
git clone https://github.com/tayaee/muse-drive.git
cd muse-drive

# Linux / macOS / WSL
./install.sh

# Windows (Command Prompt / PowerShell)
install.bat
```

*(Or run `uv tool install . --force` directly)*

> **Tip:** After installing, `muse-drive` is available directly in your PATH.

---

## Usage

### 1) Mount Workspace

Simply run `muse-drive mount` to mount to the default location for your operating system:
- **Windows:** Mounts to `M:` drive
- **Linux / macOS:** Mounts to `~/muse/workspace`

```bash
muse-drive mount M:                 # Windows
muse-drive mount ~/muse/workspace   # Linux / macOS
```

### 2) Check Mount Status

```bash
muse-drive status
```

*Example Output:*
```text
Status: Mounted and Running
  Mount Path:  /home/user/muse/workspace
  WebDAV URL:  http://127.0.0.1:8080/
  PID:         12345
```

### 3) Unmount Workspace

```bash
muse-drive umount
```

---

## Requirements & Authentication

1. **Python 3.10+** (managed automatically by `uv`)
2. **Session Cookies:** Requires `%USERPROFILE%\.config\muse-cli\cookies.txt` (or `~/.config/muse-cli/cookies.txt` on Linux/macOS, or custom path via `MUSE_COOKIES_PATH` environment variable).
   - This `cookies.txt` is shared by `muse-cli`, `muse-cli-w`, and `muse-drive` — log in once, use it in all three apps.
   - For the `cookies.txt` format and how to create/refresh it, see [muse-cli – Log in once](https://github.com/nikships/muse-cli#log-in-once).

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

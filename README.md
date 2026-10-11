# muse-drive

Mount your Muse AI cloud Workspace directly as a Windows network drive (e.g. `M:`) using a lightweight local WebDAV proxy.

No third-party kernel filesystem drivers (like WinFsp or Dokany) are required. Works out-of-the-box on standard Windows!

---

## Installation

**Prerequisite:** [`uv`](https://github.com/astral-sh/uv) is required to install and run `muse-drive`.

### 1. Install directly from Git URL (Recommended)

Install directly without cloning the repository:

```bash
uv tool install git+https://github.com/tayaee/muse-drive.git --force
```

### Alternative: Clone repository and install

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

## Configure `cookies.txt`

`muse-drive` authenticates with the Muse AI cloud gateway using session cookies stored in `cookies.txt`.

### 1. Default File Locations
- **Windows:** `%USERPROFILE%\.config\muse-cli\cookies.txt`
- **Linux / macOS:** `~/.config/muse-cli/cookies.txt`
- *(Optional)* Set a custom path via `MUSE_COOKIES_PATH` environment variable:
  ```bash
  export MUSE_COOKIES_PATH="/path/to/your/cookies.txt"
  ```

### 2. How to Set Up
- **Shared Login (Recommended):** If you have already logged in via [`muse-cli`](https://github.com/nikships/muse-cli), `muse-drive` will automatically reuse the existing cookies file.
- **Manual Export:** Export your Muse session cookies from your browser (Netscape format) and save them to the location above.
  - For step-by-step instructions and cookie format, see [muse-cli – Log in once](https://github.com/nikships/muse-cli#log-in-once).

---

## Usage

### 1) Mount Workspace

Simply run `muse-drive mount` to mount to the default location for your operating system:
- **Windows:** Mounts to `M:` drive as `Muse Drive`
- **Linux / macOS:** Mounts to `~/muse/workspace`

`muse-drive` automatically scans 10 safe ports in the 10,000+ range (`18844` to `18853`) and selects the first available port. If all safe ports are busy, it falls back to port `8844`. You can also specify an exact port and label using command-line flags.

```bash
# Default mount (automatically selects an available port)
muse-drive mount

# Windows with explicit drive, port, and label options:
muse-drive mount M: --port 18844 --label "Muse Drive"

# Linux / macOS with custom directory and port:
muse-drive mount ~/muse/workspace --port 18844
```

*Example Output (Windows):*
```text
Connecting Windows drive M: -> http://127.0.0.1:18844/ ...
Mounted successfully:
  Drive:       M: [Muse Drive]
  WebDAV URL:  http://127.0.0.1:18844/
  PID:         12345
  Log file:    %TEMP%\muse-drive.log
```

### 2) Check Mount Status

```bash
muse-drive status
```

*Example Output:*
```text
Status: Mounted and Running
  Drive:       M:
  WebDAV URL:  http://127.0.0.1:8844/
  PID:         12345
  Log file:    %TEMP%\muse-drive.log
```

### 3) Unmount Workspace

```bash
muse-drive umount
```

---

## Logs & Troubleshooting

- **Log File:** Logs are written to `%TEMP%\muse-drive.log` on Windows (or `/tmp/muse-drive.log` on Linux/macOS).
- **Windows WebClient Service:** If mounting to a Windows drive returns `System error 64` or `System error 67`, ensure the Windows WebClient service is running. Run the following command in an Administrator Command Prompt:
  ```cmd
  net start webclient
  ```

---

## Requirements

1. **Python 3.10+** (managed automatically by `uv`)
2. **Session Cookies:** Valid `cookies.txt` (see [Configure `cookies.txt`](#configure-cookiestxt) above).

---

## Architecture & How It Works

```
[Windows File Explorer]
         │
    (WebDAV / HTTP)
         ▼
[Local WebDAV Server (127.0.0.1:PORT)]
    - Powered by WsgiDAV & cheroot
    - Metadata & directory list caching
         │
    (Direct WebSocket + Noise-XX transport)
         ▼
[Muse AI Cloud Gateway (hatch.metaaivm.com)]
```

- **Zero-Binary Dependency:** Communicates directly with the Muse gateway via WebSocket & Noise-XX encryption without calling `muse-cli.exe`.
- **Shared Authentication:** Automatically reuses session cookies from `%USERPROFILE%\.config\muse-cli\cookies.txt` (or `~/.config/muse-cli/cookies.txt` on Linux/macOS).
- **Native Explorer Experience:** Mapped via Windows' native `net use M: http://127.0.0.1:8844/ /persistent:no`. Browse, open files, or drag-and-drop directly from Windows File Explorer.

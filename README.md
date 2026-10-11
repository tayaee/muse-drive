# muse-drive

Mount your Muse AI cloud Workspace directly as a Windows network drive (e.g. `M:`) using a lightweight local WebDAV proxy.

No third-party kernel filesystem drivers (like WinFsp or Dokany) are required. Works out-of-the-box on standard Windows!

---

## Installation

**Prerequisite:** [`uv`](https://github.com/astral-sh/uv) is required to install and run `muse-drive`.

### Standard Installation

Clone the repository and run the install script:

**Windows (Command Prompt / PowerShell):**
```cmd
git clone https://github.com/tayaee/muse-drive.git
cd muse-drive
install.bat
```

**Linux / macOS:**
```bash
git clone https://github.com/tayaee/muse-drive.git
cd muse-drive
./install.sh
```

*(Alternative: You can also install directly via `uv tool install git+https://github.com/tayaee/muse-drive.git --force`)*

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

Use the provided mount script:

- **Windows:**
  ```cmd
  mount.bat                                # Mount M: with default label "Muse Drive"
  mount.bat Z:                             # Mount to custom drive letter Z:
  mount.bat --drive Z: --label "Workspace" # Mount with custom drive letter and label
  ```

- **Linux / macOS:**
  ```bash
  ./mount.sh                               # Mount ~/muse/workspace
  ./mount.sh --drive ~/my-workspace        # Mount to custom directory
  ```

*(Or use the CLI command directly: `muse-drive mount [DRIVE/PATH] [--label LABEL] [--port PORT]`)*

`muse-drive` automatically scans 10 safe ports in the 10,000+ range (`18844` to `18853`) and selects the first available port. If all safe ports are busy, it falls back to port `8844`.

*Example Output (Windows):*
```text
Connecting Windows drive M: -> http://127.0.0.1:18844/ ...
Mounted successfully:
  Drive:       M: [Muse Drive]
  WebDAV URL:  http://127.0.0.1:18844/
  PID:         12345
```

### 2) Check Mount Status

```bash
muse-drive status
```

*Example Output:*
```text
Status: Mounted and Running
  Drive:       M:
  WebDAV URL:  http://127.0.0.1:18844/
  PID:         12345
```

### 3) Unmount Workspace

- **Windows:**
  ```cmd
  umount.bat
  ```

- **Linux / macOS:**
  ```bash
  ./umount.sh
  ```

*(Or use the CLI command: `muse-drive umount`)*

---

## Logs & Troubleshooting

- **Logs:** Logs are printed directly to `stdout`.
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

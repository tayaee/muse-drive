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

*(Alternative: To install directly from git as a global CLI tool without local sync, run `install-from-git.bat` / `./install-from-git.sh`)*

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

### Mount

- **Windows:** (Default: `M:`)
  ```cmd
  mount.bat
  ```

- **Linux / macOS:** (Default: `~/muse-workspace`)
  ```bash
  ./mount.sh
  ```

### Unmount

- **Windows:**
  ```cmd
  umount.bat
  ```

- **Linux / macOS:**
  ```bash
  ./umount.sh
  ```

### Options (Optional)

```cmd
# Windows: specify drive or label
mount.bat Z:
mount.bat --drive Z: --label "Workspace"

# Linux / macOS: specify target directory
./mount.sh ~/my-workspace
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

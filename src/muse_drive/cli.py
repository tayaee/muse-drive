"""Command Line Interface for muse-drive."""
import argparse
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from .client import MuseWorkspaceClient, find_cookies_path, get_default_cookies_path
from .server import (
    clear_daemon_state,
    load_daemon_state,
    save_daemon_state,
    start_server,
)

SYSTEM = platform.system().lower()
IS_WINDOWS = SYSTEM == "windows"
IS_DARWIN = SYSTEM == "darwin"
IS_LINUX = SYSTEM == "linux"


def _default_target() -> str:
    """Return default mount target: M: on Windows, ~/muse/workspace on Linux/macOS."""
    if IS_WINDOWS:
        return "M:"
    return str(Path.home() / "muse" / "workspace")


def _resolve_target(args) -> str:
    """Resolve target path or drive letter from positional or optional flags."""
    raw = getattr(args, "target", None) or getattr(args, "target_opt", None) or getattr(args, "drive", None)
    if not raw:
        return _default_target()
    raw = raw.strip()
    if IS_WINDOWS:
        # Normalize drive letter like 'M' or 'm:' to 'M:'
        if len(raw) <= 3 and raw[0].isalpha() and (len(raw) == 1 or raw[1] == ":"):
            d = raw.rstrip(":\\/").upper()
            return f"{d}:"
        return raw
    # Linux / macOS: expand ~ and make absolute path
    return str(Path(raw).expanduser().resolve())


def _is_process_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if IS_WINDOWS:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        else:
            os.kill(pid, 0)
            return True
    except OSError:
        return False


def _kill_process(pid: int):
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
            if _is_process_running(pid):
                os.kill(pid, signal.SIGKILL)
    except Exception:
        pass


def _mount_target(target: str, host: str, port: int) -> tuple[bool, str, int]:
    """Mount the WebDAV proxy to the target drive/directory. Returns (success, method, pid)."""
    webdav_url = f"http://{host}:{port}/"

    if IS_WINDOWS:
        print(f"Connecting Windows drive {target} -> {webdav_url} ...")
        res = subprocess.run(
            ["net", "use", target, webdav_url, "/persistent:no"],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            return True, "net_use", 0
        print(f"Warning: 'net use' returned error: {res.stderr.strip()}", file=sys.stderr)
        return False, "net_use", 0

    target_path = Path(target)
    target_path.mkdir(parents=True, exist_ok=True)

    if IS_DARWIN:
        print(f"Mounting WebDAV volume on {target_path} ...")
        res = subprocess.run(
            ["mount_webdav", webdav_url, str(target_path)],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            return True, "mount_webdav", 0
        print(f"Notice: mount_webdav returned: {res.stderr.strip()}", file=sys.stderr)
        return False, "mount_webdav", 0

    # Linux FUSE mounting
    rclone_bin = shutil.which("rclone") or (
        str(Path.home() / ".local" / "bin" / "rclone")
        if (Path.home() / ".local" / "bin" / "rclone").is_file()
        else None
    )
    if rclone_bin:
        print(f"Mounting {target_path} via rclone (FUSE) ...")
        cmd = [
            rclone_bin,
            "mount",
            ":webdav:",
            str(target_path),
            "--webdav-url",
            webdav_url,
            "--webdav-vendor",
            "other",
            "--vfs-cache-mode",
            "writes",
        ]
        rproc = subprocess.Popen(
            cmd,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.0)
        if _is_process_running(rproc.pid):
            return True, "rclone", rproc.pid
        print("Warning: rclone mount process did not stay running.", file=sys.stderr)

    if shutil.which("gio"):
        print(f"Attempting gio (GVfs) mount -> dav://{host}:{port}/ ...")
        res = subprocess.run(
            ["gio", "mount", f"dav://{host}:{port}/"],
            capture_output=True,
            text=True,
        )
        gvfs_mount = Path(f"/run/user/{os.getuid()}/gvfs/dav:host={host},port={port}")
        if gvfs_mount.exists():
            try:
                if target_path.exists() and not any(target_path.iterdir()) and not target_path.is_symlink():
                    target_path.rmdir()
                    target_path.symlink_to(gvfs_mount)
                return True, "gio", 0
            except Exception:
                pass

    print(f"Notice: WebDAV proxy is running on {webdav_url}", file=sys.stderr)
    print("To mount as a local folder in Linux, rclone is required (install via: ./install.sh)", file=sys.stderr)
    return False, "none", 0


def _unmount_target(target: str, mount_method: str = "", host: str = "127.0.0.1", port: int = 8080, rclone_pid: int = 0):
    """Unmount drive or directory and kill auxiliary mount daemons."""
    if IS_WINDOWS and target:
        print(f"Disconnecting Windows drive {target} ...")
        res = subprocess.run(["net", "use", target, "/delete", "/yes"], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"Drive {target} disconnected.")
        else:
            print(f"Notice: {res.stderr.strip() or 'Drive was not actively mapped.'}")
        return

    target_path = Path(target)
    if IS_DARWIN:
        print(f"Unmounting {target_path} ...")
        subprocess.run(["diskutil", "unmount", str(target_path)], capture_output=True)
        return

    # Linux
    if target_path.is_symlink():
        try:
            target_path.unlink()
            target_path.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    if mount_method == "gio" or shutil.which("gio"):
        subprocess.run(["gio", "mount", "-u", f"dav://{host}:{port}/"], capture_output=True)

    if rclone_pid and _is_process_running(rclone_pid):
        _kill_process(rclone_pid)

    if shutil.which("fusermount3"):
        subprocess.run(["fusermount3", "-u", str(target_path)], capture_output=True)
    elif shutil.which("fusermount"):
        subprocess.run(["fusermount", "-u", str(target_path)], capture_output=True)
    else:
        subprocess.run(["umount", str(target_path)], capture_output=True)


def _print_connection_error_guide(error: Exception, cookies_path: Path | None = None):
    """Print friendly guidance when connection or cookies error occurs."""
    expected_p = cookies_path or get_default_cookies_path()
    print(f"Error connecting to Muse workspace: {error}", file=sys.stderr)
    print("\n" + "=" * 64, file=sys.stderr)
    print("  [Muse Workspace Authentication / Connection Guide]", file=sys.stderr)
    print(f"  • Cookies file location:", file=sys.stderr)
    print(f"      {expected_p}", file=sys.stderr)
    print("  • The session cookies file is missing, expired, or invalid.", file=sys.stderr)
    print("  • Please refer to the repository instructions to set it up:", file=sys.stderr)
    print("      👉 https://github.com/tayaee/muse-drive", file=sys.stderr)
    print("=" * 64 + "\n", file=sys.stderr)


def cmd_serve(args):
    """Internal command: run the WebDAV server in the current process."""
    try:
        cookies_p = find_cookies_path()
        client = MuseWorkspaceClient(cookies_p)
    except Exception as e:
        _print_connection_error_guide(e)
        sys.exit(1)
    start_server(args.host, args.port, client)


def cmd_mount(args):
    """Mount Muse workspace to a local drive letter or directory."""
    target = _resolve_target(args)
    host = args.host
    port = args.port

    state = load_daemon_state()
    if state and _is_process_running(state.get("pid", 0)):
        cur_target = state.get("target") or state.get("drive", "")
        cur_port = state.get("port", port)
        print(f"muse-drive is already mounted on {cur_target} (http://{host}:{cur_port}/, PID: {state.get('pid')})")
        return

    # Verify cookies.txt before starting
    cookies_p = None
    try:
        cookies_p = find_cookies_path()
        client = MuseWorkspaceClient(cookies_p)
        # Test connection & authentication
        client.ping()
    except Exception as e:
        _print_connection_error_guide(e, cookies_p)
        sys.exit(1)

    if args.foreground:
        print(f"Starting muse-drive in foreground on http://{host}:{port}/ ...")
        ok, method, rclone_pid = _mount_target(target, host, port)
        try:
            start_server(host, port, client)
        finally:
            _unmount_target(target, method, host, port, rclone_pid)
        return

    # Spawn daemon process
    python_exe = sys.executable
    daemon_cmd = [
        python_exe,
        "-m",
        "muse_drive.cli",
        "_serve",
        "--host",
        host,
        "--port",
        str(port),
    ]

    # Spawn detached background process
    if IS_WINDOWS:
        flags = 0x00000008 | 0x00000200
        proc = subprocess.Popen(
            daemon_cmd,
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        proc = subprocess.Popen(
            daemon_cmd,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # Wait briefly for server startup
    time.sleep(1.0)

    if not _is_process_running(proc.pid):
        print("Error: muse-drive daemon failed to start.", file=sys.stderr)
        sys.exit(1)

    # Perform OS-level mount
    ok, method, rclone_pid = _mount_target(target, host, port)

    save_daemon_state({
        "pid": proc.pid,
        "target": target,
        "drive": target,  # backwards compatibility
        "host": host,
        "port": port,
        "method": method,
        "rclone_pid": rclone_pid,
    })

    print(f"Mounted successfully:")
    target_label = "Drive" if IS_WINDOWS else "Mount Path"
    print(f"  {target_label}:  {target} [Muse Workspace]")
    print(f"  WebDAV URL:  http://{host}:{port}/")
    print(f"  PID:         {proc.pid}")


def cmd_umount(args):
    """Unmount Muse workspace drive and stop daemon."""
    state = load_daemon_state()
    target = _resolve_target(args) if (args.target or args.target_opt or args.drive) else (
        state.get("target") or state.get("drive") if state else _default_target()
    )
    mount_method = state.get("method", "") if state else ""
    rclone_pid = state.get("rclone_pid", 0) if state else 0
    host = state.get("host", "127.0.0.1") if state else "127.0.0.1"
    port = state.get("port", 8080) if state else 8080

    _unmount_target(target, mount_method, host, port, rclone_pid)

    if state:
        pid = state.get("pid", 0)
        if _is_process_running(pid):
            print(f"Stopping muse-drive daemon (PID: {pid}) ...")
            _kill_process(pid)
        clear_daemon_state()
        print("Daemon stopped.")
    else:
        print("No active muse-drive daemon state found.")


def cmd_status(args):
    """Show current mount and daemon status."""
    state = load_daemon_state()
    if not state or not _is_process_running(state.get("pid", 0)):
        print("Status: Not mounted (daemon is stopped)")
        if state:
            clear_daemon_state()
        return

    target = state.get("target") or state.get("drive", "")
    host = state.get("host", "127.0.0.1")
    port = state.get("port", 8080)
    pid = state.get("pid")

    print(f"Status: Mounted and Running")
    target_label = "Drive" if IS_WINDOWS else "Mount Path"
    if target:
        print(f"  {target_label}:  {target}")
    print(f"  WebDAV URL: http://{host}:{port}/")
    print(f"  PID:        {pid}")


def main():
    parser = argparse.ArgumentParser(
        prog="muse-drive",
        description="Mount Muse AI cloud workspace as a local drive or directory via local WebDAV proxy",
    )
    sub = parser.add_subparsers(dest="subcommand")

    # mount
    p_mount = sub.add_parser("mount", help="Mount workspace as a local drive or directory")
    p_mount.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Mount target: Drive letter on Windows (default: M:), directory path on Linux/macOS (default: ~/muse/workspace)",
    )
    p_mount.add_argument("--target", "-t", dest="target_opt", help="Mount target path or drive letter")
    p_mount.add_argument("--mountpoint", dest="target_opt", help=argparse.SUPPRESS)
    p_mount.add_argument("--drive", "-d", dest="drive", help="Drive letter (Windows legacy option)")
    p_mount.add_argument("--host", default="127.0.0.1", help="Local host binding (default: 127.0.0.1)")
    p_mount.add_argument("--port", "-p", type=int, default=8080, help="Local WebDAV port (default: 8080)")
    p_mount.add_argument("--foreground", "-f", action="store_true", help="Run server in foreground")
    p_mount.set_defaults(func=cmd_mount)

    # umount / unmount
    p_umount = sub.add_parser("umount", aliases=["unmount"], help="Unmount workspace drive or directory")
    p_umount.add_argument("target", nargs="?", default=None, help="Mount target to disconnect (optional)")
    p_umount.add_argument("--target", "-t", dest="target_opt", help="Mount target path or drive letter")
    p_umount.add_argument("--drive", "-d", dest="drive", help="Drive letter (Windows legacy option)")
    p_umount.set_defaults(func=cmd_umount)

    # status
    p_status = sub.add_parser("status", help="Check mount status")
    p_status.set_defaults(func=cmd_status)

    # internal serve
    p_serve = sub.add_parser("_serve", help=argparse.SUPPRESS)
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8080)
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()

"""Command Line Interface for muse-drive."""
import argparse
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from .client import MuseWorkspaceClient, find_cookies_path, get_default_cookies_path
from .logger import get_log_file_path, log, setup_logging
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

DEFAULT_PORT = 8844


def _is_port_in_use(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            s.bind((host, port))
            return False
    except OSError:
        return True


def _find_available_port(host: str, start_port: int = DEFAULT_PORT, max_attempts: int = 20) -> int:
    for p in range(start_port, start_port + max_attempts):
        if not _is_port_in_use(host, p):
            return p
    return start_port


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
    if pid <= 0:
        return
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


def _wait_for_server(host: str, port: int, timeout: float = 10.0, proc: subprocess.Popen | None = None) -> bool:
    """Wait for WebDAV HTTP server to become responsive via TCP connection."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc and proc.poll() is not None:
            # Process terminated prematurely
            return False
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(0.2)
    return False


def _check_windows_webclient_service() -> bool:
    """Check if the Windows WebClient service is currently running."""
    if not IS_WINDOWS:
        return True
    try:
        res = subprocess.run(["sc", "query", "webclient"], capture_output=True, text=True)
        return "RUNNING" in res.stdout
    except Exception:
        return True


def _ensure_windows_webclient():
    """Attempt to start Windows WebClient service if stopped."""
    if not IS_WINDOWS:
        return
    try:
        query = subprocess.run(["sc", "query", "webclient"], capture_output=True, text=True)
        if "RUNNING" not in query.stdout:
            log("Windows WebClient service is not running. Attempting to start via 'net start webclient'...")
            res = subprocess.run(["net", "start", "webclient"], capture_output=True, text=True)
            log(f"'net start webclient' result: code={res.returncode}, out={res.stdout.strip()}, err={res.stderr.strip()}")
    except Exception as e:
        log(f"Error checking/starting WebClient service: {e}", level="WARNING")


def _print_log_tail(lines: int = 15):
    """Print the last lines of the log file for immediate troubleshooting."""
    log_p = get_log_file_path()
    if log_p.is_file():
        try:
            content = log_p.read_text(encoding="utf-8", errors="replace").splitlines()
            tail = content[-lines:]
            if tail:
                print(f"\n--- Recent Log Output ({log_p}) ---", file=sys.stderr)
                for l in tail:
                    print(l, file=sys.stderr)
                print("-" * 50, file=sys.stderr)
        except Exception:
            pass


def _mount_target(target: str, host: str, port: int) -> tuple[bool, str, int, str]:
    """Mount the WebDAV proxy to the target drive/directory.
    
    Returns (success, method, pid, error_message).
    """
    webdav_url = f"http://{host}:{port}/"
    log(f"Initiating OS-level mount: target={target}, url={webdav_url}")

    if IS_WINDOWS:
        _ensure_windows_webclient()

        # Disconnect any stale or existing connection on the target drive
        subprocess.run(["net", "use", target, "/delete", "/yes"], capture_output=True)

        print(f"Connecting Windows drive {target} -> {webdav_url} ...")
        res = subprocess.run(
            ["net", "use", target, webdav_url, "/persistent:no"],
            capture_output=True,
            text=True,
        )
        log(f"'net use {target} {webdav_url}' returncode: {res.returncode}\nstdout: {res.stdout.strip()}\nstderr: {res.stderr.strip()}")

        if res.returncode == 0:
            return True, "net_use", 0, ""

        err1 = (res.stderr or res.stdout).strip()

        # Fallback 1: Try with UNC path \\host@port\DavWWWRoot
        unc_path = f"\\\\{host}@{port}\\DavWWWRoot"
        log(f"Retrying mount with UNC path: {target} -> {unc_path} ...")
        print(f"Retrying with UNC path {target} -> {unc_path} ...")
        res_unc = subprocess.run(
            ["net", "use", target, unc_path, "/persistent:no"],
            capture_output=True,
            text=True,
        )
        log(f"'net use {target} {unc_path}' returncode: {res_unc.returncode}\nstdout: {res_unc.stdout.strip()}\nstderr: {res_unc.stderr.strip()}")

        if res_unc.returncode == 0:
            return True, "net_use", 0, ""

        err2 = (res_unc.stderr or res_unc.stdout).strip()
        final_err = f"{err1}\n{err2}".strip() if err2 and err2 != err1 else err1
        return False, "net_use", 0, final_err

    target_path = Path(target)
    target_path.mkdir(parents=True, exist_ok=True)

    if IS_DARWIN:
        print(f"Mounting WebDAV volume on {target_path} ...")
        res = subprocess.run(
            ["mount_webdav", webdav_url, str(target_path)],
            capture_output=True,
            text=True,
        )
        log(f"mount_webdav returncode: {res.returncode}\nstdout: {res.stdout}\nstderr: {res.stderr}")
        if res.returncode == 0:
            return True, "mount_webdav", 0, ""
        err = (res.stderr or res.stdout).strip()
        return False, "mount_webdav", 0, err

    # Linux FUSE mounting via rclone
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
            log(f"rclone mounted successfully (PID: {rproc.pid})")
            return True, "rclone", rproc.pid, ""
        log("rclone mount process did not stay running", level="WARNING")

    # Linux fallback via gio
    if shutil.which("gio"):
        print(f"Attempting gio (GVfs) mount -> dav://{host}:{port}/ ...")
        res = subprocess.run(
            ["gio", "mount", f"dav://{host}:{port}/"],
            capture_output=True,
            text=True,
        )
        log(f"gio mount output: {res.stdout} {res.stderr}")
        gvfs_mount = Path(f"/run/user/{os.getuid()}/gvfs/dav:host={host},port={port}")
        if gvfs_mount.exists():
            try:
                if target_path.exists() and not any(target_path.iterdir()) and not target_path.is_symlink():
                    target_path.rmdir()
                    target_path.symlink_to(gvfs_mount)
                return True, "gio", 0, ""
            except Exception as e:
                log(f"Failed symlinking GVfs mount: {e}", level="WARNING")

    err_msg = (
        f"WebDAV proxy is running on {webdav_url}\n"
        "To mount as a local folder in Linux, rclone is required (install via: ./install.sh)"
    )
    return False, "none", 0, err_msg


def _unmount_target(target: str, mount_method: str = "", host: str = "127.0.0.1", port: int = DEFAULT_PORT, rclone_pid: int = 0):
    """Unmount drive or directory and kill auxiliary mount daemons."""
    log(f"Unmounting target={target}, method={mount_method}")
    if IS_WINDOWS and target:
        print(f"Disconnecting Windows drive {target} ...")
        res = subprocess.run(["net", "use", target, "/delete", "/yes"], capture_output=True, text=True)
        log(f"'net use {target} /delete' returncode: {res.returncode}\n{res.stdout}\n{res.stderr}")
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
    setup_logging()
    log(f"muse-drive daemon started in pid {os.getpid()} on {args.host}:{args.port}")
    try:
        cookies_p = find_cookies_path()
        client = MuseWorkspaceClient(cookies_p)
    except Exception as e:
        log(f"Failed to initialize client in daemon: {e}", level="ERROR")
        _print_connection_error_guide(e)
        sys.exit(1)

    try:
        start_server(args.host, args.port, client)
    except Exception as e:
        log(f"Daemon server crashed: {e}", level="ERROR")
        sys.exit(1)


def cmd_mount(args):
    """Mount Muse workspace to a local drive letter or directory."""
    target = _resolve_target(args)
    host = args.host
    port = args.port
    log_path = get_log_file_path()

    setup_logging()

    # Check port availability and auto-fallback if using default port
    if _is_port_in_use(host, port):
        port_explicit = any(arg in sys.argv for arg in ("-p", "--port"))
        if port_explicit:
            print(f"Error: Port {port} is already in use or restricted by OS permissions.", file=sys.stderr)
            log(f"Port {port} is in use (explicitly specified). Aborting mount.", level="ERROR")
            sys.exit(1)
        available_p = _find_available_port(host, port)
        if available_p != port:
            print(f"Notice: Port {port} is busy or restricted, automatically using port {available_p} instead.")
            log(f"Port {port} busy, automatically switched to port {available_p}")
            port = available_p

    log(f"Executing 'mount' command for target '{target}' on {host}:{port}")

    state = load_daemon_state()
    if state and _is_process_running(state.get("pid", 0)):
        cur_target = state.get("target") or state.get("drive", "")
        cur_port = state.get("port", port)
        print(f"muse-drive is already mounted on {cur_target} (http://{host}:{cur_port}/, PID: {state.get('pid')})")
        print(f"Log file: {log_path}")
        return

    # Verify cookies.txt before starting
    cookies_p = None
    try:
        cookies_p = find_cookies_path()
        client = MuseWorkspaceClient(cookies_p)
        # Test connection & authentication
        client.ping()
        log("Successfully verified cookies and reached Muse gateway.")
    except Exception as e:
        log(f"Connection verification failed: {e}", level="ERROR")
        _print_connection_error_guide(e, cookies_p)
        sys.exit(1)

    if args.foreground:
        print(f"Starting muse-drive in foreground on http://{host}:{port}/ ...")
        print(f"Log file: {log_path}")
        ok, method, rclone_pid, err_msg = _mount_target(target, host, port)
        if not ok:
            print(f"Warning: Mount failed: {err_msg}", file=sys.stderr)
        try:
            start_server(host, port, client)
        finally:
            _unmount_target(target, method, host, port, rclone_pid)
        return

    # Spawn daemon process with output redirected to %TEMP%/muse-drive.log
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

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "a", encoding="utf-8", buffering=1)

    log(f"Spawning background daemon: {' '.join(daemon_cmd)}")

    if IS_WINDOWS:
        flags = 0x00000008 | 0x00000200
        proc = subprocess.Popen(
            daemon_cmd,
            creationflags=flags,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
    else:
        proc = subprocess.Popen(
            daemon_cmd,
            start_new_session=True,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

    log(f"Background daemon spawned with PID {proc.pid}")

    # Wait for WebDAV server to actively bind and accept connections
    print(f"Waiting for WebDAV proxy to start on http://{host}:{port}/ ...")
    if not _wait_for_server(host, port, timeout=10.0, proc=proc):
        log("Server failed to become responsive within 10 seconds", level="ERROR")
        print(f"Error: muse-drive daemon failed to start or respond on http://{host}:{port}/", file=sys.stderr)
        _print_log_tail()
        _kill_process(proc.pid)
        clear_daemon_state()
        sys.exit(1)

    # Perform OS-level mount
    ok, method, rclone_pid, mount_err = _mount_target(target, host, port)

    if not ok:
        log(f"Mount failed for {target}: {mount_err}", level="ERROR")
        print(f"\nError: Failed to mount {target}.", file=sys.stderr)
        if mount_err:
            print(f"Details: {mount_err}", file=sys.stderr)

        if IS_WINDOWS:
            if not _check_windows_webclient_service():
                print("\n[Windows WebClient 안내]", file=sys.stderr)
                print("Windows의 WebDAV 클라이언트(WebClient) 서비스가 실행 중이지 않습니다.", file=sys.stderr)
                print("관리자 권한 명령 프롬프트(cmd)에서 아래 명령어를 실행하여 서비스를 시작해 주세요:", file=sys.stderr)
                print("    net start webclient\n", file=sys.stderr)

        print(f"Log file: {log_path}", file=sys.stderr)
        _print_log_tail()

        print("Cleaning up daemon process ...", file=sys.stderr)
        _kill_process(proc.pid)
        clear_daemon_state()
        sys.exit(1)

    # SUCCESS: ONLY reached when ok is True
    save_daemon_state({
        "pid": proc.pid,
        "target": target,
        "drive": target,  # backwards compatibility
        "host": host,
        "port": port,
        "method": method,
        "rclone_pid": rclone_pid,
        "log_file": str(log_path),
    })

    log(f"Mount succeeded on {target} (PID: {proc.pid})")
    print(f"Mounted successfully:")
    target_label = "Drive" if IS_WINDOWS else "Mount Path"
    print(f"  {target_label}:  {target} [Muse Workspace]")
    print(f"  WebDAV URL:  http://{host}:{port}/")
    print(f"  PID:         {proc.pid}")
    print(f"  Log file:    {log_path}")


def cmd_umount(args):
    """Unmount Muse workspace drive and stop daemon."""
    state = load_daemon_state()
    target = _resolve_target(args) if (args.target or args.target_opt or args.drive) else (
        state.get("target") or state.get("drive") if state else _default_target()
    )
    mount_method = state.get("method", "") if state else ""
    rclone_pid = state.get("rclone_pid", 0) if state else 0
    host = state.get("host", "127.0.0.1") if state else "127.0.0.1"
    port = state.get("port", DEFAULT_PORT) if state else DEFAULT_PORT

    setup_logging()
    log(f"Executing 'umount' command for target '{target}'")

    _unmount_target(target, mount_method, host, port, rclone_pid)

    if state:
        pid = state.get("pid", 0)
        if _is_process_running(pid):
            print(f"Stopping muse-drive daemon (PID: {pid}) ...")
            _kill_process(pid)
        clear_daemon_state()
        log("Daemon stopped and state cleared.")
        print("Daemon stopped.")
    else:
        print("No active muse-drive daemon state found.")


def cmd_status(args):
    """Show current mount and daemon status."""
    log_path = get_log_file_path()
    state = load_daemon_state()
    if not state or not _is_process_running(state.get("pid", 0)):
        print("Status: Not mounted (daemon is stopped)")
        print(f"Log file: {log_path}")
        if state:
            clear_daemon_state()
        return

    target = state.get("target") or state.get("drive", "")
    host = state.get("host", "127.0.0.1")
    port = state.get("port", DEFAULT_PORT)
    pid = state.get("pid")

    print(f"Status: Mounted and Running")
    target_label = "Drive" if IS_WINDOWS else "Mount Path"
    if target:
        print(f"  {target_label}:  {target}")
    print(f"  WebDAV URL: http://{host}:{port}/")
    print(f"  PID:        {pid}")
    print(f"  Log file:   {log_path}")


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
    p_mount.add_argument("--port", "-p", type=int, default=DEFAULT_PORT, help=f"Local WebDAV port (default: {DEFAULT_PORT})")
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
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()

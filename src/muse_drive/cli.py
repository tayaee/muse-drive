"""Command Line Interface for muse-drive."""
import argparse
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path

from .client import MuseWorkspaceClient, find_cookies_path
from .server import (
    clear_daemon_state,
    load_daemon_state,
    save_daemon_state,
    start_server,
)

IS_WINDOWS = platform.system().lower() == "windows"


def _normalize_drive_letter(drive: str) -> str:
    """Normalize drive letter like 'M' or 'm:' to 'M:'."""
    d = drive.strip().rstrip(":\\/").upper()
    return f"{d}:"


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


def cmd_serve(args):
    """Internal command: run the WebDAV server in the current process."""
    client = MuseWorkspaceClient()
    start_server(args.host, args.port, client)


def cmd_mount(args):
    """Mount Muse workspace to a local drive letter."""
    drive = _normalize_drive_letter(args.drive) if args.drive else ("M:" if IS_WINDOWS else "")
    host = args.host
    port = args.port

    state = load_daemon_state()
    if state and _is_process_running(state.get("pid", 0)):
        cur_drive = state.get("drive", "")
        cur_port = state.get("port", port)
        print(f"muse-drive is already mounted on {cur_drive} (http://{host}:{cur_port}/, PID: {state.get('pid')})")
        return

    # Verify cookies.txt before starting
    try:
        cookies_p = find_cookies_path()
        client = MuseWorkspaceClient(cookies_p)
        # Quick ping test
        client.stat("")
    except Exception as e:
        print(f"Error connecting to Muse workspace: {e}", file=sys.stderr)
        sys.exit(1)

    if args.foreground:
        print(f"Starting muse-drive in foreground on http://{host}:{port}/ ...")
        if IS_WINDOWS and drive:
            subprocess.run(["net", "use", drive, f"http://{host}:{port}/", "/persistent:no"])
        try:
            start_server(host, port, client)
        finally:
            if IS_WINDOWS and drive:
                subprocess.run(["net", "use", drive, "/delete", "/yes"], capture_output=True)
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
        # DETACHED_PROCESS = 0x00000008, CREATE_NEW_PROCESS_GROUP = 0x00000200
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

    save_daemon_state({"pid": proc.pid, "drive": drive, "host": host, "port": port})

    # Mount network drive in Windows
    if IS_WINDOWS and drive:
        print(f"Connecting Windows drive {drive} -> http://{host}:{port}/ ...")
        res = subprocess.run(
            ["net", "use", drive, f"http://{host}:{port}/", "/persistent:no"],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            print(f"Warning: 'net use' returned error: {res.stderr.strip()}", file=sys.stderr)
            print("Note: You can also open the URL directly in File Explorer: http://127.0.0.1:8080/")

    print(f"Mounted successfully:")
    if drive:
        print(f"  Drive:       {drive} [Muse Workspace]")
    print(f"  WebDAV URL:  http://{host}:{port}/")
    print(f"  PID:         {proc.pid}")


def cmd_umount(args):
    """Unmount Muse workspace drive and stop daemon."""
    state = load_daemon_state()
    drive = _normalize_drive_letter(args.drive) if args.drive else (state.get("drive", "M:") if state else "M:")

    if IS_WINDOWS and drive:
        print(f"Disconnecting Windows drive {drive} ...")
        res = subprocess.run(["net", "use", drive, "/delete", "/yes"], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"Drive {drive} disconnected.")
        else:
            print(f"Notice: {res.stderr.strip() or 'Drive was not actively mapped.'}")

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

    drive = state.get("drive", "")
    host = state.get("host", "127.0.0.1")
    port = state.get("port", 8080)
    pid = state.get("pid")

    print(f"Status: Mounted and Running")
    if drive:
        print(f"  Drive:      {drive}")
    print(f"  WebDAV URL: http://{host}:{port}/")
    print(f"  PID:        {pid}")


def main():
    parser = argparse.ArgumentParser(
        prog="muse-drive",
        description="Mount Muse AI cloud workspace as a Windows drive via local WebDAV proxy",
    )
    sub = parser.add_subparsers(dest="subcommand")

    # mount
    p_mount = sub.add_parser("mount", help="Mount workspace as a local drive")
    p_mount.add_argument("--drive", "-d", default="M:", help="Drive letter (e.g. M:)")
    p_mount.add_argument("--host", default="127.0.0.1", help="Local host binding (default: 127.0.0.1)")
    p_mount.add_argument("--port", "-p", type=int, default=8080, help="Local WebDAV port (default: 8080)")
    p_mount.add_argument("--foreground", "-f", action="store_true", help="Run server in foreground")
    p_mount.set_defaults(func=cmd_mount)

    # umount / unmount
    p_umount = sub.add_parser("umount", aliases=["unmount"], help="Unmount workspace drive")
    p_umount.add_argument("--drive", "-d", help="Drive letter to disconnect")
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

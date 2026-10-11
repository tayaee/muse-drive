"""High-level client for Muse workspace file operations."""
import base64
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

from .gateway import GatewayClient, load_cookies, AuthError, GatewayError

CHUNK_SIZE = 32 * 1024  # 32KB chunks compliant with Noise protocol frame limits


def get_default_cookies_path() -> Path:
    """Return the expected cookies.txt path for the current OS."""
    env_path = os.environ.get("MUSE_COOKIES_PATH")
    if env_path:
        return Path(env_path)
    if sys.platform.startswith("win"):
        win_profile = os.environ.get("USERPROFILE")
        if win_profile:
            return Path(win_profile) / ".config" / "muse-cli" / "cookies.txt"
    return Path.home() / ".config" / "muse-cli" / "cookies.txt"


def find_cookies_path() -> Path:
    """Locate the cookies.txt file across platforms (Windows %USERPROFILE% / Linux ~/.config)."""
    env_path = os.environ.get("MUSE_COOKIES_PATH")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p
        raise FileNotFoundError(f"MUSE_COOKIES_PATH is set to '{p}', but this file does not exist.")

    # Standard location: ~/.config/muse-cli/cookies.txt
    user_home = Path.home()
    standard_p = user_home / ".config" / "muse-cli" / "cookies.txt"
    if standard_p.is_file():
        return standard_p

    # Windows specific fallback if Path.home() differs from USERPROFILE
    win_profile = os.environ.get("USERPROFILE")
    if win_profile:
        win_p = Path(win_profile) / ".config" / "muse-cli" / "cookies.txt"
        if win_p.is_file():
            return win_p

    expected_p = get_default_cookies_path()
    raise FileNotFoundError(
        f"cookies.txt not found at: {expected_p}\n"
        "Please set up your cookies.txt file by referring to https://github.com/tayaee/muse-drive "
        "(or set custom path via MUSE_COOKIES_PATH)."
    )


class MuseWorkspaceClient:
    """Thread-safe client for interacting with Muse cloud workspace."""

    def __init__(self, cookies_path: Path | None = None):
        self.cookies_path = cookies_path or find_cookies_path()
        self._lock = threading.Lock()
        self._client: GatewayClient | None = None
        self._cache_dir: dict[str, tuple[float, list[dict]]] = {}
        self._cache_stat: dict[str, tuple[float, dict | None]] = {}
        self.cache_ttl = 3.0  # 3-second cache to optimize frequent Windows Explorer requests

    def _get_client(self) -> GatewayClient:
        with self._lock:
            if self._client is None:
                cookies = load_cookies(str(self.cookies_path))
                self._client = GatewayClient(cookies=cookies)
            return self._client

    def _reset_client(self):
        with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None

    def call_with_retry(self, method: str, body: dict[str, Any], retries: int = 1) -> dict[str, Any]:
        """Call gateway API with automatic reconnection on disconnect."""
        for attempt in range(retries + 1):
            client = self._get_client()
            try:
                res = client.call_json(method, body=body)
                return res
            except Exception as e:
                self._reset_client()
                if attempt == retries:
                    raise

    def ping(self) -> bool:
        """Test authentication and connection to the Muse gateway. Raises on failure."""
        self.call_with_retry("fs.stat", {"path": "workspace"}, retries=0)
        return True

    def normalize_path(self, rel_path: str) -> str:
        """Ensure path resolves relative to workspace."""
        p = rel_path.strip().replace("\\", "/").strip("/")
        if not p or p == ".":
            return "workspace"
        if p == "workspace" or p.startswith("workspace/"):
            return p
        return f"workspace/{p}"

    def invalidate_cache(self, rel_path: str | None = None):
        if rel_path is None:
            self._cache_dir.clear()
            self._cache_stat.clear()
        else:
            p = self.normalize_path(rel_path)
            self._cache_dir.pop(p, None)
            self._cache_stat.pop(p, None)
            parent = "/".join(p.split("/")[:-1])
            self._cache_dir.pop(parent, None)

    def list_dir(self, rel_path: str) -> list[dict]:
        """List entries in a workspace folder. Returns list of entry dicts."""
        norm_path = self.normalize_path(rel_path)
        now = time.time()
        cached = self._cache_dir.get(norm_path)
        if cached and (now - cached[0] < self.cache_ttl):
            return cached[1]

        res = self.call_with_retry("fs.list", {"path": norm_path})
        entries = res.get("entries", [])
        self._cache_dir[norm_path] = (now, entries)
        return entries

    def stat(self, rel_path: str) -> dict | None:
        """Get stat info for a file or directory, or None if not found."""
        norm_path = self.normalize_path(rel_path)
        now = time.time()
        cached = self._cache_stat.get(norm_path)
        if cached and (now - cached[0] < self.cache_ttl):
            return cached[1]

        try:
            res = self.call_with_retry("fs.stat", {"path": norm_path})
            r = res.get("result", res) if isinstance(res, dict) else res
            self._cache_stat[norm_path] = (now, r)
            return r
        except Exception:
            self._cache_stat[norm_path] = (now, None)
            return None

    def read_file(self, rel_path: str, offset: int = 0, length: int | None = None) -> bytes:
        """Read binary data from a workspace file."""
        norm_path = self.normalize_path(rel_path)
        stat_res = self.stat(rel_path)
        total_size = stat_res.get("size", 0) if stat_res else 0

        target_len = (total_size - offset) if length is None else length
        if target_len <= 0 and total_size > 0:
            return b""

        chunks = []
        cur_offset = offset
        remaining = target_len

        while remaining > 0 or (target_len <= 0 and cur_offset == 0):
            fetch_len = min(CHUNK_SIZE, remaining) if remaining > 0 else CHUNK_SIZE
            body = {"path": norm_path, "offset": cur_offset, "len": fetch_len}
            read_res = self.call_with_retry("fs.read", body)
            res_data = read_res.get("result", read_res) if isinstance(read_res, dict) else {}
            b64_part = res_data.get("data_base64")
            if not b64_part:
                break
            part_bytes = base64.b64decode(b64_part)
            chunks.append(part_bytes)
            cur_offset += len(part_bytes)
            if remaining > 0:
                remaining -= len(part_bytes)
            if res_data.get("eof") or len(part_bytes) < fetch_len:
                break

        return b"".join(chunks)

    def write_file(self, rel_path: str, data: bytes, overwrite: bool = True):
        """Write binary data to a workspace file using chunked upload."""
        norm_path = self.normalize_path(rel_path)
        offset = 0
        is_first = True
        total = len(data)

        while True:
            chunk = data[offset : offset + CHUNK_SIZE]
            if not chunk and not is_first:
                break

            b64_data = base64.b64encode(chunk).decode("ascii")
            body = {
                "path": norm_path,
                "data_base64": b64_data,
                "overwrite": overwrite if is_first else False,
                "append": not is_first,
                "create_parent": True,
            }
            res = self.call_with_retry("fs.write", body)
            if not res.get("ok"):
                err = res.get("error", "write error")
                raise RuntimeError(f"failed to write {norm_path}: {err}")

            offset += len(chunk)
            is_first = False
            if offset >= total:
                break

        self.invalidate_cache(rel_path)

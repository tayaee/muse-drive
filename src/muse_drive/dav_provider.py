"""WsgiDAV Provider implementation mapping WebDAV methods to Muse workspace."""
import io
import time
from datetime import datetime
from typing import Any

from wsgidav.dav_provider import DAVCollection, DAVNonCollection, DAVProvider

from .client import MuseWorkspaceClient


def _iso_to_timestamp(iso_str: str | None) -> float:
    if not iso_str:
        return time.time()
    try:
        cleaned = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt.timestamp()
    except Exception:
        return time.time()


def _clean_dav_path(path: str) -> str:
    """Normalize WebDAV path by stripping DavWWWRoot prefix used by Windows."""
    p = path.strip("/")
    if p.lower() == "davwwwroot":
        return ""
    if p.lower().startswith("davwwwroot/"):
        return p[len("davwwwroot/"):].strip("/")
    return p


class MuseFileResource(DAVNonCollection):
    """Represents a regular file stored in Muse workspace."""

    def __init__(self, path: str, environ: dict, provider: "MuseDAVProvider", stat_data: dict | None = None):
        super().__init__(path, environ)
        self.provider = provider
        self.client: MuseWorkspaceClient = provider.client
        self.rel_path = _clean_dav_path(path)
        self._stat = stat_data or self.client.stat(self.rel_path)

    def get_content_length(self) -> int:
        if self._stat:
            return self._stat.get("size", 0)
        return 0

    def get_content_type(self) -> str:
        name = self.name.lower()
        if name.endswith(".png"):
            return "image/png"
        if name.endswith(".jpg") or name.endswith(".jpeg"):
            return "image/jpeg"
        if name.endswith(".json"):
            return "application/json"
        if name.endswith(".md"):
            return "text/markdown"
        if name.endswith(".txt"):
            return "text/plain"
        return "application/octet-stream"

    def get_creation_date(self) -> float:
        return self.get_last_modified()

    def get_last_modified(self) -> float:
        if self._stat:
            m = self._stat.get("modifiedAt") or self._stat.get("modified_ms")
            if isinstance(m, (int, float)):
                return m / 1000.0
            if isinstance(m, str):
                return _iso_to_timestamp(m)
        return self.provider.start_time

    def support_etag(self) -> bool:
        return True

    def get_etag(self) -> str:
        last_m = self.get_last_modified()
        size = self.get_content_length()
        return f"{int(last_m)}-{size}"

    def support_ranges(self) -> bool:
        return True

    def get_content(self) -> io.BytesIO:
        data = self.client.read_file(self.rel_path)
        return io.BytesIO(data)

    def begin_write(self, content_type: str | None = None) -> io.BytesIO:
        class _UploadBuffer(io.BytesIO):
            def __init__(self, res: "MuseFileResource"):
                super().__init__()
                self.res = res

            def close(self):
                val = self.getvalue()
                super().close()
                self.res.client.write_file(self.res.rel_path, val, overwrite=True)

        return _UploadBuffer(self)

    def delete(self):
        pass


class MuseDirectoryResource(DAVCollection):
    """Represents a directory in Muse workspace."""

    def __init__(self, path: str, environ: dict, provider: "MuseDAVProvider"):
        super().__init__(path, environ)
        self.provider = provider
        self.client: MuseWorkspaceClient = provider.client
        self.rel_path = _clean_dav_path(path)

    def get_creation_date(self) -> float:
        return self.get_last_modified()

    def get_last_modified(self) -> float:
        if self.rel_path:
            stat_data = self.client.stat(self.rel_path)
            if stat_data:
                m = stat_data.get("modifiedAt") or stat_data.get("modified_ms")
                if isinstance(m, (int, float)):
                    return m / 1000.0
                if isinstance(m, str):
                    return _iso_to_timestamp(m)
        return self.provider.start_time

    def get_member_names(self) -> list[str]:
        entries = self.client.list_dir(self.rel_path)
        return [e.get("name", "") for e in entries if e.get("name")]

    def get_member_list(self) -> list[DAVCollection | DAVNonCollection]:
        entries = self.client.list_dir(self.rel_path)
        members = []
        for e in entries:
            name = e.get("name", "")
            child_path = f"{self.path.rstrip('/')}/{name}"
            is_dir = e.get("type") in ("directory", "dir") or e.get("kind") in ("directory", "dir")
            if is_dir:
                members.append(MuseDirectoryResource(child_path, self.environ, self.provider))
            else:
                members.append(MuseFileResource(child_path, self.environ, self.provider, stat_data=e))
        return members

    def get_member(self, name: str) -> DAVCollection | DAVNonCollection | None:
        child_path = f"{self.path.rstrip('/')}/{name}"
        return self.provider.get_resource_inst(child_path, self.environ)

    def create_empty_resource(self, name: str) -> MuseFileResource:
        child_path = f"{self.path.rstrip('/')}/{name}"
        res = MuseFileResource(child_path, self.environ, self.provider)
        self.client.write_file(res.rel_path, b"", overwrite=True)
        return res

    def create_collection(self, name: str):
        child_path = f"{self.path.rstrip('/')}/{name}"
        self.client.invalidate_cache(self.rel_path)
        return MuseDirectoryResource(child_path, self.environ, self.provider)


class MuseDAVProvider(DAVProvider):
    """Custom WsgiDAV Provider mapping WebDAV URIs to Muse workspace."""

    def __init__(self, client: MuseWorkspaceClient):
        super().__init__()
        self.client = client
        self.start_time = time.time()

    def get_resource_inst(self, path: str, environ: dict) -> DAVCollection | DAVNonCollection | None:
        clean_path = _clean_dav_path(path)

        if not clean_path:
            return MuseDirectoryResource(path, environ, self)

        stat_data = self.client.stat(clean_path)
        if stat_data:
            if stat_data.get("kind") in ("dir", "directory") or stat_data.get("type") in ("dir", "directory"):
                return MuseDirectoryResource(path, environ, self)
            return MuseFileResource(path, environ, self, stat_data=stat_data)

        # Fallback check through parent directory listing
        parent_rel = "/".join(clean_path.split("/")[:-1])
        base_name = clean_path.split("/")[-1]
        try:
            parent_entries = self.client.list_dir(parent_rel)
            for e in parent_entries:
                if e.get("name") == base_name:
                    if e.get("type") in ("dir", "directory") or e.get("kind") in ("dir", "directory"):
                        return MuseDirectoryResource(path, environ, self)
                    return MuseFileResource(path, environ, self, stat_data=e)
        except Exception:
            pass

        return None

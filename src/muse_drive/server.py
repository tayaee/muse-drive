"""WebDAV server runner using WsgiDAV and cheroot."""
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

from cheroot import wsgi
from wsgidav.wsgidav_app import WsgiDAVApp

from .client import MuseWorkspaceClient
from .dav_provider import MuseDAVProvider


def get_state_dir() -> Path:
    base = Path.home() / ".config" / "muse-drive"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_state_file() -> Path:
    return get_state_dir() / "daemon_state.json"


def save_daemon_state(data: dict[str, Any]):
    get_state_file().write_text(json.dumps(data, indent=2))


def load_daemon_state() -> dict[str, Any] | None:
    sf = get_state_file()
    if sf.is_file():
        try:
            return json.loads(sf.read_text())
        except Exception:
            return None
    return None


def clear_daemon_state():
    sf = get_state_file()
    if sf.is_file():
        sf.unlink()


def create_app(client: MuseWorkspaceClient) -> WsgiDAVApp:
    provider = MuseDAVProvider(client)
    config = {
        "host": "127.0.0.1",
        "port": 8080,
        "mount_path": "",
        "provider_mapping": {"/": provider},
        "http_authenticator": {
            "domain": "Muse Workspace",
            "accept_basic": True,
            "accept_digest": False,
            "default_to_digest": False,
        },
        "simple_dc": {
            "user_mapping": {"*": True},  # Allow anonymous access on localhost
        },
        "verbose": 1,
        "enable_ms_attach": True,  # Enable MS WebDAV Mini-Redirector compatibility
    }
    return WsgiDAVApp(config)


def start_server(host: str, port: int, client: MuseWorkspaceClient):
    app = create_app(client)
    server = wsgi.Server(bind_addr=(host, port), wsgi_app=app, numthreads=10)
    print(f"Muse WebDAV server running at http://{host}:{port}/")
    try:
        server.start()
    except (KeyboardInterrupt, SystemExit):
        server.stop()

"""Logging utilities for muse-drive."""
import logging
import os
import sys
import tempfile
from pathlib import Path


def get_log_file_path() -> Path:
    """Return %TEMP%\\muse-drive.log on Windows, /tmp/muse-drive.log on Linux/macOS."""
    if sys.platform.startswith("win"):
        temp_dir = os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir()
        return Path(temp_dir) / "muse-drive.log"
    return Path(tempfile.gettempdir()) / "muse-drive.log"


def get_logger(name: str = "muse_drive") -> logging.Logger:
    return logging.getLogger(name)


def setup_logging(verbose: bool = True):
    """Configure root logger to append to %TEMP%/muse-drive.log."""
    log_path = get_log_file_path()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Avoid duplicate file handlers
    has_file_handler = any(
        isinstance(h, logging.FileHandler) and Path(getattr(h, "baseFilename", "")) == log_path
        for h in root.handlers
    )
    if not has_file_handler:
        try:
            fh = logging.FileHandler(str(log_path), mode="a", encoding="utf-8")
            fh.setFormatter(formatter)
            root.addHandler(fh)
        except Exception:
            pass

    for log_name in ("wsgidav", "cheroot.error", "cheroot.access", "muse_drive"):
        l = logging.getLogger(log_name)
        l.setLevel(logging.INFO)


def log(msg: str, level: str = "INFO"):
    """Quick log helper that records to %TEMP%/muse-drive.log."""
    setup_logging()
    lg = get_logger("muse_drive")
    lvl = getattr(logging, level.upper(), logging.INFO)
    lg.log(lvl, msg)

"""Logging utilities for muse-drive."""
import logging
import os
import sys
import tempfile
from pathlib import Path


def get_log_file_path() -> Path | None:
    """Disabled file logging - returns None."""
    return None


def get_logger(name: str = "muse_drive") -> logging.Logger:
    return logging.getLogger(name)


def setup_logging(verbose: bool = True):
    """Configure root logger to output directly to stdout."""
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Avoid duplicate stdout stream handlers
    has_stdout_handler = any(
        isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stdout
        for h in root.handlers
    )
    if not has_stdout_handler:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        root.addHandler(sh)

    for log_name in ("wsgidav", "cheroot.error", "cheroot.access", "muse_drive"):
        l = logging.getLogger(log_name)
        l.setLevel(logging.INFO)


def log(msg: str, level: str = "INFO"):
    """Quick log helper that outputs to stdout."""
    setup_logging()
    lg = get_logger("muse_drive")
    lvl = getattr(logging, level.upper(), logging.INFO)
    lg.log(lvl, msg)


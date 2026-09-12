"""Centralized logging configuration.

Call `setup_logging()` once, early, from main.py. Every module then just
does `logger = logging.getLogger(__name__)` and inherits this config --
no per-module handler setup, no duplicate log lines.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

_DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(
    log_dir: str | Path = "logs",
    log_filename: str = "app.log",
    level: str = "INFO",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    """Configure the root logger with a console handler (stdout) and a
    rotating file handler.

    Args:
        log_dir: directory the log file lives in (created if missing).
        log_filename: name of the log file within log_dir.
        level: minimum level name ("DEBUG", "INFO", "WARNING", "ERROR").
        max_bytes: rotate after the file reaches this size.
        backup_count: number of rotated backups to keep.
    """
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    log_path = log_dir_path / log_filename

    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers if setup_logging() is accidentally called
    # more than once (e.g. in tests that import main multiple times).
    root_logger.handlers.clear()

    formatter = logging.Formatter(_DEFAULT_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    logging.getLogger(__name__).info(
        "Logging initialized: level=%s file=%s", level, log_path
    )

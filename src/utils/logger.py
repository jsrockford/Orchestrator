"""
Logging helpers for the orchestration project.

Reads defaults from config.yaml when available and wires up console/file output.
"""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Tuple

try:
    from .config_loader import get_config  # type: ignore circular import false positive
except Exception:  # pragma: no cover - config access optional during bootstrap
    get_config = None  # type: ignore[assignment]


DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"

_LOGGING_DEFAULTS: Optional[Tuple[int, str, bool, int, int]] = None
_LOGGING_FORMAT: str = DEFAULT_FORMAT


def get_timestamped_log_path(base_log_path: str) -> str:
    """
    Convert a log file path to include a timestamp.

    Example:
        logs/orchestrator.log -> logs/orchestrator_2025-11-11_08-30-45.log

    Args:
        base_log_path: Original log file path from config

    Returns:
        Log path with timestamp inserted before extension
    """
    log_path = Path(base_log_path)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    stem = log_path.stem
    suffix = log_path.suffix
    new_name = f"{stem}_{timestamp}{suffix}"
    return str(log_path.parent / new_name)


def _load_logging_defaults() -> Tuple[int, Optional[str], bool, Optional[int], Optional[int], str]:
    """
    Resolve logging defaults from config.yaml (if available).
    """
    global _LOGGING_DEFAULTS, _LOGGING_FORMAT
    if _LOGGING_DEFAULTS is not None:
        level, log_file, console, max_bytes, backup_count = _LOGGING_DEFAULTS
        return (
            level,
            log_file or None,
            console,
            max_bytes or None,
            backup_count or None,
            _LOGGING_FORMAT,
        )

    level = logging.INFO
    log_file: Optional[str] = None
    console = True
    max_bytes: Optional[int] = None
    backup_count: Optional[int] = None
    fmt = DEFAULT_FORMAT

    if get_config is not None:
        try:
            config = get_config().get_section("logging") or {}
        except Exception:  # pragma: no cover - config access may fail at import time
            config = {}
        level_str = str(config.get("level", "INFO")).upper()
        level = getattr(logging, level_str, logging.INFO)
        base_log_file = config.get("file") or None
        # Add timestamp to log filename for each run
        if base_log_file:
            log_file = get_timestamped_log_path(base_log_file)
        console = bool(config.get("console", True))
        max_bytes_val = config.get("max_bytes")
        backup_count_val = config.get("backup_count")
        fmt = config.get("format", DEFAULT_FORMAT)
        if isinstance(max_bytes_val, int) and max_bytes_val > 0:
            max_bytes = max_bytes_val
        if isinstance(backup_count_val, int) and backup_count_val >= 0:
            backup_count = backup_count_val

    _LOGGING_DEFAULTS = (level, log_file or "", console, max_bytes or 0, backup_count or 0)
    _LOGGING_FORMAT = fmt
    return level, log_file, console, max_bytes, backup_count, fmt


def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    level: int = logging.INFO,
    console: bool = True,
    *,
    fmt: Optional[str] = None,
    max_bytes: Optional[int] = None,
    backup_count: Optional[int] = None,
) -> logging.Logger:
    """
    Set up a logger with file and/or console handlers.

    Args:
        name: Logger name (typically __name__)
        log_file: Path to log file (optional)
        level: Logging level (default: INFO)
        console: Whether to also log to console (default: True)
        fmt: Optional log format string
        max_bytes: Enable rotating file handler if provided (>0)
        backup_count: Number of backup files for rotating handler

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    pattern = fmt or DEFAULT_FORMAT
    formatter = logging.Formatter(pattern, datefmt=DEFAULT_DATEFMT)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Create handler with immediate flush capability
        if max_bytes and max_bytes > 0:
            base_handler_class = RotatingFileHandler
            handler_args = (log_file, )
            handler_kwargs = {'maxBytes': max_bytes, 'backupCount': backup_count or 0}
        else:
            base_handler_class = logging.FileHandler
            handler_args = (log_file, )
            handler_kwargs = {}

        # Create a custom handler that flushes immediately after each emit
        class ImmediateFlushFileHandler(base_handler_class):
            def emit(self, record):
                super().emit(record)
                # Flush immediately to ensure logs are written even on crashes
                if hasattr(self, 'stream') and self.stream:
                    self.stream.flush()

        handler = ImmediateFlushFileHandler(*handler_args, **handler_kwargs)
        handler.setLevel(level)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get an existing logger or create one honouring config defaults.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        level, log_file, console, max_bytes, backup_count, fmt = _load_logging_defaults()
        return setup_logger(
            name,
            log_file=log_file,
            level=level,
            console=console,
            fmt=fmt,
            max_bytes=max_bytes,
            backup_count=backup_count,
        )

    return logger

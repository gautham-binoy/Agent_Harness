"""Structured logging configuration for the adaptive harness."""

from __future__ import annotations

import logging
import sys
from datetime import datetime


class CleanFormatter(logging.Formatter):
    """Clean, human-readable log formatter adhering to evaluation spec."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname
        msg = record.getMessage()
        return f"{timestamp} {level} {msg}"


def setup_logger(name: str = "harness", log_level: str = "INFO") -> logging.Logger:
    """Initialize and configure a clean structured logger."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Prevent adding duplicate handlers if setup_logger is called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(CleanFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger


logger = setup_logger()

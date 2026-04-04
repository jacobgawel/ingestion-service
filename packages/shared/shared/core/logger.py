"""Custom logging configuration for the ingestion service.

This module provides a logging setup similar to RapidOCR's format:
[LEVEL] timestamp [LoggerName] filename:line_number: message
"""

import logging
import sys
from typing import Optional


class CustomFormatter(logging.Formatter):
    """Custom formatter that mimics RapidOCR's logging format."""

    def __init__(self, logger_name: str = "IngestionService"):
        self.logger_name = logger_name
        # Format: [LEVEL] timestamp [LoggerName] filename:line_number: message
        super().__init__(
            fmt=f"[%(levelname)s] %(asctime)s [{self.logger_name}] %(filename)s:%(lineno)d: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def formatTime(self, record, datefmt=None):
        """Override formatTime to include milliseconds in the RapidOCR format."""
        import time

        ct = self.converter(record.created)
        if datefmt:
            s = time.strftime(datefmt, ct)
        else:
            s = time.strftime("%Y-%m-%d %H:%M:%S", ct)
        # Add milliseconds
        s = f"{s},{int(record.msecs):03d}"
        return s


def setup_logger(
    name: str = "IngestionService",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """Set up and return a logger with custom formatting.

    Args:
        name: The name to display in the log output (e.g., "IngestionService")
        level: The logging level (default: logging.INFO)
        log_file: Optional file path to write logs to (in addition to console)

    Returns:
        A configured logger instance

    Example:
        >>> from shared.core.logger import setup_logger
        >>> logger = setup_logger("IngestionService")
        >>> logger.info("Processing started")
        [INFO] 2026-02-15 23:20:15,123 [IngestionService] my_file.py:45: Processing started
    """
    logger = logging.getLogger(name)

    # Prevent adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False  # Prevent duplicate logs

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(CustomFormatter(name))
    logger.addHandler(console_handler)

    # Optional file handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(CustomFormatter(name))
        logger.addHandler(file_handler)

    return logger


def get_logger(
    name: str = "IngestionService", level: int = logging.INFO
) -> logging.Logger:
    """Get a logger instance with custom formatting.

    This is a convenience wrapper around setup_logger that can be called
    multiple times without adding duplicate handlers.

    Args:
        name: The name to display in the log output
        level: The logging level (default: logging.INFO)

    Returns:
        A configured logger instance
    """
    return setup_logger(name=name, level=level)


def configure_uvicorn_logging(log_level: int = logging.INFO) -> dict:
    """Configure uvicorn logging to use custom formatter.

    Returns a logging config dict that can be passed to uvicorn.run()

    Args:
        log_level: The logging level for uvicorn loggers

    Returns:
        Logging configuration dictionary for uvicorn
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "custom": {
                "()": CustomFormatter,
                "logger_name": "Uvicorn",
            },
            "access": {
                "()": CustomFormatter,
                "logger_name": "UvicornAccess",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "custom",
                "stream": "ext://sys.stdout",
            },
            "access": {
                "class": "logging.StreamHandler",
                "formatter": "access",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["access"],
                "level": log_level,
                "propagate": False,
            },
        },
    }


# Default logger instance for the ingestion service
logger = setup_logger("IngestionService", level=logging.INFO)

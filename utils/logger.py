"""
Centralized logging configuration for the Agent Bridge service.

This module provides a consistent logging setup using Rich for colorful output.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from rich.logging import RichHandler


def _get_log_level() -> int:
    """Get log level from environment variable or default to INFO."""
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return log_level_map.get(log_level_str, logging.INFO)


def _get_log_file() -> Optional[Path]:
    """Get log file path from environment variable."""
    log_file = os.getenv("LOG_FILE")
    if log_file:
        return Path(log_file)
    return None


def setup_logging(log_level: Optional[int] = None, log_file: Optional[Path] = None) -> None:
    """
    Set up centralized logging configuration.

    Args:
        log_level: Log level to use (defaults to LOG_LEVEL env var or INFO)
        log_file: Optional path to log file (defaults to LOG_FILE env var or None)
    """
    # Get configuration from parameters or environment
    level = log_level if log_level is not None else _get_log_level()
    file_path = log_file if log_file is not None else _get_log_file()

    # Clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Set root logger level
    root_logger.setLevel(level)

    # Create console handler with Rich
    # RichHandler handles its own formatting with colors and styling
    console_handler = RichHandler(
        rich_tracebacks=True,
        show_path=True,
        show_time=True,
        show_level=True,
        markup=True,
        console=None,  # Use default console (stdout)
    )
    console_handler.setLevel(level)

    # Add console handler
    root_logger.addHandler(console_handler)

    # Add file handler if log file is specified
    file_handler: Optional[logging.FileHandler] = None
    if file_path:
        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create file handler (plain text, no colors)
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setLevel(level)

        # Create formatter for file (detailed, no colors)
        file_format = logging.Formatter(
            fmt="%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_format)

        # Add file handler
        root_logger.addHandler(file_handler)

    # Configure uvicorn loggers to use our setup
    # Disable propagation to prevent duplicate logs (uvicorn -> root logger)
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(level)
    uvicorn_logger.propagate = False
    uvicorn_logger.handlers.clear()
    uvicorn_logger.addHandler(console_handler)
    if file_handler is not None:
        uvicorn_logger.addHandler(file_handler)

    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.setLevel(level)
    uvicorn_access_logger.propagate = False
    uvicorn_access_logger.handlers.clear()
    uvicorn_access_logger.addHandler(console_handler)
    if file_handler is not None:
        uvicorn_access_logger.addHandler(file_handler)

    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    uvicorn_error_logger.setLevel(level)
    uvicorn_error_logger.propagate = False
    uvicorn_error_logger.handlers.clear()
    uvicorn_error_logger.addHandler(console_handler)
    if file_handler is not None:
        uvicorn_error_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        Logger instance configured with the centralized setup
    """
    return logging.getLogger(name)


# Initialize logging with defaults when module is imported
# This ensures logging works even if modules are imported before main() runs
# main.py can call setup_logging() again to reconfigure with command-line args
setup_logging()

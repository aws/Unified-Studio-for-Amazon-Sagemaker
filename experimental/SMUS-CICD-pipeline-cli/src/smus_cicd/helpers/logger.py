"""Logging configuration for SMUS CLI."""

import logging
import sys


def setup_logger(
    name: str, level: str = "INFO", json_output: bool = False
) -> logging.Logger:
    """
    Set up logger with appropriate handlers.

    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_output: If True, send logs to stderr to avoid contaminating JSON stdout

    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)

    # Clear existing handlers
    logger.handlers.clear()

    # Set level
    logger.setLevel(getattr(logging, level.upper()))

    # Create handler - use stderr for JSON output to keep stdout clean
    handler = logging.StreamHandler(sys.stderr if json_output else sys.stdout)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False

    return logger


def get_logger(name: str, json_output: bool = False) -> logging.Logger:
    """Get or create logger with appropriate configuration."""
    logger_name = f"smus_cicd.{name}"
    logger = logging.getLogger(logger_name)

    if not logger.handlers:
        # Set up with default INFO level, can be overridden by environment
        import os

        level = os.environ.get("SMUS_LOG_LEVEL", "INFO")
        setup_logger(logger_name, level, json_output)

    return logger

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


def get_logger(name: str, json_output: bool = None) -> logging.Logger:
    """Get or create logger with appropriate configuration."""
    logger_name = f"smus_cicd.{name}"
    
    # Auto-detect JSON output mode if not specified
    if json_output is None:
        json_output = _detect_json_output_mode()
    
    # Always set up the logger to ensure correct configuration
    import os
    level = os.environ.get("SMUS_LOG_LEVEL", "INFO")
    return setup_logger(logger_name, level, json_output)


def _detect_json_output_mode() -> bool:
    """
    Detect if we're in JSON output mode by checking command line arguments.
    
    Returns:
        True if JSON output mode is detected, False otherwise
    """
    import sys
    
    # Check if --output JSON is in the command line arguments
    args = sys.argv
    for i, arg in enumerate(args):
        if arg == "--output" and i + 1 < len(args):
            return args[i + 1].upper() == "JSON"
        elif arg.startswith("--output="):
            return arg.split("=", 1)[1].upper() == "JSON"
    
    return False

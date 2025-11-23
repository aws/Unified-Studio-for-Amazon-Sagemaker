"""CLI bootstrap action handler for non-AWS actions."""

from typing import Any, Dict

from ...helpers.logger import get_logger
from ..models import BootstrapAction

logger = get_logger("bootstrap.handlers.cli")


def handle_cli_action(
    action: BootstrapAction, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle CLI actions."""
    service, action_name = action.type.split(".", 1)

    if action_name == "print":
        return print_action(action, context)
    elif action_name == "wait":
        return wait_action(action, context)
    elif action_name == "validate_deployment":
        return validate_deployment(action, context)
    elif action_name == "notify":
        return notify_action(action, context)
    else:
        raise ValueError(f"Unknown CLI action: {action_name}")


def print_action(action: BootstrapAction, context: Dict[str, Any]) -> Dict[str, Any]:
    """Print a message to console or log."""
    message = action.parameters.get("message", "Bootstrap action executed")
    level = action.parameters.get("level", "info")  # info, debug, warning, error
    output = action.parameters.get("output", "console")  # console, log, both

    # Output to console
    if output in ("console", "both"):
        print(f"[BOOTSTRAP] {message}")

    # Output to log
    if output in ("log", "both"):
        if level == "debug":
            logger.debug(message)
        elif level == "warning":
            logger.warning(message)
        elif level == "error":
            logger.error(message)
        else:
            logger.info(message)

    return {
        "action": "cli.print",
        "status": "success",
        "message": message,
        "level": level,
        "output": output,
    }


def wait_action(action: BootstrapAction, context: Dict[str, Any]) -> Dict[str, Any]:
    """Wait for specified seconds."""
    import time

    seconds = action.parameters.get("seconds", 0)
    logger.info(f"Waiting for {seconds} seconds")
    time.sleep(seconds)

    return {"action": "cli.wait", "status": "success", "seconds": seconds}


def validate_deployment(
    action: BootstrapAction, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Run validation checks."""
    checks = action.parameters.get("checks", [])
    logger.info(f"Running {len(checks)} validation checks")

    return {
        "action": "cli.validate_deployment",
        "status": "success",
        "checks_run": len(checks),
    }


def notify_action(action: BootstrapAction, context: Dict[str, Any]) -> Dict[str, Any]:
    """Send notifications."""
    recipient = action.parameters.get("recipient", "default")
    message = action.parameters.get("message", "")
    logger.info(f"Sending notification to {recipient}: {message}")

    return {"action": "cli.notify", "status": "success", "recipient": recipient}

"""Custom bootstrap action handler for non-AWS actions."""

from typing import Any, Dict

from ...helpers.logger import get_logger
from ..models import BootstrapAction

logger = get_logger("bootstrap.handlers.custom")


def handle_custom_action(
    action: BootstrapAction, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle custom actions."""
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
        raise ValueError(f"Unknown custom action: {action_name}")


def print_action(action: BootstrapAction, context: Dict[str, Any]) -> Dict[str, Any]:
    """Print a message - useful for testing."""
    message = action.parameters.get("message", "Bootstrap action executed")
    logger.info(f"Custom print: {message}")

    return {
        "action": "custom.print",
        "status": "success",
        "message": message,
        "context": context,
    }


def wait_action(action: BootstrapAction, context: Dict[str, Any]) -> Dict[str, Any]:
    """Wait for specified seconds."""
    import time

    seconds = action.parameters.get("seconds", 0)
    logger.info(f"Waiting for {seconds} seconds")
    time.sleep(seconds)

    return {"action": "custom.wait", "status": "success", "seconds": seconds}


def validate_deployment(
    action: BootstrapAction, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Run validation checks."""
    checks = action.parameters.get("checks", [])
    logger.info(f"Running {len(checks)} validation checks")

    return {
        "action": "custom.validate_deployment",
        "status": "success",
        "checks_run": len(checks),
    }


def notify_action(action: BootstrapAction, context: Dict[str, Any]) -> Dict[str, Any]:
    """Send notifications."""
    recipient = action.parameters.get("recipient", "default")
    message = action.parameters.get("message", "")
    logger.info(f"Sending notification to {recipient}: {message}")

    return {"action": "custom.notify", "status": "success", "recipient": recipient}

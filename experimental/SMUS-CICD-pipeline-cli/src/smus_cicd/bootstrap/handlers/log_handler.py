"""Log bootstrap action handler for debugging and diagnostics."""

from typing import Any, Dict

from ...helpers.logger import get_logger
from ..models import BootstrapAction

logger = get_logger("bootstrap.handlers.log")


def handle_log_action(
    action: BootstrapAction, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle log actions."""
    service, action_name = action.type.split(".", 1)

    if action_name == "debug":
        return debug_action(action, context)
    else:
        raise ValueError(f"Unknown log action: {action_name}")


def debug_action(action: BootstrapAction, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Debug action that logs a message with variable resolution.

    Useful for testing variable substitution without side effects.

    Parameters:
        message: String with variables to resolve and log

    Example:
        - type: log.debug
          message: "Project: {proj.name}, Bucket: {proj.connection.default.s3_shared.s3Uri}"
    """
    from ...helpers.context_resolver import ContextResolver

    message = action.parameters.get("message", "")

    if not message:
        logger.warning("log.debug called with empty message")
        return {"action": "log.debug", "status": "success", "message": ""}

    # Get context for resolution
    project_name = context.get("project_name")
    domain_id = context.get("domain_id")
    domain_name = context.get("domain_name")
    region = context.get("region")
    stage_name = context.get("stage_name")
    env_vars = context.get("env_vars", {})

    logger.debug(f"Original message: {message}")

    # Resolve variables
    resolver = ContextResolver(
        project_name=project_name,
        domain_id=domain_id,
        region=region,
        domain_name=domain_name,
        stage_name=stage_name,
        env_vars=env_vars,
    )

    try:
        resolved_message = resolver.resolve(message)
        logger.debug(f"Resolved message: {resolved_message}")

        return {
            "action": "log.debug",
            "status": "success",
            "original": message,
            "resolved": resolved_message,
        }
    except Exception as e:
        logger.error(f"Failed to resolve variables: {e}")
        return {
            "action": "log.debug",
            "status": "error",
            "original": message,
            "error": str(e),
        }

"""Bootstrap action executor."""

from typing import Any, Dict, List

from ..helpers.logger import get_logger
from .action_registry import ActionRegistry
from .models import BootstrapAction

logger = get_logger("bootstrap.executor")


class BootstrapExecutor:
    """Execute bootstrap actions in sequence."""

    def __init__(self, registry: ActionRegistry):
        self.registry = registry

    def execute_actions(
        self, actions: List[BootstrapAction], context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute all bootstrap actions sequentially."""
        results = []

        for action in actions:
            logger.info(f"Executing bootstrap action: {action.type}")

            try:
                result = self.registry.execute(action, context)
                results.append(
                    {"action": action.type, "status": "success", "result": result}
                )
                logger.info(f"Successfully executed: {action.type}")
            except Exception as e:
                logger.error(f"Failed to execute {action.type}: {e}")
                results.append(
                    {"action": action.type, "status": "failed", "error": str(e)}
                )
                # Stop on first failure
                raise

        return results

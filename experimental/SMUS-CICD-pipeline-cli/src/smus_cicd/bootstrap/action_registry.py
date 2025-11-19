"""Action registry for bootstrap handlers."""

from typing import Any, Callable, Dict

from .models import BootstrapAction


class ActionRegistry:
    """Registry for bootstrap action handlers."""

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}

    def register(self, service: str, handler: Callable):
        """Register a handler for a service."""
        self._handlers[service] = handler

    def get_handler(self, action_type: str) -> Callable:
        """Get handler for action type."""
        # Check for exact match first (e.g., "workflow.create")
        if action_type in self._handlers:
            return self._handlers[action_type]

        # Fall back to service-level handler (e.g., "workflow")
        service = action_type.split(".", 1)[0]

        if service not in self._handlers:
            raise ValueError(f"No handler registered for service: {service}")

        return self._handlers[service]

    def execute(
        self, action: BootstrapAction, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an action."""
        handler = self.get_handler(action.type)
        return handler(action, context)


# Global registry instance
registry = ActionRegistry()

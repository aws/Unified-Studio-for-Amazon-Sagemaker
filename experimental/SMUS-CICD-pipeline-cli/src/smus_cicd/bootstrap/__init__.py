"""Bootstrap module for handling deployment bootstrap actions."""

from .action_registry import registry
from .executor import BootstrapExecutor
from .handlers.custom_handler import handle_cli_action
from .handlers.datazone_handler import handle_datazone_action
from .handlers.mwaaserverless_handler import handle_mwaaserverless_action
from .handlers.quicksight_handler import handle_quicksight_action
from .handlers.workflow_create_handler import handle_workflow_create
from .handlers.workflow_handler import handle_workflow_action
from .models import BootstrapAction, BootstrapConfig

# Register handlers
registry.register("project", handle_datazone_action)
registry.register("datazone", handle_datazone_action)  # Backward compatibility
registry.register("workflow", handle_workflow_action)
registry.register("workflow.create", handle_workflow_create)
registry.register("mwaaserverless", handle_workflow_action)  # Backward compatibility
registry.register("cli", handle_cli_action)
registry.register("custom", handle_cli_action)  # Backward compatibility
registry.register("quicksight", handle_quicksight_action)

# Create global executor
executor = BootstrapExecutor(registry)

__all__ = [
    "BootstrapAction",
    "BootstrapConfig",
    "registry",
    "executor",
]

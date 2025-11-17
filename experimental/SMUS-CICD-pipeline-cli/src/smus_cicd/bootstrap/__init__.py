"""Bootstrap module for handling deployment bootstrap actions."""

from .action_registry import registry
from .executor import BootstrapExecutor
from .handlers.custom_handler import handle_custom_action
from .handlers.datazone_handler import handle_datazone_action
from .handlers.mwaaserverless_handler import handle_mwaaserverless_action
from .models import BootstrapAction, BootstrapConfig

# Register handlers
registry.register("datazone", handle_datazone_action)
registry.register("mwaaserverless", handle_mwaaserverless_action)
registry.register("custom", handle_custom_action)

# Create global executor
executor = BootstrapExecutor(registry)

__all__ = [
    "BootstrapAction",
    "BootstrapConfig",
    "registry",
    "executor",
]

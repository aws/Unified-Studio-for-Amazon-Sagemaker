"""Bootstrap action models."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class BootstrapAction:
    """Single bootstrap action."""

    type: str  # Format: service.action (e.g., datazone.create_environment)

    # Generic fields for all actions
    parameters: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate action type format."""
        if "." not in self.type:
            raise ValueError(
                f"Action type must be in format 'service.action', got: {self.type}"
            )


@dataclass
class BootstrapConfig:
    """Bootstrap configuration."""

    actions: List[BootstrapAction] = field(default_factory=list)

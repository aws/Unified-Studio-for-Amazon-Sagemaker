"""Base EventBridge emitter for event emission."""

import json
from typing import Any, Dict, List, Optional

import boto3

from .logger import get_logger

logger = get_logger("eventbridge_emitter")


class EventBridgeEmitter:
    """Base class for emitting events to EventBridge."""

    def __init__(
        self,
        enabled: bool = True,
        event_bus_name: str = "default",
        region: Optional[str] = None,
    ):
        """
        Initialize EventBridge client.

        Args:
            enabled: Whether event emission is enabled
            event_bus_name: EventBridge event bus name or ARN
            region: AWS region for EventBridge client
        """
        self.enabled = enabled
        self.event_bus_name = event_bus_name
        self.region = region
        self._client = None

    @property
    def client(self):
        """Lazy-load EventBridge client."""
        if self._client is None and self.enabled:
            self._client = boto3.client("events", region_name=self.region)
        return self._client

    def emit_event(
        self,
        source: str,
        detail_type: str,
        detail: Dict[str, Any],
        resources: Optional[List[str]] = None,
    ) -> bool:
        """
        Emit event to EventBridge.

        Args:
            source: Event source identifier
            detail_type: Event detail type
            detail: Event detail payload
            resources: Optional list of resource ARNs

        Returns:
            True if event emitted successfully, False otherwise
        """
        if not self.enabled:
            return True

        try:
            entry = {
                "Source": source,
                "DetailType": detail_type,
                "Detail": json.dumps(detail),
                "EventBusName": self.event_bus_name,
            }

            if resources:
                entry["Resources"] = resources

            response = self.client.put_events(Entries=[entry])

            if response.get("FailedEntryCount", 0) > 0:
                logger.error(f"Failed to emit event: {response.get('Entries', [])}")
                return False

            logger.info(f"✓ Emitted event: {detail_type}")
            return True

        except Exception as e:
            logger.error(f"Error emitting event {detail_type}: {e}")
            return False

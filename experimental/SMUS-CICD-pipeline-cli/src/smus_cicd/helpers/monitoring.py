"""Monitoring helpers for deployment events."""

from typing import Any, Dict, Optional

from ..application import ApplicationManifest
from .event_emitter import EventEmitter
from .metadata_collector import MetadataCollector


def create_event_emitter(
    manifest: ApplicationManifest,
    region: str,
    emit_events: Optional[bool] = None,
    event_bus_name: Optional[str] = None,
) -> EventEmitter:
    """
    Create EventEmitter from manifest configuration and CLI overrides.

    Args:
        manifest: Pipeline manifest with monitoring config
        region: AWS region for EventBridge
        emit_events: CLI override for enabled flag
        event_bus_name: CLI override for event bus name

    Returns:
        Configured EventEmitter instance
    """
    # Default values
    enabled = True
    bus_name = "default"

    # Apply manifest configuration
    if manifest.monitoring and manifest.monitoring.eventbridge:
        eb_config = manifest.monitoring.eventbridge
        enabled = eb_config.enabled
        bus_name = eb_config.eventBusName

    # Apply CLI overrides
    if emit_events is not None:
        enabled = emit_events
    if event_bus_name is not None:
        bus_name = event_bus_name

    return EventEmitter(enabled=enabled, event_bus_name=bus_name, region=region)


def build_target_info(stage_name: str, target_config) -> Dict[str, Any]:
    """
    Build target information dictionary for events.

    Args:
        stage_name: Name of the target
        target_config: Target configuration object

    Returns:
        Dictionary with target information
    """
    return {
        "name": stage_name,
        "stage": target_config.stage,
        "domain": {
            "name": target_config.domain.name,
            "region": target_config.domain.region,
        },
        "project": {
            "name": target_config.project.name,
        },
    }


def build_bundle_info(bundle_path: str) -> Dict[str, Any]:
    """
    Build bundle information dictionary for events.

    Args:
        bundle_path: Path to bundle file

    Returns:
        Dictionary with bundle information
    """
    import os

    bundle_info = {
        "path": bundle_path,
    }

    if os.path.exists(bundle_path):
        bundle_info["size"] = os.path.getsize(bundle_path)

    return bundle_info


def collect_metadata(manifest: ApplicationManifest) -> Optional[Dict[str, Any]]:
    """
    Collect metadata if enabled in manifest.

    Args:
        manifest: Pipeline manifest with monitoring config

    Returns:
        Metadata dictionary or None if disabled
    """
    if (
        manifest.monitoring
        and manifest.monitoring.eventbridge
        and manifest.monitoring.eventbridge.includeMetadata
    ):
        return MetadataCollector.collect()
    return None

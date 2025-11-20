"""DataZone bootstrap action handler."""

from typing import Any, Dict

import boto3
import typer

from ...helpers import datazone
from ...helpers.connection_creator import ConnectionCreator
from ...helpers.logger import get_logger
from ..models import BootstrapAction

logger = get_logger("bootstrap.handlers.datazone")


def handle_datazone_action(
    action: BootstrapAction, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle DataZone actions."""
    service, api = action.type.split(".", 1)

    if api == "create_environment":
        return create_environment(action, context)
    elif api == "create_connection":
        return create_connection(action, context)
    elif api == "create_domain":
        return create_domain(action, context)
    else:
        raise ValueError(f"Unknown DataZone action: {api}")


def create_environment(
    action: BootstrapAction, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Create DataZone environment."""
    logger.info("Creating DataZone environment")

    # TODO: Implement environment creation
    # This will use existing logic from initialization_handler.py

    return {"action": "datazone.create_environment", "status": "not_implemented"}


def create_connection(
    action: BootstrapAction, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Create or update DataZone connection (idempotent)."""
    logger.info("Creating DataZone connection")

    # Extract context
    target_config = context.get("target_config")
    config = context.get("config")
    metadata = context.get("metadata", {})

    # Get connection parameters
    params = action.parameters
    name = params.get("name")
    connection_type = params.get("connection_type")
    properties = params.get("properties", {})

    if not name or not connection_type:
        raise ValueError("Connection name and type are required")

    # Get project info from metadata
    project_info = metadata.get("project_info", {})
    project_id = project_info.get("project_id")
    domain_id = project_info.get("domain_id")
    region = config.get("region")

    if not project_id or not domain_id:
        raise ValueError("Project info not available for connection creation")

    # Get project environments
    environments = datazone.get_project_environments(project_id, domain_id, region)
    if not environments:
        raise ValueError(f"No environments found for project {project_id}")

    environment_id = environments[0].get("id")
    datazone_client = boto3.client("datazone", region_name=region)

    # Check if connection already exists
    existing_connection = None
    try:
        response = datazone_client.list_connections(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )
        for conn in response.get("items", []):
            if conn["name"] == name:
                existing_connection = conn
                break
    except Exception as e:
        logger.warning(f"Failed to check existing connections: {e}")

    # Build desired properties
    creator = ConnectionCreator(domain_id=domain_id, region=region)
    desired_props = creator._build_connection_props(connection_type, **properties)

    if existing_connection:
        connection_id = existing_connection["connectionId"]
        typer.echo(f"🔍 Connection '{name}' exists: {connection_id}")

        # Get full connection details
        try:
            detail = datazone_client.get_connection(
                domainIdentifier=domain_id, identifier=connection_id
            )
            current_props = detail.get("props", {})

            # Compare properties
            if current_props == desired_props:
                typer.echo(f"✓ Connection '{name}' unchanged")
                return {
                    "action": "datazone.create_connection",
                    "status": "unchanged",
                    "connection_id": connection_id,
                }

            # Update connection with new properties
            typer.echo(f"🔄 Updating connection '{name}'")
            datazone_client.update_connection(
                domainIdentifier=domain_id,
                identifier=connection_id,
                props=desired_props,
            )
            typer.echo(f"✅ Connection '{name}' updated: {connection_id}")
            return {
                "action": "datazone.create_connection",
                "status": "updated",
                "connection_id": connection_id,
            }

        except Exception as e:
            typer.echo(f"❌ Failed to update connection '{name}': {e}")
            raise

    # Create new connection (either new or MLflow recreate)
    if not existing_connection:
        typer.echo(
            f"🔗 Creating {connection_type} connection '{name}' in environment {environment_id}"
        )

        try:
            connection_id = creator.create_connection(
                environment_id=environment_id,
                name=name,
                connection_type=connection_type,
                **properties,
            )

            typer.echo(f"✅ Connection '{name}' created: {connection_id}")
            return {
                "action": "datazone.create_connection",
                "status": "created",
                "connection_id": connection_id,
            }

        except Exception as e:
            typer.echo(f"❌ Failed to create connection '{name}': {e}")
            raise


def create_domain(action: BootstrapAction, context: Dict[str, Any]) -> Dict[str, Any]:
    """Create DataZone domain."""
    logger.info("Creating DataZone domain")

    # TODO: Implement domain creation

    return {"action": "datazone.create_domain", "status": "not_implemented"}

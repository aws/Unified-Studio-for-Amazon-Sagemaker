"""Workflow utility functions."""

from typing import Any, Dict, Optional

import boto3


def get_connection_type(
    connection_name: str, domain_id: str, project_id: str, region: str
) -> Optional[str]:
    """
    Get connection type from DataZone.

    Args:
        connection_name: Name of the connection
        domain_id: DataZone domain ID
        project_id: DataZone project ID
        region: AWS region

    Returns:
        Connection type (e.g., 'WORKFLOWS_SERVERLESS', 'WORKFLOWS_MWAA') or None
    """
    try:
        client = boto3.client("datazone", region_name=region)
        response = client.list_connections(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )

        for conn in response.get("items", []):
            if conn["name"] == connection_name:
                return conn["type"]

        return None
    except Exception:
        return None


def workflow_uses_serverless(
    workflow: Dict[str, Any], domain_id: str, project_id: str, region: str
) -> bool:
    """
    Check if a workflow uses serverless Airflow by looking up connection type.

    Args:
        workflow: Workflow configuration dict
        domain_id: DataZone domain ID
        project_id: DataZone project ID
        region: AWS region

    Returns:
        True if workflow uses WORKFLOWS_SERVERLESS connection
    """
    conn_name = workflow.get("connectionName", "")
    if not conn_name:
        return False

    conn_type = get_connection_type(conn_name, domain_id, project_id, region)
    return conn_type == "WORKFLOWS_SERVERLESS"

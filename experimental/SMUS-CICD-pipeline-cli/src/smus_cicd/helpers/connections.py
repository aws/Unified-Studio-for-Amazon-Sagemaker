"""Connection extraction and handling module."""

import boto3
from typing import Dict, Any, Optional


def extract_connection_properties(connection_detail: Dict[str, Any]) -> Dict[str, Any]:
    """Extract type-specific properties from a DataZone connection."""
    connection_type = connection_detail.get("type", "")
    props = connection_detail.get("props", {})

    conn_info = {
        "connectionId": connection_detail.get("connectionId", ""),
        "type": connection_type,
        "description": connection_detail.get("description"),
        # Preserve physicalEndpoints for boto3 client creation
        "physicalEndpoints": connection_detail.get("physicalEndpoints", []),
    }

    # Extract AWS location info from physicalEndpoints for display
    physical_endpoints = connection_detail.get("physicalEndpoints", [])
    if physical_endpoints and len(physical_endpoints) > 0:
        aws_location = physical_endpoints[0].get("awsLocation", {})
        if aws_location:
            conn_info["region"] = aws_location.get("awsRegion")
            conn_info["awsAccountId"] = aws_location.get("awsAccountId")

    # Extract type-specific properties
    if connection_type == "S3":
        s3_props = props.get("s3Properties", {})
        conn_info["s3Uri"] = s3_props.get("s3Uri", "")
        conn_info["status"] = s3_props.get("status")

    elif connection_type == "ATHENA":
        athena_props = props.get("athenaProperties", {})
        conn_info["workgroupName"] = athena_props.get("workgroupName")

    elif connection_type == "SPARK":
        spark_props = props.get("sparkGlueProperties", {})
        conn_info["glueVersion"] = spark_props.get("glueVersion")
        conn_info["workerType"] = spark_props.get("workerType")
        conn_info["numberOfWorkers"] = spark_props.get("numberOfWorkers")

    elif connection_type in ["MWAA", "WORKFLOWS_MWAA"]:
        mwaa_props = props.get("mwaaProperties", {})
        env_name = mwaa_props.get("environmentName")

        # If no environment name in properties, infer it from project structure
        if (
            not env_name
            and connection_detail.get("domain_id")
            and connection_detail.get("project_id")
        ):
            env_name = f"DataZoneMWAAEnv-{connection_detail['domain_id']}-{connection_detail['project_id']}-dev"

        conn_info["environmentName"] = env_name

    elif connection_type == "IAM":
        iam_props = props.get("iamProperties", {})
        conn_info["glueLineageSyncEnabled"] = iam_props.get("glueLineageSyncEnabled")

    elif connection_type == "LAKEHOUSE":
        # LAKEHOUSE connections typically don't have additional properties
        pass

    return conn_info


def get_project_connections(
    project_name: str, domain_name: str, region: str
) -> Dict[str, Dict[str, Any]]:
    """Get all connections for a DataZone project with extracted properties."""
    from . import datazone

    # Get domain and project IDs
    domain_id = datazone.get_domain_id_by_name(domain_name, region)
    if not domain_id:
        return {}

    project_id = datazone.get_project_id_by_name(project_name, domain_id, region)
    if not project_id:
        return {}

    # Get connections from DataZone
    datazone_client = boto3.client("datazone", region_name=region)

    try:
        response = datazone_client.list_connections(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )

        connections = {}
        for conn in response.get("items", []):
            conn_name = conn.get("name", "unknown")

            # Get detailed connection info
            try:
                detail_response = datazone_client.get_connection(
                    domainIdentifier=domain_id, identifier=conn.get("connectionId", "")
                )

                connection_detail = detail_response.copy()
                # Add context for environment name inference
                connection_detail["domain_id"] = domain_id
                connection_detail["project_id"] = project_id

                # Extract properties using centralized logic
                conn_info = extract_connection_properties(connection_detail)
                connections[conn_name] = conn_info

            except Exception as e:
                # If we can't get details, use basic info
                connections[conn_name] = {
                    "connectionId": conn.get("connectionId", ""),
                    "type": conn.get("type", ""),
                    "description": conn.get("description"),
                    "error": f"Could not get connection details: {str(e)}",
                }

        return connections

    except Exception as e:
        return {"error": f"Could not list connections: {str(e)}"}

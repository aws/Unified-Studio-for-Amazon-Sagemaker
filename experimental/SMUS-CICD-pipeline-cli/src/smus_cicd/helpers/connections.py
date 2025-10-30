"""Connection extraction and handling module."""

from typing import Any, Dict

import boto3


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
        spark_props = props.get("sparkGlueProperties", {}) or props.get(
            "sparkEmrProperties", {}
        )
        conn_info["glueVersion"] = spark_props.get("glueVersion")
        conn_info["workerType"] = spark_props.get("workerType")
        conn_info["numberOfWorkers"] = spark_props.get("numberOfWorkers")
        conn_info["computeArn"] = spark_props.get("computeArn")
        conn_info["runtimeRole"] = spark_props.get("runtimeRole")

    elif connection_type == "REDSHIFT":
        redshift_props = props.get("redshiftProperties", {})
        conn_info["host"] = redshift_props.get("host")
        conn_info["port"] = redshift_props.get("port")
        conn_info["databaseName"] = redshift_props.get("databaseName")
        storage = redshift_props.get("storage", {})
        conn_info["clusterName"] = storage.get("clusterName")
        conn_info["workgroupName"] = storage.get("workgroupName")

    elif connection_type in ["MWAA", "WORKFLOWS_MWAA"]:
        mwaa_props = props.get("workflowsMwaaProperties", {}) or props.get(
            "mwaaProperties", {}
        )
        env_name = mwaa_props.get("mwaaEnvironmentName") or mwaa_props.get(
            "environmentName"
        )

        # If no environment name in properties, infer it from project structure
        if (
            not env_name
            and connection_detail.get("domain_id")
            and connection_detail.get("project_id")
        ):
            env_name = f"DataZoneMWAAEnv-{connection_detail['domain_id']}-{connection_detail['project_id']}-dev"

        conn_info["mwaaEnvironmentName"] = env_name

    elif connection_type == "MLFLOW":
        mlflow_props = props.get("mlflowProperties", {})
        conn_info["trackingServerName"] = mlflow_props.get("trackingServerName")
        conn_info["trackingServerArn"] = mlflow_props.get("trackingServerArn")

    elif connection_type == "WORKFLOWS_SERVERLESS":
        # Empty properties structure - no additional info to extract
        pass

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

    # DEBUG: Log the exact parameters being used for the ListConnections call
    import sys

    is_json_output = "--output" in sys.argv and "JSON" in sys.argv
    if not is_json_output:
        print(
            f"🔍 DEBUG ListConnections: region={region}, domain_id={domain_id}, project_id={project_id}",
            file=sys.stderr,
        )

    try:
        # Get project-level connections
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

        # Also get environment-level connections for the project's environments
        try:
            # Get environments for this project
            env_response = datazone_client.list_environments(
                domainIdentifier=domain_id, projectIdentifier=project_id
            )

            for env in env_response.get("items", []):
                env_id = env.get("id")
                if env_id:
                    try:
                        # Get connections for this environment
                        env_conn_response = datazone_client.list_connections(
                            domainIdentifier=domain_id,
                            projectIdentifier=project_id,
                            environmentIdentifier=env_id,
                        )

                        for conn in env_conn_response.get("items", []):
                            conn_name = conn.get("name", "unknown")

                            # Skip if we already have this connection from project level
                            if conn_name in connections:
                                continue

                            # Get detailed connection info
                            try:
                                detail_response = datazone_client.get_connection(
                                    domainIdentifier=domain_id,
                                    identifier=conn.get("connectionId", ""),
                                )

                                connection_detail = detail_response.copy()
                                # Add context for environment name inference
                                connection_detail["domain_id"] = domain_id
                                connection_detail["project_id"] = project_id

                                # Extract properties using centralized logic
                                conn_info = extract_connection_properties(
                                    connection_detail
                                )
                                connections[conn_name] = conn_info

                            except Exception as e:
                                # If we can't get details, use basic info
                                connections[conn_name] = {
                                    "connectionId": conn.get("connectionId", ""),
                                    "type": conn.get("type", ""),
                                    "description": conn.get("description"),
                                    "error": f"Could not get environment connection details: {str(e)}",
                                }

                    except Exception as e:
                        if not is_json_output:
                            print(
                                f"🔍 DEBUG: Failed to list connections for environment {env_id}: {e}",
                                file=sys.stderr,
                            )
                        continue

        except Exception as e:
            if not is_json_output:
                print(
                    f"🔍 DEBUG: Failed to list environments for project: {e}",
                    file=sys.stderr,
                )

        return connections

    except Exception as e:
        # Check if this is a permission error
        error_str = str(e)
        if any(
            perm_error in error_str.lower()
            for perm_error in [
                "accessdenied",
                "access denied",
                "unauthorized",
                "forbidden",
                "permission",
                "not authorized",
                "insufficient privileges",
            ]
        ):
            raise Exception(
                f"AWS Permission Error: {error_str}. Check if the role has DataZone permissions to list connections."
            )

        # For other errors, return error info but don't fail completely
        return {"error": f"Could not list connections: {str(e)}"}

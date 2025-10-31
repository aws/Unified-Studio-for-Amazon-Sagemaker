"""AWS Airflow Serverless helper functions."""

import os
import time
from typing import Any, Dict, List

import boto3

from . import boto3_client
from .logger import get_logger

# Airflow Serverless (Overdrive) configuration - configurable via environment variables
AIRFLOW_SERVERLESS_ENDPOINT = os.environ.get("AIRFLOW_SERVERLESS_ENDPOINT")
AIRFLOW_SERVERLESS_SERVICE = "awsoverdriveservice"


def create_airflow_serverless_client(
    connection_info: Dict[str, Any] = None, region: str = None
):
    """Create Airflow Serverless client with proper endpoint configuration."""
    # Use AIRFLOW_SERVERLESS_ENDPOINT if set, otherwise use domain region without endpoint
    if AIRFLOW_SERVERLESS_ENDPOINT:
        endpoint_url = AIRFLOW_SERVERLESS_ENDPOINT
        # Extract region from endpoint if not provided
        if not region:
            if "us-east-1" in endpoint_url:
                client_region = "us-east-1"
            elif "us-west-2" in endpoint_url:
                client_region = "us-west-2"
            else:
                client_region = "us-east-1"
        else:
            client_region = region

        print(
            f"🔍 DEBUG: Creating Airflow Serverless client with region={client_region}, endpoint={endpoint_url}"
        )
        session = boto3.Session()
        client = session.client(
            AIRFLOW_SERVERLESS_SERVICE,
            region_name=client_region,
            endpoint_url=endpoint_url,
        )
    else:
        # Use domain region without custom endpoint
        client_region = region
        print(
            f"🔍 DEBUG: Creating Airflow Serverless client with region={client_region}, endpoint=default"
        )
        session = boto3.Session()
        client = session.client(AIRFLOW_SERVERLESS_SERVICE, region_name=client_region)

    return client


def create_workflow(
    workflow_name: str,
    dag_s3_location: Dict[str, str],
    role_arn: str,
    description: str = None,
    tags: Dict[str, str] = None,
    datazone_domain_id: str = None,
    datazone_domain_region: str = None,
    datazone_project_id: str = None,
    connection_info: Dict[str, Any] = None,
    region: str = None,
    security_group_ids: List[str] = None,
    subnet_ids: List[str] = None,
) -> Dict[str, Any]:
    """Create a new serverless Airflow workflow."""
    logger = get_logger("airflow_serverless")

    try:
        client = create_airflow_serverless_client(connection_info, region)

        params = {
            "Name": workflow_name,
            "DefinitionS3Location": dag_s3_location,
            "RoleArn": role_arn,
            "OverdriveVersion": 1,
        }

        # Add DataZone environment variables if provided
        if datazone_domain_id and datazone_project_id:
            from . import datazone

            env_vars = {}
            env_vars["DataZoneDomainRegion"] = datazone_domain_region or region
            env_vars["DataZoneDomainId"] = datazone_domain_id
            env_vars["DataZoneProjectId"] = datazone_project_id

            # Get environment_id from IAM connection
            try:
                project_connections = datazone.get_project_connections(
                    project_id=datazone_project_id,
                    domain_id=datazone_domain_id,
                    region=datazone_domain_region or region,
                )

                # Find IAM connection and extract environment_id
                for conn_name, conn_info in project_connections.items():
                    if conn_info.get("type") == "IAM":
                        env_id = conn_info.get("environmentId")
                        if env_id:
                            env_vars["DataZoneEnvironmentId"] = env_id
                            logger.info(
                                f"Found DataZone environment ID from IAM connection: {env_id}"
                            )
                            break
            except Exception as e:
                logger.warning(
                    f"Could not get DataZone environment ID from connections: {e}"
                )

            # Add DataZone stage and endpoint - COMMENTED OUT FOR TESTING
            # env_vars["DataZoneStage"] = "prod"
            # env_vars["DataZoneEndpoint"] = (
            #     f"https://datazone.{datazone_domain_region or region}.amazonaws.com"
            # )

            params["EnvironmentVariables"] = env_vars
            logger.info(f"🔍 DEBUG: DataZone environment variables: {env_vars}")

        # Network configuration - commented out for now
        # if security_group_ids and subnet_ids:
        #     params["NetworkConfiguration"] = {
        #         "SecurityGroupIds": security_group_ids,
        #         "SubnetIds": subnet_ids
        #     }
        #     logger.info(f"🔍 DEBUG: Network configuration: SecurityGroups={security_group_ids}, Subnets={subnet_ids}")

        if description:
            params["Description"] = description
        if tags:
            params["Tags"] = tags

        import typer

        typer.echo(f"🔍 DEBUG: Client region: {region}")
        typer.echo(
            f"🔍 DEBUG: Client endpoint: {AIRFLOW_SERVERLESS_ENDPOINT or 'default'}"
        )
        typer.echo(f"🔍 DEBUG: Create workflow request params: {params}")

        logger.info(f"Creating serverless Airflow workflow: {workflow_name}")
        response = client.create_workflow(**params)

        typer.echo(f"🔍 DEBUG: Create workflow response: {response}")

        workflow_arn = response["WorkflowArn"]
        logger.info(f"Successfully created workflow: {workflow_arn}")

        return {
            "workflow_arn": workflow_arn,
            "workflow_version": response["WorkflowVersion"],
            "created_at": response["CreatedAt"],
            "revision_id": response["RevisionId"],
            "success": True,
        }

    except Exception as e:
        logger.error(f"🔍 DEBUG: Exception in create_workflow: {type(e).__name__}: {e}")
        logger.error(f"🔍 DEBUG: Full exception details: {str(e)}")
        # Handle ConflictException when workflow already exists (idempotent behavior)
        if "ConflictException" in str(e) and "already exists" in str(e):
            logger.info(
                f"Workflow {workflow_name} already exists, returning existing workflow info"
            )

            # Get existing workflow info and return it
            try:
                client = create_airflow_serverless_client(connection_info, region)

                # Get existing workflow ARN first
                workflows = list_workflows(connection_info, region)
                logger.info(f"🔍 DEBUG: Found {len(workflows)} workflows in list")
                logger.info(f"🔍 DEBUG: Looking for workflow name: {workflow_name}")
                for wf in workflows:
                    logger.info(f"🔍 DEBUG: Checking workflow: {wf.get('name')}")

                workflow_arn = None
                for wf in workflows:
                    if wf["name"] == workflow_name:
                        workflow_arn = wf["workflow_arn"]
                        logger.info(f"Found existing workflow: {workflow_arn}")
                        return {
                            "workflow_arn": workflow_arn,
                            "workflow_version": wf.get("workflow_version"),
                            "success": True,
                            "already_exists": True,
                        }

                if not workflow_arn:
                    logger.error(
                        f"Could not find existing workflow {workflow_name} in list"
                    )
                    raise Exception(f"Could not find existing workflow {workflow_name}")

                # Delete the existing workflow
                logger.info(f"Deleting existing workflow: {workflow_name}")
                delete_params = {"WorkflowArn": workflow_arn}
                logger.info(
                    f"🔍 DEBUG: Delete workflow request params: {delete_params}"
                )
                client.delete_workflow(**delete_params)
                logger.info(f"Successfully deleted workflow: {workflow_arn}")

                # Wait a moment for the deletion to propagate
                import time

                logger.info("Waiting for workflow deletion to propagate...")
                time.sleep(5)

                # Recreate the workflow with original parameters
                logger.info(f"Recreating serverless Airflow workflow: {workflow_name}")
                logger.info(f"🔍 DEBUG: Recreate workflow request params: {params}")
                response = client.create_workflow(**params)
                logger.info(f"🔍 DEBUG: Recreate workflow response: {response}")

                workflow_arn = response["WorkflowArn"]
                logger.info(f"Successfully recreated workflow: {workflow_arn}")

                return {
                    "workflow_arn": workflow_arn,
                    "workflow_version": response["WorkflowVersion"],
                    "created_at": response["CreatedAt"],
                    "revision_id": response["RevisionId"],
                    "success": True,
                }

            except Exception as delete_recreate_error:
                logger.error(
                    f"Failed to delete and recreate workflow {workflow_name}: {delete_recreate_error}"
                )
                raise Exception(
                    f"Failed to delete and recreate workflow {workflow_name}: {delete_recreate_error}"
                )

        logger.error(f"Failed to create workflow {workflow_name}: {e}")
        raise Exception(f"Failed to create workflow {workflow_name}: {e}")


def get_workflow_status(
    workflow_arn: str, connection_info: Dict[str, Any] = None, region: str = None
) -> Dict[str, Any]:
    """Get serverless Airflow workflow status and details."""
    try:
        client = create_airflow_serverless_client(connection_info, region)
        response = client.get_workflow(WorkflowArn=workflow_arn)

        return {
            "workflow_arn": response["WorkflowArn"],
            "name": response["Name"],
            "status": response["WorkflowStatus"],
            "created_at": response["CreatedAt"],
            "updated_at": response["ModifiedAt"],
            "success": True,
        }

    except Exception as e:
        logger = get_logger("airflow_serverless")
        logger.error(f"Failed to get workflow status for {workflow_arn}: {e}")
        return {"success": False, "error": str(e)}


def list_workflows(
    connection_info: Dict[str, Any] = None, region: str = None, max_results: int = 50
) -> List[Dict[str, Any]]:
    """List all serverless Airflow workflows."""
    logger = get_logger("airflow_serverless")
    try:
        client = create_airflow_serverless_client(connection_info, region)
        response = client.list_workflows(MaxResults=max_results)

        # Debug: Print the raw response
        logger.debug(f"Raw list_workflows response: {response}")

        workflows = []
        for workflow in response.get("Workflows", []):
            workflow_data = {
                "workflow_arn": workflow["WorkflowArn"],
                "workflow_version": workflow.get("WorkflowVersion"),
                "name": workflow["Name"],
                "status": workflow[
                    "WorkflowStatus"
                ],  # Use WorkflowStatus instead of Status
                "created_at": workflow["CreatedAt"],
                "updated_at": workflow[
                    "ModifiedAt"
                ],  # Use ModifiedAt instead of UpdatedAt
                "tags": {},
            }

            # Fetch tags for each workflow
            try:
                tags_response = client.list_tags_for_resource(
                    ResourceArn=workflow["WorkflowArn"]
                )
                workflow_data["tags"] = tags_response.get("Tags", {})
            except Exception as tag_error:
                logger.warning(
                    f"Failed to fetch tags for workflow {workflow['Name']}: {tag_error}"
                )
                workflow_data["tags"] = {}

            workflows.append(workflow_data)

        return workflows

    except Exception as e:
        logger.error(f"Failed to list workflows: {e}")
        return []


def start_workflow_run(
    workflow_arn: str,
    run_name: str = None,
    connection_info: Dict[str, Any] = None,
    region: str = None,
) -> Dict[str, Any]:
    """Start a serverless Airflow workflow run."""
    logger = get_logger("airflow_serverless")

    try:
        client = create_airflow_serverless_client(connection_info, region)

        params = {"WorkflowArn": workflow_arn}
        # Note: RunName is not supported by the API, using ClientToken for uniqueness if needed
        if run_name:
            params["ClientToken"] = run_name

        logger.info(f"Starting workflow run for: {workflow_arn}")
        response = client.start_workflow_run(**params)

        # Debug: Print the raw response
        logger.debug(f"Raw start_workflow_run response: {response}")

        run_id = response["RunId"]
        logger.info(f"Successfully started workflow run: {run_id}")

        return {
            "run_id": run_id,
            "workflow_arn": workflow_arn,
            "status": response.get(
                "Status", "QUEUED"
            ),  # Default status if not provided
            "started_at": response.get("StartedAt"),  # May not be present initially
            "success": True,
        }

    except Exception as e:
        logger.error(f"Failed to start workflow run for {workflow_arn}: {e}")
        raise Exception(f"Failed to start workflow run for {workflow_arn}: {e}")


def get_workflow_run_status(
    workflow_arn: str,
    run_id: str,
    connection_info: Dict[str, Any] = None,
    region: str = None,
) -> Dict[str, Any]:
    """Get serverless Airflow workflow run status."""
    logger = get_logger("airflow_serverless")

    try:
        client = create_airflow_serverless_client(connection_info, region)
        response = client.get_workflow_run(WorkflowArn=workflow_arn, RunId=run_id)

        # Debug: Print the raw response
        logger.debug(f"Raw get_workflow_run response: {response}")

        # Handle different response structures
        run_detail = response.get("RunDetail", {})
        status = run_detail.get("RunState") or response.get("Status", "UNKNOWN")

        return {
            "run_id": response["RunId"],
            "workflow_arn": response.get(
                "WorkflowArn", workflow_arn
            ),  # Use provided if not in response
            "status": status,
            "started_at": run_detail.get("StartedAt"),
            "ended_at": run_detail.get("EndedAt"),
            "success": True,
        }

    except Exception as e:
        logger.error(f"Failed to get workflow run status for {run_id}: {e}")
        raise Exception(f"Failed to get workflow run status for {run_id}: {e}")


def list_workflow_runs(
    workflow_arn: str,
    connection_info: Dict[str, Any] = None,
    region: str = None,
    max_results: int = 10,
) -> List[Dict[str, Any]]:
    """List workflow runs for a serverless Airflow workflow."""
    logger = get_logger("airflow_serverless")

    try:
        client = create_airflow_serverless_client(connection_info, region)
        response = client.list_workflow_runs(
            WorkflowArn=workflow_arn, MaxResults=max_results
        )

        # Debug: Print the raw response
        logger.debug(f"Raw list_workflow_runs response: {response}")

        runs = []
        for run in response.get("WorkflowRuns", []):
            # Handle nested RunDetailSummary structure
            run_detail = run.get("RunDetailSummary", {})
            runs.append(
                {
                    "run_id": run["RunId"],
                    "workflow_arn": run.get("WorkflowArn", workflow_arn),
                    "status": run_detail.get("Status", "UNKNOWN"),
                    "started_at": run_detail.get("StartedAt"),
                    "ended_at": run_detail.get("EndedAt"),
                }
            )

        return runs

    except Exception as e:
        logger.error(f"Failed to list workflow runs for {workflow_arn}: {e}")
        return []


def delete_workflow(
    workflow_arn: str, connection_info: Dict[str, Any] = None, region: str = None
) -> Dict[str, Any]:
    """Delete a serverless Airflow workflow."""
    logger = get_logger("airflow_serverless")

    try:
        client = create_airflow_serverless_client(connection_info, region)

        logger.info(f"Deleting workflow: {workflow_arn}")
        client.delete_workflow(WorkflowArn=workflow_arn)

        logger.info(f"Successfully deleted workflow: {workflow_arn}")
        return {"success": True, "workflow_arn": workflow_arn}

    except Exception as e:
        logger.error(f"Failed to delete workflow {workflow_arn}: {e}")
        raise Exception(f"Failed to delete workflow {workflow_arn}: {e}")


def get_cloudwatch_logs(
    log_group_name: str,
    start_time: int = None,
    end_time: int = None,
    limit: int = 100,
    connection_info: Dict[str, Any] = None,
    region: str = None,
) -> List[Dict[str, Any]]:
    """Get CloudWatch logs for serverless Airflow workflows."""
    try:
        # Use regular CloudWatch client for logs
        logs_client = boto3_client.create_client("logs", connection_info, region)

        params = {"logGroupName": log_group_name, "limit": limit}

        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        response = logs_client.filter_log_events(**params)

        events = []
        for event in response.get("events", []):
            events.append(
                {
                    "timestamp": event["timestamp"],
                    "message": event["message"],
                    "log_stream_name": event["logStreamName"],
                }
            )

        return events

    except Exception as e:
        logger = get_logger("airflow_serverless")
        logger.error(f"Failed to get CloudWatch logs for {log_group_name}: {e}")
        return []


def validate_airflow_serverless_health(
    project_name: str, config: Dict[str, Any]
) -> bool:
    """Validate serverless Airflow service health."""
    try:
        # Simple health check by listing workflows
        list_workflows(region=config.get("region"))
        return True  # If we can list workflows, service is healthy

    except Exception as e:
        logger = get_logger("airflow_serverless")
        logger.error(f"Serverless Airflow health check failed: {e}")
        return False


def wait_for_workflow_completion(
    workflow_arn: str,
    run_id: str,
    timeout_minutes: int = 60,
    connection_info: Dict[str, Any] = None,
    region: str = None,
    status_callback: callable = None,
) -> Dict[str, Any]:
    """Wait for a serverless Airflow workflow run to complete."""
    logger = get_logger("airflow_serverless")

    timeout_seconds = timeout_minutes * 60
    start_time = time.time()
    last_status = None

    while time.time() - start_time < timeout_seconds:
        status_result = get_workflow_run_status(
            workflow_arn, run_id, connection_info, region
        )

        if not status_result["success"]:
            return status_result

        status = status_result["status"]
        elapsed = int(time.time() - start_time)

        # Call status callback if provided
        if status_callback and status != last_status:
            status_callback(status, elapsed, last_status)
        last_status = status

        if status in [
            "SUCCEEDED",
            "FAILED",
            "CANCELLED",
            "SUCCESS",
            "STOPPED",
            "TIMEOUT",
        ]:
            logger.info(f"Workflow run {run_id} completed with status: {status}")
            return status_result

        logger.info(f"Workflow run {run_id} status: {status}, waiting...")
        time.sleep(30)  # Wait 30 seconds before checking again

    logger.warning(
        f"Workflow run {run_id} did not complete within {timeout_minutes} minutes"
    )
    return {
        "success": False,
        "error": f"Timeout after {timeout_minutes} minutes",
        "status": "TIMEOUT",
    }


def upload_dag_to_s3(
    dag_content: str, bucket_name: str, dag_key: str, region: str = None
) -> Dict[str, Any]:
    """Upload DAG content to S3."""
    logger = get_logger("airflow_serverless")

    try:
        s3_client = boto3_client.create_client("s3", region=region)

        s3_client.put_object(
            Bucket=bucket_name, Key=dag_key, Body=dag_content, ContentType="text/yaml"
        )

        logger.info(f"Successfully uploaded DAG to s3://{bucket_name}/{dag_key}")
        return {"success": True, "bucket": bucket_name, "key": dag_key}

    except Exception as e:
        logger.error(f"Failed to upload DAG to S3: {e}")
        return {"success": False, "error": str(e)}


def stop_workflow_run(
    workflow_arn: str,
    run_id: str,
    connection_info: Dict[str, Any] = None,
    region: str = None,
) -> Dict[str, Any]:
    """Stop a serverless Airflow workflow run."""
    logger = get_logger("airflow_serverless")

    try:
        client = create_airflow_serverless_client(connection_info, region)

        logger.info(f"Stopping workflow run: {run_id}")
        client.stop_workflow_run(WorkflowArn=workflow_arn, RunId=run_id)

        logger.info(f"Successfully stopped workflow run: {run_id}")
        return {"success": True, "run_id": run_id}

    except Exception as e:
        logger.error(f"Failed to stop workflow run {run_id}: {e}")
        raise Exception(f"Failed to stop workflow run {run_id}: {e}")


def cleanup_s3_dag(
    bucket_name: str, dag_key: str, region: str = None
) -> Dict[str, Any]:
    """Clean up DAG file from S3."""
    logger = get_logger("airflow_serverless")

    try:
        s3_client = boto3_client.create_client("s3", region=region)
        s3_client.delete_object(Bucket=bucket_name, Key=dag_key)

        logger.info(f"Successfully deleted DAG from s3://{bucket_name}/{dag_key}")
        return {"success": True}

    except Exception as e:
        logger.error(f"Failed to delete DAG from S3: {e}")
        return {"success": False, "error": str(e)}

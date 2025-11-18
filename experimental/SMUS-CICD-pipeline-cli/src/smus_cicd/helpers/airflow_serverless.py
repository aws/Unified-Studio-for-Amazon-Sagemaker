"""AWS Airflow Serverless helper functions."""

import os
import time
from typing import Any, Dict, List

import boto3

from . import boto3_client
from .logger import get_logger

# Airflow Serverless (MWAA Serverless) configuration - configurable via environment variables
AIRFLOW_SERVERLESS_ENDPOINT = os.environ.get("AIRFLOW_SERVERLESS_ENDPOINT")
AIRFLOW_SERVERLESS_SERVICE = "mwaaserverless-internal"


def format_log_event(event: dict) -> str:
    """
    Format a CloudWatch log event for display.

    Args:
        event: Log event dict with timestamp, log_stream_name, and message

    Returns:
        Formatted log line string
    """
    timestamp = time.strftime(
        "%Y-%m-%d %H:%M:%S", time.localtime(event["timestamp"] / 1000)
    )
    stream = event.get("log_stream_name", "unknown")
    message = event["message"]
    return f"[{timestamp}] [{stream}] {message}"


def create_airflow_serverless_client(
    connection_info: Dict[str, Any] = None, region: str = None
):
    """Create Airflow Serverless client with proper endpoint configuration."""
    session = boto3.Session()

    # Determine region
    if not region:
        region = session.region_name or "us-east-1"

    # Use AIRFLOW_SERVERLESS_ENDPOINT if set, otherwise use public endpoint
    if AIRFLOW_SERVERLESS_ENDPOINT:
        endpoint_url = AIRFLOW_SERVERLESS_ENDPOINT
    else:
        endpoint_url = f"https://airflow-serverless.{region}.api.aws/"

    print(
        f"🔍 DEBUG: Creating Airflow Serverless client with region={region}, endpoint={endpoint_url}"
    )

    return session.client(
        AIRFLOW_SERVERLESS_SERVICE,
        region_name=region,
        endpoint_url=endpoint_url,
    )


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

        # Parse S3 location into bucket and key
        s3_bucket = None
        s3_key = None
        if dag_s3_location.startswith("s3://"):
            parts = dag_s3_location[5:].split("/", 1)
            s3_bucket = parts[0]
            s3_key = parts[1] if len(parts) > 1 else ""

        params = {
            "Name": workflow_name,
            "DefinitionS3Location": {
                "Bucket": s3_bucket,
                "ObjectKey": s3_key,
            },
            "RoleArn": role_arn,
        }

        # Network configuration - commented out for now
        # if security_group_ids and subnet_ids:
        #     params["NetworkConfiguration"] = {
        #         "SecurityGroupIds": security_group_ids,
        #         "SubnetIds": subnet_ids
        #     }
        #     logger.debug(f"Network configuration: SecurityGroups={security_group_ids}, Subnets={subnet_ids}")

        if description:
            params["Description"] = description
        if tags:
            params["Tags"] = tags

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

            # Add DataZone endpoint from environment variable if set
            import os

            if os.getenv("AWS_ENDPOINT_URL_DATAZONE"):
                env_vars["DataZoneEndpoint"] = os.getenv("AWS_ENDPOINT_URL_DATAZONE")

            params["EnvironmentVariables"] = env_vars
            logger.debug(f"DataZone environment variables: {env_vars}")

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
        logger.debug(f"Exception in create_workflow: {type(e).__name__}: {e}")
        logger.debug(f"Full exception details: {str(e)}")
        # Handle ConflictException when workflow already exists (idempotent behavior)
        if "ConflictException" in str(e):
            logger.info(f"Workflow {workflow_name} already exists, updating it")

            try:
                client = create_airflow_serverless_client(connection_info, region)

                # Get existing workflow ARN
                workflow_arn = None
                next_token = None
                max_pages = 10
                page_count = 0

                while page_count < max_pages:
                    if next_token:
                        workflows_response = client.list_workflows(
                            MaxResults=50, NextToken=next_token
                        )
                    else:
                        workflows_response = client.list_workflows(MaxResults=50)

                    for wf in workflows_response.get("Workflows", []):
                        if wf["Name"] == workflow_name:
                            workflow_arn = wf["WorkflowArn"]
                            break

                    if workflow_arn:
                        break

                    next_token = workflows_response.get("NextToken")
                    if not next_token:
                        break

                    page_count += 1

                if not workflow_arn:
                    raise Exception(
                        f"Workflow {workflow_name} exists but could not be found in list"
                    )

                logger.info(f"Found existing workflow: {workflow_arn}, updating it")

                update_params = {
                    "WorkflowArn": workflow_arn,
                    "DefinitionS3Location": {
                        "Bucket": s3_bucket,
                        "ObjectKey": s3_key,
                    },
                    "RoleArn": role_arn,
                }

                if description:
                    update_params["Description"] = description

                # Add EnvironmentVariables if provided
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

                    # Add DataZone endpoint from environment variable if set
                    if os.getenv("AWS_ENDPOINT_URL_DATAZONE"):
                        env_vars["DataZoneEndpoint"] = os.getenv(
                            "AWS_ENDPOINT_URL_DATAZONE"
                        )

                    update_params["EnvironmentVariables"] = env_vars
                    logger.info(
                        f"🔍 DEBUG: Updating with environment variables: {env_vars}"
                    )

                logger.info(f"Updating workflow with params: {update_params}")
                update_response = client.update_workflow(**update_params)
                logger.info(f"Successfully updated workflow: {workflow_arn}")

                return {
                    "workflow_arn": workflow_arn,
                    "workflow_version": update_response.get("WorkflowVersion"),
                    "success": True,
                    "already_exists": True,
                    "updated": True,
                }

            except Exception as update_error:
                logger.error(
                    f"Failed to update workflow {workflow_name}: {update_error}"
                )
                raise
        else:
            # Not a ConflictException, raise the original error
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
    """List all serverless Airflow workflows with pagination."""
    logger = get_logger("airflow_serverless")
    try:
        client = create_airflow_serverless_client(connection_info, region)
        workflows = []
        next_token = None

        # Paginate through all workflows
        while True:
            if next_token:
                response = client.list_workflows(
                    MaxResults=max_results, NextToken=next_token
                )
            else:
                response = client.list_workflows(MaxResults=max_results)

            # Debug: Print the raw response
            logger.debug(f"Raw list_workflows response: {response}")

            for workflow in response.get("Workflows", []):
                workflow_data = {
                    "workflow_arn": workflow["WorkflowArn"],
                    "workflow_version": workflow.get("WorkflowVersion"),
                    "name": workflow["Name"],
                    "status": workflow["WorkflowStatus"],
                    "created_at": workflow["CreatedAt"],
                    "updated_at": workflow["ModifiedAt"],
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

            # Check if there are more pages
            next_token = response.get("NextToken")
            if not next_token:
                break

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

        created_at = run_detail.get("CreatedAt")
        started_on = run_detail.get("StartedOn")
        completed_on = run_detail.get("CompletedOn")

        # Calculate queue time if both timestamps available
        queue_time_seconds = None
        if created_at and started_on:
            queue_time_seconds = (started_on - created_at).total_seconds()

        return {
            "run_id": response["RunId"],
            "workflow_arn": response.get(
                "WorkflowArn", workflow_arn
            ),  # Use provided if not in response
            "status": status,
            "created_at": created_at,
            "started_at": started_on,
            "ended_at": completed_on,
            "queue_time_seconds": queue_time_seconds,
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
            
            created_at = run_detail.get("CreatedAt")
            started_on = run_detail.get("StartedOn")
            completed_on = run_detail.get("CompletedOn")
            
            # Calculate queue time if both timestamps available
            queue_time_seconds = None
            if created_at and started_on:
                queue_time_seconds = (started_on - created_at).total_seconds()
            
            runs.append(
                {
                    "run_id": run["RunId"],
                    "workflow_arn": run.get("WorkflowArn", workflow_arn),
                    "status": run_detail.get("Status", "UNKNOWN"),
                    "created_at": created_at,
                    "started_at": started_on,
                    "ended_at": completed_on,
                    "queue_time_seconds": queue_time_seconds,
                }
            )

        return runs

    except Exception as e:
        logger.error(f"Failed to list workflow runs for {workflow_arn}: {e}")
        return []


def is_workflow_run_active(run: Dict[str, Any]) -> bool:
    """
    Check if a workflow run is still active (not completed).

    A run is considered complete if it has ended_at OR has a terminal status.
    Terminal statuses: SUCCESS, FAILED, STOPPED, COMPLETED

    Args:
        run: Run dictionary from list_workflow_runs with keys: run_id, status, ended_at, started_at

    Returns:
        bool: True if run is still active, False if completed
    """
    terminal_statuses = {"SUCCESS", "FAILED", "STOPPED", "COMPLETED"}
    ended_at = run.get("ended_at")
    status = run.get("status")

    # Run is complete if it has ended_at OR has terminal status
    return not (ended_at or status in terminal_statuses)


def is_workflow_run_complete(
    run_id: str,
    workflow_arn: str = None,
    connection_info: Dict[str, Any] = None,
    region: str = None,
) -> tuple[bool, str]:
    """Check if workflow run is complete by examining task statuses.

    Returns:
        tuple: (is_complete, final_status) where final_status is SUCCESS, FAILED, or STOPPED
    """
    logger = get_logger("airflow_serverless")

    try:
        client = create_airflow_serverless_client(connection_info, region)
        response = client.list_task_instances(RunId=run_id)

        tasks = response.get("TaskInstances", [])
        if not tasks:
            return False, None

        terminal_states = {"COMPLETED", "FAILED", "STOPPED", "SKIPPED"}
        task_statuses = [task.get("Status") for task in tasks]

        # Check if all tasks are in terminal state
        all_complete = all(status in terminal_states for status in task_statuses)

        if all_complete:
            # Determine final status: FAILED if any failed, SUCCESS otherwise
            if any(status == "FAILED" for status in task_statuses):
                return True, "FAILED"
            elif any(status == "STOPPED" for status in task_statuses):
                return True, "STOPPED"
            else:
                return True, "SUCCESS"

        return False, None

    except Exception as e:
        logger.error(f"Error checking task status for {run_id}: {e}")
        return False, None


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

    except logs_client.exceptions.ResourceNotFoundException:
        logger = get_logger("airflow_serverless")
        logger.error(f"Log group not found: {log_group_name}")
        raise Exception(f"Log group not found: {log_group_name}")
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
    queue_start_time = None
    total_queue_time = 0

    while time.time() - start_time < timeout_seconds:
        status_result = get_workflow_run_status(
            workflow_arn, run_id, connection_info, region
        )

        if not status_result["success"]:
            return status_result

        status = status_result["status"]
        elapsed = int(time.time() - start_time)

        # Track queue time
        if status == "QUEUED":
            if queue_start_time is None:
                queue_start_time = time.time()
                logger.info(f"Workflow run {run_id} entered QUEUED state")
        elif queue_start_time is not None:
            # Exited queue state
            queue_duration = int(time.time() - queue_start_time)
            total_queue_time += queue_duration
            logger.info(
                f"Workflow run {run_id} was in QUEUED state for {queue_duration}s"
            )
            queue_start_time = None

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
            # Log final queue time if still in queue when completed
            if queue_start_time is not None:
                queue_duration = int(time.time() - queue_start_time)
                total_queue_time += queue_duration
                logger.info(
                    f"Workflow run {run_id} was in QUEUED state for {queue_duration}s (final)"
                )

            if total_queue_time > 0:
                logger.info(
                    f"Workflow run {run_id} total QUEUED time: {total_queue_time}s"
                )

            logger.info(f"Workflow run {run_id} completed with status: {status}")
            
            # Return with final_status and proper success flag
            return {
                "final_status": status,
                "run_id": run_id,
                "success": status in ["SUCCEEDED", "SUCCESS"],
                "workflow_arn": workflow_arn,
            }

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


# Shared workflow helper functions
def generate_workflow_name(bundle_name: str, project_name: str, dag_name: str) -> str:
    """
    Generate standardized workflow name.

    Args:
        bundle_name: Application/bundle name
        project_name: Project name
        dag_name: DAG/workflow name

    Returns:
        Formatted workflow name: {bundle}_{project}_{dag}
    """
    safe_pipeline = bundle_name.replace("-", "_")
    safe_project = project_name.replace("-", "_")
    safe_dag = dag_name.replace("-", "_")
    return f"{safe_pipeline}_{safe_project}_{safe_dag}"


def find_workflow_arn(
    workflow_name: str, region: str, connection_info: Dict[str, Any] = None
) -> str:
    """
    Find workflow ARN by name.

    Args:
        workflow_name: Name of workflow to find
        region: AWS region
        connection_info: Optional connection info

    Returns:
        Workflow ARN

    Raises:
        Exception: If workflow not found
    """
    workflows = list_workflows(region=region, connection_info=connection_info)

    for wf in workflows:
        if wf["name"] == workflow_name:
            return wf["workflow_arn"]

    available = [wf["name"] for wf in workflows]
    raise Exception(
        f"Workflow '{workflow_name}' not found. Available workflows: {available}"
    )


def start_workflow_run_verified(
    workflow_arn: str,
    region: str,
    run_name: str = None,
    connection_info: Dict[str, Any] = None,
    verify_started: bool = True,
    wait_seconds: int = 10,
) -> Dict[str, Any]:
    """
    Start workflow run and optionally verify it actually started.

    This includes the tested logic from run.py that ensures the workflow
    actually transitions to a running state, not just API success.

    Args:
        workflow_arn: Workflow ARN
        region: AWS region
        run_name: Optional run name
        connection_info: Optional connection info
        verify_started: Whether to verify workflow started (default: True)
        wait_seconds: Seconds to wait before verification (default: 10)

    Returns:
        Dict with run_id, status, workflow_arn, success

    Raises:
        Exception: If workflow fails to start or verification fails
    """
    logger = get_logger("airflow_serverless")

    # Start the workflow
    result = start_workflow_run(
        workflow_arn=workflow_arn,
        run_name=run_name,
        connection_info=connection_info,
        region=region,
    )

    if not result.get("success"):
        raise Exception(f"Failed to start workflow: {result.get('error')}")

    initial_status = result.get("status")

    # Optionally verify workflow actually started
    if verify_started:
        logger.info(f"Verifying workflow started (initial status: {initial_status})")

        # Valid running states
        running_states = ["STARTING", "QUEUED", "RUNNING"]

        if initial_status not in running_states:
            logger.info(f"Waiting {wait_seconds}s before re-checking status...")
            time.sleep(wait_seconds)

            # Re-check status
            status_check = get_workflow_status(
                workflow_arn=workflow_arn,
                connection_info=connection_info,
                region=region,
            )

            current_status = (
                status_check.get("status")
                if status_check.get("success")
                else initial_status
            )

            if current_status not in running_states:
                raise Exception(
                    f"Workflow run started but status is '{current_status}' "
                    f"(expected {running_states}). "
                    f"The workflow may not have actually started."
                )

            logger.info(f"✓ Verified workflow status: {current_status}")
            result["status"] = current_status

    return result


def get_workflow_logs(
    workflow_arn: str,
    run_id: str,
    region: str,
    max_lines: int = 100,
    connection_info: Dict[str, Any] = None,
) -> List[str]:
    """
    Get workflow logs for a specific run.

    Args:
        workflow_arn: Workflow ARN
        run_id: Run ID
        region: AWS region
        max_lines: Maximum number of log lines
        connection_info: Optional connection info

    Returns:
        List of formatted log lines
    """
    # Extract workflow name and construct log group
    workflow_name = workflow_arn.split("/")[-1]
    log_group = f"/aws/mwaa-serverless/{workflow_name}/"

    log_events = get_cloudwatch_logs(
        log_group_name=log_group, region=region, limit=max_lines
    )

    # Format log events as strings
    formatted_logs = []
    for event in log_events:
        timestamp = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(event["timestamp"] / 1000)
        )
        stream = event.get("log_stream_name", "unknown")
        message = event["message"]
        formatted_logs.append(f"[{timestamp}] [{stream}] {message}")

    return formatted_logs


def monitor_workflow_logs_live(
    workflow_arn: str, region: str, run_id: str = None, callback=None
) -> dict:
    """
    Monitor workflow logs live until completion.

    Args:
        workflow_arn: Workflow ARN
        region: AWS region
        run_id: Specific run ID to monitor (if None, monitors most recent)
        callback: Optional callback function(log_event) for each log line

    Returns:
        dict with final_status, run_id, success
    """
    import time

    workflow_name = workflow_arn.split("/")[-1]
    log_group = f"/aws/mwaa-serverless/{workflow_name}/"

    last_timestamp = None
    final_status = None
    final_run_id = run_id
    first_fetch = True

    while True:
        try:
            # Check workflow runs
            runs = list_workflow_runs(workflow_arn, region=region, max_results=5)

            if not runs:
                # No runs yet, wait and retry
                time.sleep(5)
                continue

            # Find the target run
            if run_id:
                target_run = next((r for r in runs if r["run_id"] == run_id), None)
                if not target_run:
                    raise Exception(f"Run {run_id} not found")
            else:
                target_run = runs[0]  # Most recent
                final_run_id = target_run["run_id"]

            # Check if target run is still active
            is_active = is_workflow_run_active(target_run)

            # Fetch logs - on first fetch, get all logs; afterwards get incremental
            if first_fetch:
                # Get all logs from the beginning
                log_events = get_cloudwatch_logs(
                    log_group,
                    start_time=None,
                    region=region,
                    limit=10000,  # Large limit to get all logs
                )
                first_fetch = False
            else:
                # Get only new logs since last timestamp
                log_events = get_cloudwatch_logs(
                    log_group,
                    start_time=last_timestamp + 1 if last_timestamp else None,
                    region=region,
                    limit=1000,  # Increased from 50 to handle bursts
                )

            # Process logs
            if log_events:
                for event in log_events:
                    if callback:
                        callback(event)
                    last_timestamp = event["timestamp"]

            # Check if target run completed
            if not is_active:
                final_status = target_run.get("status") or "COMPLETED"
                break

            time.sleep(5)

        except Exception as e:
            # Log error but continue monitoring
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error in live monitoring: {e}")
            time.sleep(5)

    return {
        "success": final_status in ["COMPLETED", "SUCCESS"],
        "final_status": final_status,
        "run_id": final_run_id,
    }

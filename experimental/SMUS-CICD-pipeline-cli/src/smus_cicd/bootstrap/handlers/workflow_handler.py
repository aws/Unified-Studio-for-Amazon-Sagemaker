"""Workflow bootstrap action handler."""

from typing import Any, Dict

from ...helpers.logger import get_logger
from ...workflows import WorkflowOperations
from ..models import BootstrapAction

logger = get_logger("bootstrap.handlers.workflow")


def handle_workflow_action(
    action: BootstrapAction, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle workflow actions."""
    service, api = action.type.split(".", 1)

    if api == "run":
        return run_workflow(action, context)
    elif api == "logs":
        return fetch_workflow_logs(action, context)
    elif api == "monitor":
        return monitor_workflow(action, context)
    else:
        raise ValueError(f"Unknown workflow action: {api}")


def run_workflow(action: BootstrapAction, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trigger workflow run.

    Action parameters:
        workflowName: Name of workflow to trigger (required)
        wait: Whether to wait for completion (optional, default: false)
        region: AWS region override (optional)
    """
    workflow_name = action.parameters.get("workflowName")
    if not workflow_name:
        raise ValueError("workflowName is required for workflow.run action")

    wait = action.parameters.get("wait", False)
    region = action.parameters.get("region")

    manifest = context.get("manifest")
    target_config = context.get("target_config")

    if not manifest or not target_config:
        raise ValueError("Missing manifest or target_config in context")

    logger.info(f"Bootstrap action: Triggering workflow '{workflow_name}'")

    result = WorkflowOperations.trigger_workflow(
        manifest=manifest,
        target_config=target_config,
        workflow_name=workflow_name,
        wait=wait,
        region=region,
    )

    logger.info(
        f"Workflow triggered: {result['workflow_name']} (run_id: {result['run_id']})"
    )

    return {
        "action": "workflow.run",
        "workflow_name": result["workflow_name"],
        "run_id": result["run_id"],
        "status": result["status"],
        "workflow_arn": result["workflow_arn"],
    }


def fetch_workflow_logs(
    action: BootstrapAction, context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Fetch workflow logs.

    Action parameters:
        workflowName: Name of workflow (required)
        live: Stream logs continuously (optional, default: false)
        lines: Number of log lines (optional, default: 100)
        runId: Specific run ID (optional, defaults to most recent)
        region: AWS region override (optional)
    """
    workflow_name = action.parameters.get("workflowName")
    if not workflow_name:
        raise ValueError("workflowName is required for workflow.logs action")

    live = action.parameters.get("live", False)
    lines = action.parameters.get("lines", 100)
    run_id = action.parameters.get("runId")
    region = action.parameters.get("region")

    manifest = context.get("manifest")
    target_config = context.get("target_config")

    if not manifest or not target_config:
        raise ValueError("Missing manifest or target_config in context")

    region = region or target_config.domain.region

    # Get workflow status to find ARN
    status_result = WorkflowOperations.get_workflow_status(
        manifest=manifest,
        target_config=target_config,
        workflow_name=workflow_name,
        region=region,
    )

    if not status_result.get("success"):
        raise Exception(status_result.get("error", "Failed to get workflow status"))

    workflow_arn = status_result["workflow_arn"]

    logger.info(f"Bootstrap action: Fetching logs for workflow '{workflow_name}'")

    result = WorkflowOperations.fetch_logs(
        workflow_arn=workflow_arn,
        region=region,
        live=live,
        lines=lines,
        run_id=run_id,
    )

    if not result.get("success"):
        raise Exception(result.get("error", "Failed to fetch logs"))

    logger.info(f"Fetched {len(result.get('logs', []))} log lines")

    return {
        "action": "workflow.logs",
        "workflow_name": workflow_name,
        "run_id": result["run_id"],
        "status": result["status"],
        "log_lines": len(result.get("logs", [])),
    }


def monitor_workflow(
    action: BootstrapAction, context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Monitor workflow status.

    Action parameters:
        workflowName: Name of workflow (required)
        region: AWS region override (optional)
    """
    workflow_name = action.parameters.get("workflowName")
    if not workflow_name:
        raise ValueError("workflowName is required for workflow.monitor action")

    region = action.parameters.get("region")

    manifest = context.get("manifest")
    target_config = context.get("target_config")

    if not manifest or not target_config:
        raise ValueError("Missing manifest or target_config in context")

    logger.info(f"Bootstrap action: Monitoring workflow '{workflow_name}'")

    result = WorkflowOperations.get_workflow_status(
        manifest=manifest,
        target_config=target_config,
        workflow_name=workflow_name,
        region=region,
    )

    if not result.get("success"):
        raise Exception(result.get("error", "Failed to get workflow status"))

    logger.info(f"Workflow status retrieved: {len(result.get('runs', []))} recent runs")

    return {
        "action": "workflow.monitor",
        "workflow_name": result["workflow_name"],
        "workflow_arn": result["workflow_arn"],
        "recent_runs": result.get("runs", []),
    }

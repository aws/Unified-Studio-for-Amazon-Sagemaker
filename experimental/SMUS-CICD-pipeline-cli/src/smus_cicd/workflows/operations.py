"""Core workflow operations - reusable by commands and bootstrap actions."""

from typing import Any, Dict, Optional

from ..helpers import airflow_serverless
from ..helpers.logger import get_logger

logger = get_logger(__name__)


class WorkflowOperations:
    """Reusable workflow operations for serverless Airflow and MWAA."""

    @staticmethod
    def trigger_workflow(
        manifest,
        target_config,
        workflow_name: str,
        wait: bool = False,
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Trigger a workflow run.

        Args:
            manifest: Application manifest
            target_config: Target configuration
            workflow_name: Name of workflow to trigger
            wait: Whether to wait for completion
            region: AWS region (defaults to target_config.domain.region)

        Returns:
            Dict with success, run_id, status, workflow_arn
        """
        region = region or target_config.domain.region

        # Generate workflow name using helper
        full_workflow_name = airflow_serverless.generate_workflow_name(
            bundle_name=manifest.application_name,
            project_name=target_config.project.name,
            dag_name=workflow_name,
        )

        logger.info(f"Triggering workflow: {full_workflow_name}")

        # Find workflow ARN using helper
        workflow_arn = airflow_serverless.find_workflow_arn(
            workflow_name=full_workflow_name, region=region
        )

        # Start workflow run with verification
        result = airflow_serverless.start_workflow_run_verified(
            workflow_arn=workflow_arn, region=region, verify_started=True
        )

        logger.info(
            f"Workflow started: {result.get('run_id')} (status: {result.get('status')})"
        )

        return {
            "success": True,
            "run_id": result.get("run_id"),
            "status": result.get("status"),
            "workflow_arn": workflow_arn,
            "workflow_name": full_workflow_name,
        }

    @staticmethod
    def fetch_logs(
        workflow_arn: str,
        region: str,
        live: bool = False,
        lines: int = 100,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch workflow logs.

        Args:
            workflow_arn: Workflow ARN
            region: AWS region
            live: Whether to stream logs continuously and wait for completion
            lines: Number of log lines to fetch (ignored if live=True)
            run_id: Optional specific run ID

        Returns:
            Dict with logs and metadata
        """
        logger.info(f"Fetching logs for workflow: {workflow_arn}")

        if live:
            # Use live monitoring - streams logs until completion
            logger.info("Starting live log monitoring...")
            
            logs = []
            
            def log_callback(event):
                logs.append(event)
            
            result = airflow_serverless.monitor_workflow_logs_live(
                workflow_arn, region, callback=log_callback
            )
            
            return {
                "success": result["success"],
                "run_id": result["run_id"],
                "status": result["final_status"],
                "logs": logs,
                "workflow_arn": workflow_arn,
            }
        
        # Static log fetch (original behavior)
        runs = airflow_serverless.list_workflow_runs(workflow_arn, region=region)

        if not runs:
            return {"success": False, "error": "No workflow runs found"}

        # Use specified run_id or most recent
        target_run = None
        if run_id:
            target_run = next((r for r in runs if r["run_id"] == run_id), None)
        else:
            target_run = runs[0]  # Most recent

        if not target_run:
            return {"success": False, "error": f"Run {run_id} not found"}

        # Fetch logs
        logs = airflow_serverless.get_workflow_logs(
            workflow_arn, target_run["run_id"], region=region, max_lines=lines
        )

        return {
            "success": True,
            "run_id": target_run["run_id"],
            "status": target_run.get("status"),
            "logs": logs,
            "workflow_arn": workflow_arn,
        }

    @staticmethod
    def get_workflow_status(
        manifest, target_config, workflow_name: str, region: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get workflow status.

        Args:
            manifest: Application manifest
            target_config: Target configuration
            workflow_name: Name of workflow
            region: AWS region

        Returns:
            Dict with workflow status information
        """
        region = region or target_config.domain.region

        # Generate workflow name using helper
        full_workflow_name = airflow_serverless.generate_workflow_name(
            bundle_name=manifest.application_name,
            project_name=target_config.project.name,
            dag_name=workflow_name,
        )

        # Find workflow ARN using helper
        try:
            workflow_arn = airflow_serverless.find_workflow_arn(
                workflow_name=full_workflow_name, region=region
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

        # Get recent runs
        runs = airflow_serverless.list_workflow_runs(workflow_arn, region=region)

        return {
            "success": True,
            "workflow_arn": workflow_arn,
            "workflow_name": full_workflow_name,
            "runs": runs[:5] if runs else [],  # Last 5 runs
        }

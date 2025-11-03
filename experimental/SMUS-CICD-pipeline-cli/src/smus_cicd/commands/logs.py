"""Logs command implementation for workflow log monitoring."""

import json
import time
from typing import Optional

import typer

from ..helpers.utils import load_config


def logs_command(
    workflow: Optional[str] = None,
    live: bool = False,
    output: str = "TEXT",
    lines: int = 100,
) -> None:
    """
    Fetch and display workflow logs from CloudWatch.

    Args:
        workflow: Workflow ARN to fetch logs for
        live: Keep fetching logs until workflow terminates
        output: Output format (TEXT or JSON)
        lines: Number of log lines to fetch (default: 100)
    """
    if not workflow:
        typer.echo("❌ Error: --workflow parameter is required")
        typer.echo(
            "Usage: smus-cli logs --workflow arn:aws:airflow-serverless:region:account:workflow/name"
        )
        raise typer.Exit(1)

    try:
        config = load_config()

        # Determine if this is an Overdrive workflow ARN
        if "airflow-serverless" in workflow:
            _monitor_airflow_serverless_logs(workflow, live, output, lines, config)
        else:
            typer.echo("❌ Error: Only Overdrive workflow ARNs are currently supported")
            typer.echo(
                "Expected format: arn:aws:airflow-serverless:region:account:workflow/name"
            )
            raise typer.Exit(1)

    except Exception as e:
        if output.upper() == "JSON":
            typer.echo(json.dumps({"error": str(e)}, indent=2))
        else:
            typer.echo(f"❌ Error fetching logs: {e}")
        raise typer.Exit(1)


def _monitor_airflow_serverless_logs(
    workflow_arn: str, live: bool, output: str, lines: int, config: dict
) -> None:
    """
    Monitor Overdrive workflow logs.

    Args:
        workflow_arn: Overdrive workflow ARN
        live: Whether to continuously monitor logs
        output: Output format (TEXT or JSON)
        lines: Number of log lines to fetch
        config: Configuration dictionary
    """
    from ..helpers import airflow_serverless

    # Extract region from workflow ARN
    arn_parts = workflow_arn.split(":")
    if len(arn_parts) >= 4:
        region = arn_parts[3]
    else:
        region = config.get("region", "us-east-2")

    # Extract workflow name for display
    workflow_name = workflow_arn.split("/")[-1]

    if output.upper() != "JSON":
        typer.echo(f"📋 Fetching logs for workflow: {workflow_name}")
        typer.echo(f"🔗 ARN: {workflow_arn}")
        if live:
            typer.echo("🔄 Live monitoring enabled - Press Ctrl+C to stop")
        typer.echo("=" * 80)

    # Get workflow status first
    workflow_status = airflow_serverless.get_workflow_status(
        workflow_arn, region=region
    )

    if not workflow_status.get("success"):
        error_msg = f"Failed to get workflow status: {workflow_status.get('error')}"
        if output.upper() == "JSON":
            typer.echo(json.dumps({"error": error_msg}, indent=2))
        else:
            typer.echo(f"❌ {error_msg}")
        raise typer.Exit(1)

    # For live monitoring, check if there's an active workflow run
    active_run = False
    if live:
        # Get recent workflow runs to check if any are active
        recent_runs = airflow_serverless.list_workflow_runs(
            workflow_arn, region=region, max_results=1
        )

        if not recent_runs:
            error_msg = (
                "No workflow runs found. Start a workflow run before fetching logs."
            )
            if output.upper() == "JSON":
                typer.echo(json.dumps({"error": error_msg}, indent=2))
            else:
                typer.echo(f"❌ {error_msg}")
            raise typer.Exit(1)

        # Check the most recent run status
        latest_run = recent_runs[0]
        run_status = latest_run.get("status")

        # Valid active states for live monitoring
        if run_status in ["STARTING", "QUEUED", "RUNNING"]:
            active_run = True
        else:
            # Run already ended - fetch static logs instead
            if output.upper() != "JSON":
                typer.echo(f"ℹ️  Workflow run already completed (status: {run_status})")
                typer.echo(f"   Run ID: {latest_run.get('run_id')}")
                typer.echo("   Fetching all logs...")
            active_run = False

    # Construct log group name from workflow name
    # Log group format: /aws/mwaa-serverless/<workflow-name>/
    log_group = f"/aws/mwaa-serverless/{workflow_name}/"

    if output.upper() != "JSON":
        typer.echo(f"📁 Log Group: {log_group}")
        typer.echo(f"📊 Workflow Status: {workflow_status.get('status')}")
        typer.echo("-" * 80)

    # Fetch logs
    try:
        if live and active_run:
            _live_log_monitoring(workflow_arn, region, output, config)
        else:
            _fetch_static_logs(workflow_arn, region, output, lines, config)

    except KeyboardInterrupt:
        if output.upper() != "JSON":
            typer.echo("\n🛑 Log monitoring stopped by user")
        raise typer.Exit(0)


def _fetch_static_logs(
    workflow_arn: str, region: str, output: str, lines: int, config: dict
) -> None:
    """
    Fetch static logs for a workflow.

    Args:
        workflow_arn: Workflow ARN
        region: AWS region
        output: Output format
        lines: Number of lines to fetch
        config: Configuration dictionary
    """
    from ..helpers import airflow_serverless

    # Extract workflow name and construct log group
    workflow_name = workflow_arn.split("/")[-1]
    log_group = f"/aws/mwaa-serverless/{workflow_name}/"

    log_events = airflow_serverless.get_cloudwatch_logs(
        log_group, region=region, limit=lines
    )

    if output.upper() == "JSON":
        output_data = {
            "workflow_arn": workflow_arn,
            "log_events": log_events,
            "total_events": len(log_events),
        }
        typer.echo(json.dumps(output_data, indent=2, default=str))
    else:
        if log_events:
            typer.echo(f"📄 Showing {len(log_events)} log events:")
            typer.echo()

            for event in log_events:
                timestamp = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(event["timestamp"] / 1000)
                )
                stream = event.get("log_stream_name", "unknown")
                message = event["message"]

                typer.echo(f"[{timestamp}] [{stream}] {message}")
        else:
            typer.echo("📄 No log events found")


def _live_log_monitoring(
    workflow_arn: str, region: str, output: str, config: dict
) -> None:
    """
    Continuously monitor workflow logs until completion.

    Args:
        workflow_arn: Workflow ARN
        region: AWS region
        output: Output format
        config: Configuration dictionary
    """
    from ..helpers import airflow_serverless

    if output.upper() != "JSON":
        typer.echo("🔄 Starting live log monitoring...")
        typer.echo("   Press Ctrl+C to stop monitoring")
        typer.echo()

    # Extract workflow name and construct log group
    workflow_name = workflow_arn.split("/")[-1]
    log_group = f"/aws/mwaa-serverless/{workflow_name}/"

    last_timestamp = None
    check_count = 0

    while True:
        check_count += 1

        try:
            # Get current workflow runs to check if any are active
            runs = airflow_serverless.list_workflow_runs(
                workflow_arn, region=region, max_results=5
            )

            active_runs = [
                run
                for run in runs
                if run["status"] in ["STARTING", "QUEUED", "RUNNING"]
            ]

            # Fetch new logs
            log_events = airflow_serverless.get_cloudwatch_logs(
                log_group, start_time=last_timestamp, region=region, limit=50
            )

            # Display new log events
            if log_events:
                if output.upper() == "JSON":
                    # For JSON output, emit each log event as a separate JSON object
                    for event in log_events:
                        log_data = {
                            "timestamp": event["timestamp"],
                            "stream_name": event.get("log_stream_name", "unknown"),
                            "message": event["message"],
                            "workflow_arn": workflow_arn,
                        }
                        typer.echo(json.dumps(log_data, default=str))
                else:
                    for event in log_events:
                        timestamp = time.strftime(
                            "%H:%M:%S", time.localtime(event["timestamp"] / 1000)
                        )
                        stream = event.get("log_stream_name", "unknown")
                        message = event["message"]

                        typer.echo(f"[{timestamp}] [{stream}] {message}")

                # Update last timestamp
                if log_events:
                    last_timestamp = int(
                        max(event["timestamp"] for event in log_events)
                    )

            # Check if we should continue monitoring
            if not active_runs:
                if output.upper() != "JSON":
                    typer.echo(
                        "\n✅ No active workflow runs found. Monitoring complete."
                    )
                break

            # Show status update if no new logs but workflow still running
            if not log_events and active_runs and output.upper() != "JSON":
                run_info = active_runs[0]
                run_id = run_info.get("run_id", "unknown")
                status = run_info.get("status", "unknown")
                typer.echo(
                    f"🔄 [{time.strftime('%H:%M:%S')}] Workflow still {status} (Run: {run_id}, ARN: {workflow_arn}) - waiting for logs..."
                )

            time.sleep(10)  # Check every 10 seconds

        except Exception as e:
            if output.upper() == "JSON":
                error_data = {
                    "error": str(e),
                    "workflow_arn": workflow_arn,
                    "timestamp": time.time(),
                }
                typer.echo(json.dumps(error_data, default=str))
            else:
                typer.echo(f"❌ Error during live monitoring: {e}")
            break

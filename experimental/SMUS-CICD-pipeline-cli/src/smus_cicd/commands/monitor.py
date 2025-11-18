"""Monitor command implementation."""

import datetime
import json
import logging
import time
from typing import Optional

import typer

from ..application import ApplicationManifest
from ..helpers.datazone import target_uses_serverless_airflow
from ..helpers.utils import (  # noqa: F401
    build_domain_config,
    get_datazone_project_info,
    load_config,
)

logger = logging.getLogger(__name__)


def monitor_command(
    targets: Optional[str], manifest_file: str, output: str, live: bool = False
):
    """Monitor workflow status across target environments."""
    if live:
        _monitor_live(targets, manifest_file, output)
    else:
        _monitor_once(targets, manifest_file, output)


def _monitor_live(targets: Optional[str], manifest_file: str, output: str):
    """Monitor workflows continuously until all runs complete."""
    # Track previous run states
    previous_states = {}

    # Initial full display
    typer.echo("🔄 Starting live monitoring... (Press Ctrl+C to stop)\n")
    _monitor_once(targets, manifest_file, output, previous_states=previous_states)

    try:
        while True:
            time.sleep(10)  # Poll every 10 seconds

            # Check for status changes
            has_running = _check_status_changes(
                targets, manifest_file, output, previous_states
            )

            # If no workflows are running, exit
            if not has_running:
                typer.echo("\n✅ All workflows completed")
                break

    except KeyboardInterrupt:
        typer.echo("\n\n⏹️  Monitoring stopped by user")
        raise typer.Exit(0)


def _check_status_changes(
    targets: Optional[str], manifest_file: str, output: str, previous_states: dict
) -> bool:
    """Check for workflow status changes and report them. Returns True if any workflows are running."""
    manifest = ApplicationManifest.from_file(manifest_file)

    # Parse targets
    target_list = []
    if targets:
        target_list = [t.strip() for t in targets.split(",")]

    targets_to_monitor = {}
    if target_list:
        for stage_name in target_list:
            if stage_name in manifest.stages:
                targets_to_monitor[stage_name] = manifest.stages[stage_name]
    else:
        targets_to_monitor = manifest.stages

    has_running = False

    for stage_name, target_config in targets_to_monitor.items():
        config = build_domain_config(target_config)

        # Check if this target uses serverless Airflow
        uses_airflow_serverless = target_uses_serverless_airflow(
            manifest, target_config
        )

        if uses_airflow_serverless:
            from ..helpers import airflow_serverless

            # List workflows
            all_workflows = airflow_serverless.list_workflows(
                region=config.get("region")
            )
            bundle_name = manifest.application_name
            target_project = target_config.project.name

            relevant_workflows = [
                w
                for w in all_workflows
                if w.get("tags", {}).get("Pipeline") == bundle_name
                and w.get("tags", {}).get("Target") == target_project
            ]

            for workflow in relevant_workflows:
                workflow_arn = workflow["workflow_arn"]
                workflow_name = workflow["name"]

                # Get recent runs
                recent_runs = airflow_serverless.list_workflow_runs(
                    workflow_arn, region=config.get("region"), max_results=1
                )

                if recent_runs:
                    latest_run = recent_runs[0]
                    run_id = latest_run.get("run_id", "N/A")
                    status = latest_run.get("status")

                    # Check if run is still active using shared helper
                    if airflow_serverless.is_workflow_run_active(latest_run):
                        run_status = "RUNNING"
                        has_running = True
                    else:
                        run_status = status or "COMPLETED"

                    # Check for status change
                    key = f"{stage_name}:{workflow_name}:{run_id}"
                    prev_status = previous_states.get(key)

                    if prev_status and prev_status != run_status:
                        # Status changed - report it
                        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                        typer.echo(
                            f"[{timestamp}] {workflow_name} (run {run_id[:8]}...): {prev_status} → {run_status}"
                        )

                    # Update state
                    previous_states[key] = run_status

    return has_running


def _monitor_once(
    targets: Optional[str],
    manifest_file: str,
    output: str,
    previous_states: dict = None,
):
    """Monitor workflow status across target environments once."""
    try:
        # Load pipeline manifest using centralized parser
        manifest = ApplicationManifest.from_file(manifest_file)

        # Check if manifest has any workflows defined
        if not (hasattr(manifest.content, "workflows") and manifest.content.workflows):
            if output.upper() == "JSON":
                typer.echo(
                    json.dumps(
                        {
                            "bundle": manifest.application_name,
                            "message": "No workflows defined in manifest",
                            "status": "success",
                        },
                        indent=2,
                    )
                )
            else:
                typer.echo(f"Pipeline: {manifest.application_name}")
                typer.echo("📋 No workflows defined in manifest - nothing to monitor")
            return

        # Parse targets - handle single target or comma-separated list
        target_list = []
        if targets:
            target_list = [t.strip() for t in targets.split(",")]

        # Prepare output data structure for JSON format
        output_data = {
            "bundle": manifest.application_name,
            "targets": {},
            "monitoring_timestamp": None,
        }

        # Determine which targets to monitor
        targets_to_monitor = {}
        if target_list:
            # Monitor specific targets from the list
            for stage_name in target_list:
                if stage_name in manifest.stages:
                    targets_to_monitor[stage_name] = manifest.stages[stage_name]
                else:
                    error_msg = f"Target '{stage_name}' not found in manifest"
                    available_targets = list(manifest.stages.keys())
                    if output.upper() == "JSON":
                        output_data["error"] = error_msg
                        output_data["available_targets"] = available_targets
                        typer.echo(json.dumps(output_data, indent=2))
                    else:
                        typer.echo(f"Error: {error_msg}", err=True)
                        typer.echo(
                            f"Available targets: {', '.join(available_targets)}",
                            err=True,
                        )
                    raise typer.Exit(1)
        else:
            targets_to_monitor = manifest.stages

        # TEXT output header
        if output.upper() != "JSON":
            typer.echo(f"Pipeline: {manifest.application_name}")

        # Validate MWAA/MWAA Serverless health for targets before monitoring
        healthy_targets = []
        for stage_name, target_config in targets_to_monitor.items():
            # Load AWS config
            config = build_domain_config(target_config)

            project_name = target_config.project.name
            if output.upper() != "JSON":
                typer.echo(f"\n📋 Target: {stage_name} (Project: {project_name})")
                typer.echo(
                    f"   Domain: {target_config.domain.name} ({target_config.domain.region})"
                )

            # Check if this target uses serverless Airflow
            uses_airflow_serverless = target_uses_serverless_airflow(
                manifest, target_config
            )

            if uses_airflow_serverless:
                # Validate serverless Airflow health
                from ..helpers.airflow_serverless import (
                    validate_airflow_serverless_health,
                )

                if validate_airflow_serverless_health(project_name, config):
                    healthy_targets.append(stage_name)
                    if output.upper() != "JSON":
                        typer.echo("   🚀 Serverless Airflow service is healthy")
                else:
                    if output.upper() != "JSON":
                        typer.echo(
                            f"⚠️  Skipping monitoring for target '{stage_name}' - MWAA Serverless not healthy"
                        )
            else:
                # Validate MWAA health before monitoring
                from ..helpers.mwaa import validate_mwaa_health

                if validate_mwaa_health(project_name, config):
                    healthy_targets.append(stage_name)
                else:
                    if output.upper() != "JSON":
                        typer.echo(
                            f"⚠️  Skipping monitoring for target '{stage_name}' - MWAA not healthy"
                        )

        if not healthy_targets:
            if output.upper() == "JSON":
                output_data["error"] = "No healthy workflow environments found"
                typer.echo(json.dumps(output_data, indent=2))
            else:
                typer.echo(
                    "❌ No healthy workflow environments found. Cannot monitor workflows."
                )
            raise typer.Exit(1)

        # Add timestamp
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        output_data["monitoring_timestamp"] = timestamp

        # Track errors to exit with proper code
        has_errors = False

        # Monitor each target
        for stage_name, target_config in targets_to_monitor.items():
            # Skip unhealthy targets
            if stage_name not in healthy_targets:
                continue

            target_data = {
                "project": {"name": target_config.project.name},
                "domain": {
                    "name": target_config.domain.name,
                    "region": target_config.domain.region,
                },
                "status": "unknown",
                "workflows": {},
                "connections": {},
            }

            if output.upper() != "JSON":
                typer.echo(f"\n🎯 Target: {stage_name}")
                typer.echo(f"   Project: {target_config.project.name}")

            try:
                config = build_domain_config(target_config)

                project_info = get_datazone_project_info(
                    target_config.project.name, config
                )

                if project_info.get("project_id") and "error" not in project_info:
                    project_connections = project_info.get("connections", {})

                    target_data["project"]["id"] = project_info["project_id"]
                    target_data["project"]["status"] = project_info.get(
                        "status", "UNKNOWN"
                    )
                    target_data["project"]["owners"] = project_info.get("owners", [])
                    target_data["connections"] = project_connections
                    target_data["status"] = (
                        "active"
                        if project_info.get("status") == "ACTIVE"
                        else "inactive"
                    )

                    if output.upper() != "JSON":
                        typer.echo(f"   Project ID: {project_info['project_id']}")
                        typer.echo(
                            f"   Status: {project_info.get('status', 'UNKNOWN')}"
                        )
                        if project_info.get("owners"):
                            owners_str = ", ".join(project_info["owners"])
                            typer.echo(f"   Owners: {owners_str}")

                    # Check if this target uses serverless Airflow
                    uses_airflow_serverless = target_uses_serverless_airflow(
                        manifest, target_config
                    )

                    if uses_airflow_serverless:
                        # Monitor serverless Airflow workflows
                        airflow_serverless_data = _monitor_airflow_serverless_workflows(
                            manifest, target_config, config, output, previous_states
                        )
                        target_data["workflows"].update(airflow_serverless_data)
                    else:
                        # Monitor MWAA workflow connections
                        mwaa_data = _monitor_mwaa_workflows(
                            manifest, target_config, project_connections, output
                        )
                        target_data["workflows"].update(mwaa_data)

                else:
                    has_errors = True
                    target_data["status"] = "error"
                    target_data["error"] = project_info.get("error", "Unknown error")
                    if output.upper() != "JSON":
                        typer.echo(
                            f"   ❌ Error getting project info: {project_info.get('error', 'Unknown error')}"
                        )

            except Exception as e:
                has_errors = True
                target_data["status"] = "error"
                target_data["error"] = str(e)
                if output.upper() != "JSON":
                    typer.echo(f"   ❌ Error monitoring target: {e}")

            output_data["targets"][stage_name] = target_data

        # Show manifest workflows summary
        if (
            hasattr(manifest, "workflows")
            and manifest.content.workflows
            and output.upper() != "JSON"
        ):
            typer.echo("\n📋 Manifest Workflows:")
            for workflow in manifest.content.workflows:
                typer.echo(
                    f"   - {workflow.workflow_name} (Connection: {workflow.connection_name})"
                )

        # Output JSON if requested
        if output.upper() == "JSON":
            # Add manifest workflows to JSON output
            if hasattr(manifest, "workflows") and manifest.content.workflows:
                output_data["manifest_workflows"] = []
                for workflow in manifest.content.workflows:
                    workflow_data = {
                        "workflow_name": workflow.workflow_name,
                        "connection_name": workflow.connection_name,
                        "connectionName": workflow.get("connectionName", ""),
                    }
                    if hasattr(workflow, "parameters") and workflow.parameters:
                        workflow_data["parameters"] = workflow.parameters
                    output_data["manifest_workflows"].append(workflow_data)

            typer.echo(json.dumps(output_data, indent=2))

        # Check if any targets have no workflow connections and fail
        targets_with_no_workflows = [
            name
            for name, data in output_data["targets"].items()
            if data.get("status") == "no_workflows"
        ]

        if targets_with_no_workflows:
            if output.upper() != "JSON":
                typer.echo(
                    f"\n❌ Error: No workflow connections found in targets: {', '.join(targets_with_no_workflows)}"
                )
            raise typer.Exit(1)

        # Exit with error code if any errors occurred
        if has_errors:
            if output.upper() != "JSON":
                typer.echo("\n❌ Command failed due to errors above", err=True)
            raise typer.Exit(1)

    except typer.Exit:
        raise
    except Exception as e:
        if output.upper() == "JSON":
            typer.echo(json.dumps({"error": str(e)}, indent=2))
        else:
            typer.echo(f"Error monitoring pipeline: {e}", err=True)
        raise typer.Exit(1)


def _monitor_airflow_serverless_workflows(
    manifest: ApplicationManifest,
    target_config,
    config: dict,
    output: str,
    previous_states: dict = None,
) -> dict:
    """
    Monitor serverless Airflow workflows for a target.

    Args:
        manifest: Pipeline manifest object
        target_config: Target configuration object
        config: Configuration dictionary
        output: Output format (JSON or TEXT)

    Returns:
        Dictionary of workflow monitoring data
    """
    workflows_data = {}

    try:
        from ..helpers import airflow_serverless

        if output.upper() != "JSON":
            typer.echo("\n   🚀 Serverless Airflow Workflows:")

        # List all serverless Airflow workflows
        all_workflows = airflow_serverless.list_workflows(region=config.get("region"))

        # Filter workflows that belong to this pipeline/target using tags
        bundle_name = manifest.application_name
        stage_name = target_config.project.name

        relevant_workflows = []
        for workflow in all_workflows:
            workflow_tags = workflow.get("tags", {})
            # Check if workflow tags match our pipeline and target
            if (
                workflow_tags.get("Pipeline") == bundle_name
                and workflow_tags.get("Target") == stage_name
            ):
                relevant_workflows.append(workflow)

        if relevant_workflows:
            serverlessairflow_data = {
                "service": "mwaa-serverless",
                "status": "healthy",
                "workflows": {},
            }

            # Prepare table data
            table_rows = []
            for workflow in relevant_workflows:
                workflow_arn = workflow["workflow_arn"]
                workflow_name = workflow["name"]

                # Get workflow details
                workflow_status = airflow_serverless.get_workflow_status(
                    workflow_arn, region=config.get("region")
                )

                # Get recent workflow runs
                recent_runs = airflow_serverless.list_workflow_runs(
                    workflow_arn, region=config.get("region"), max_results=1
                )

                # Extract run details
                run_id = "N/A"
                run_status = "No runs"
                start_time = "N/A"
                duration = "N/A"

                if recent_runs:
                    latest_run = recent_runs[0]
                    run_id = latest_run.get("run_id", "N/A")
                    run_status = latest_run.get("RunDetailSummary", {}).get("Status")

                    # None status means initializing, treat as valid
                    if run_status is None:
                        run_status = "INITIALIZING"

                    # Track state for live monitoring
                    if previous_states is not None:
                        key = f"{target_config.project.name}:{workflow_name}:{run_id}"
                        previous_states[key] = run_status

                    # Calculate duration
                    started_at = latest_run.get("started_at")
                    ended_at = latest_run.get("ended_at")

                    if started_at:
                        from datetime import datetime

                        start_time = (
                            started_at.strftime("%Y-%m-%d %H:%M:%S")
                            if hasattr(started_at, "strftime")
                            else str(started_at)
                        )

                        if ended_at:
                            # Completed run - calculate from start to end
                            if hasattr(started_at, "timestamp") and hasattr(
                                ended_at, "timestamp"
                            ):
                                duration_seconds = (
                                    ended_at - started_at
                                ).total_seconds()
                                hours = int(duration_seconds // 3600)
                                minutes = int((duration_seconds % 3600) // 60)
                                duration = (
                                    f"{hours}h {minutes}m"
                                    if hours > 0
                                    else f"{minutes}m"
                                )
                        else:
                            # Still running - calculate from start to now
                            if hasattr(started_at, "timestamp"):
                                now = (
                                    datetime.now(started_at.tzinfo)
                                    if started_at.tzinfo
                                    else datetime.utcnow()
                                )
                                duration_seconds = (now - started_at).total_seconds()
                                hours = int(duration_seconds // 3600)
                                minutes = int((duration_seconds % 3600) // 60)
                                duration = (
                                    f"{hours}h {minutes}m"
                                    if hours > 0
                                    else f"{minutes}m"
                                )
                            else:
                                duration = "Running..."

                workflow_data = {
                    "workflow_arn": workflow_arn,
                    "status": workflow_status.get("status", "UNKNOWN"),
                    "trigger_mode": workflow_status.get("trigger_mode", "scheduled"),
                    "run_id": run_id,
                    "run_status": run_status,
                    "start_time": start_time,
                    "duration": duration,
                }

                serverlessairflow_data["workflows"][workflow_name] = workflow_data

                # Truncate workflow name for display
                display_name = (
                    workflow_name
                    if len(workflow_name) <= 40
                    else workflow_name[:37] + "..."
                )

                table_rows.append(
                    [
                        display_name,
                        workflow_status.get("status", "UNKNOWN"),
                        workflow_status.get("trigger_mode", "scheduled"),
                        run_id[:8] + "..." if len(run_id) > 8 else run_id,
                        run_status,
                        start_time,
                        duration,
                    ]
                )

            if output.upper() != "JSON":
                # Print table header
                typer.echo(
                    f"\n      {'Workflow':<40} {'Status':<10} {'Trigger':<12} {'Run ID':<12} {'Run Status':<12} {'Start Time':<20} {'Duration':<10}"
                )
                typer.echo(
                    f"      {'-' * 40} {'-' * 10} {'-' * 12} {'-' * 12} {'-' * 12} {'-' * 20} {'-' * 10}"
                )

                # Print table rows
                for row in table_rows:
                    typer.echo(
                        f"      {row[0]:<40} {row[1]:<10} {row[2]:<12} {row[3]:<12} {row[4]:<12} {row[5]:<20} {row[6]:<10}"
                    )

            workflows_data["mwaa-serverless"] = serverlessairflow_data
        else:
            if output.upper() != "JSON":
                typer.echo(
                    "      ℹ️  No Serverless Airflow workflows found for this pipeline/target"
                )

            workflows_data["mwaa-serverless"] = {
                "service": "mwaa-serverless",
                "status": "no_workflows",
                "workflows": {},
            }

    except Exception as e:
        if output.upper() != "JSON":
            typer.echo(f"      ❌ Error monitoring MWAA Serverless workflows: {e}")

        workflows_data["mwaa-serverless"] = {
            "service": "mwaa-serverless",
            "status": "error",
            "error": str(e),
            "workflows": {},
        }

    return workflows_data


def _monitor_mwaa_workflows(
    manifest: ApplicationManifest, target_config, project_connections: dict, output: str
) -> dict:
    """
    Monitor MWAA workflows for a target.

    Args:
        manifest: Pipeline manifest object
        target_config: Target configuration object
        project_connections: Project connection information
        output: Output format (JSON or TEXT)

    Returns:
        Dictionary of workflow monitoring data
    """
    workflows_data = {}

    # Monitor workflow connections
    workflow_connections = {
        name: info
        for name, info in project_connections.items()
        if info.get("type") in ["MWAA", "WORKFLOWS_MWAA"]
    }

    if workflow_connections:
        if output.upper() != "JSON":
            typer.echo("\n   📊 MWAA Workflow Status:")

        for conn_name, conn_info in workflow_connections.items():
            env_name = conn_info.get("environmentName")
            if env_name:
                workflow_data = {
                    "environment": env_name,
                    "connection_id": conn_info.get("connectionId"),
                    "status": "unknown",
                    "dags": {},
                }

                try:
                    from ..helpers import mwaa

                    # Get DAG list and details
                    existing_workflows = mwaa.list_dags(
                        env_name, target_config.domain.region, conn_info
                    )
                    all_dag_details = mwaa.get_all_dag_details(
                        env_name, target_config.domain.region, conn_info
                    )

                    workflow_data["status"] = "healthy"

                    if output.upper() != "JSON":
                        typer.echo(f"      🔧 {conn_name} ({env_name})")

                        # Get Airflow UI URL
                        airflow_url = mwaa.get_airflow_ui_url(
                            env_name,
                            target_config.domain.region,
                            conn_info,
                        )
                        if airflow_url:
                            # Format as clickable hyperlink
                            hyperlink = f"\033]8;;{airflow_url}\033\\{airflow_url}\033]8;;\033\\"
                            typer.echo(f"         🌐 Airflow UI: {hyperlink}")

                    # Get manifest workflows for comparison
                    manifest_workflows = set()
                    if hasattr(manifest, "workflows") and manifest.content.workflows:
                        manifest_workflows = {
                            w.workflow_name for w in manifest.content.workflows
                        }

                    # Monitor each DAG
                    for dag_name in sorted(existing_workflows):
                        dag_details = all_dag_details.get(dag_name, {})
                        schedule = dag_details.get("schedule_interval", "Unknown")
                        active = dag_details.get("active", None)
                        status = (
                            "ACTIVE"
                            if active
                            else ("PAUSED" if active is False else "UNKNOWN")
                        )

                        # Get recent DAG runs for monitoring
                        try:
                            dag_runs = mwaa.get_dag_runs(
                                dag_name,
                                env_name,
                                target_config.domain.region,
                                conn_info,
                                limit=5,
                            )
                            recent_status = "No runs"
                            if dag_runs:
                                recent_run = dag_runs[0]
                                recent_status = recent_run.get("state", "Unknown")
                        except Exception:
                            dag_runs = []
                            recent_status = "Unknown"

                        workflow_data["dags"][dag_name] = {
                            "schedule": schedule,
                            "status": status,
                            "recent_run_status": recent_status,
                            "in_manifest": dag_name in manifest_workflows,
                            "recent_runs": (dag_runs[:3] if dag_runs else []),
                        }

                        if output.upper() != "JSON":
                            status_icon = (
                                "✅"
                                if recent_status == "success"
                                else (
                                    "❌"
                                    if recent_status == "failed"
                                    else ("⏸️" if status == "PAUSED" else "🔄")
                                )
                            )
                            manifest_icon = (
                                "✓" if dag_name in manifest_workflows else "-"
                            )

                            typer.echo(
                                f"         {status_icon} {manifest_icon} {dag_name}"
                            )
                            typer.echo(
                                f"            Schedule: {schedule} | Status: {status} | Recent: {recent_status}"
                            )

                except Exception as e:
                    workflow_data["status"] = "error"
                    workflow_data["error"] = str(e)

                    if output.upper() != "JSON":
                        typer.echo(f"      ❌ Error monitoring {conn_name}: {e}")

                workflows_data[conn_name] = workflow_data
    else:
        if output.upper() != "JSON":
            typer.echo("   ❌ No MWAA workflow connections found")

    return workflows_data

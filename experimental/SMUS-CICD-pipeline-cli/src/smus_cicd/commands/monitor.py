"""Monitor command implementation."""

import datetime
import json
from typing import Optional

import typer

from ..helpers.utils import get_datazone_project_info
from ..pipeline import PipelineManifest


def monitor_command(targets: Optional[str], manifest_file: str, output: str):
    """Monitor workflow status across target environments."""
    try:
        # Load pipeline manifest using centralized parser
        manifest = PipelineManifest.from_file(manifest_file)

        # Validate MWAA health before monitoring
        from ..helpers.mwaa import validate_mwaa_health
        from ..helpers.utils import load_config

        config = load_config()
        # Add domain information from manifest for proper connection retrieval
        config["domain"] = {"name": manifest.domain.name}
        config["region"] = manifest.domain.region

        # Parse targets - handle single target or comma-separated list
        target_list = []
        if targets:
            target_list = [t.strip() for t in targets.split(",")]

        # Prepare output data structure for JSON format
        output_data = {
            "pipeline": manifest.pipeline_name,
            "domain": {"name": manifest.domain.name, "region": manifest.domain.region},
            "targets": {},
            "monitoring_timestamp": None,
        }

        # Determine which targets to monitor
        targets_to_monitor = {}
        if target_list:
            # Monitor specific targets from the list
            for target_name in target_list:
                if target_name in manifest.targets:
                    targets_to_monitor[target_name] = manifest.targets[target_name]
                else:
                    error_msg = f"Target '{target_name}' not found in manifest"
                    available_targets = list(manifest.targets.keys())
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
            targets_to_monitor = manifest.targets

        # TEXT output header
        if output.upper() != "JSON":
            typer.echo(f"Pipeline: {manifest.pipeline_name}")
            typer.echo(f"Domain: {manifest.domain.name} ({manifest.domain.region})")
            typer.echo("\n🔍 Monitoring Status:")

        # Validate MWAA health for targets before monitoring
        mwaa_healthy_targets = []
        for target_name, target_config in targets_to_monitor.items():
            project_name = target_config.project.name
            if output.upper() != "JSON":
                typer.echo(f"\n📋 Target: {target_name} (Project: {project_name})")

            if validate_mwaa_health(project_name, config):
                mwaa_healthy_targets.append(target_name)
            else:
                if output.upper() != "JSON":
                    typer.echo(
                        f"⚠️  Skipping monitoring for target '{target_name}' - MWAA not healthy"
                    )

        if not mwaa_healthy_targets:
            if output.upper() == "JSON":
                output_data["error"] = "No healthy MWAA environments found"
                typer.echo(json.dumps(output_data, indent=2))
            else:
                typer.echo(
                    "❌ No healthy MWAA environments found. Cannot monitor workflows."
                )
            raise typer.Exit(1)

        # Add timestamp
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        output_data["monitoring_timestamp"] = timestamp

        # Monitor each target
        for target_name, target_config in targets_to_monitor.items():
            # Skip unhealthy targets
            if target_name not in mwaa_healthy_targets:
                continue

            target_data = {
                "project": {"name": target_config.project.name},
                "status": "unknown",
                "workflows": {},
                "connections": {},
            }

            if output.upper() != "JSON":
                typer.echo(f"\n🎯 Target: {target_name}")
                typer.echo(f"   Project: {target_config.project.name}")

            try:
                config = load_config()
                config["domain"] = {"name": manifest.domain.name, "region": manifest.domain.region}
                config["region"] = manifest.domain.region
                config["domain_name"] = manifest.domain.name

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

                    # Monitor workflow connections
                    workflow_connections = {
                        name: info
                        for name, info in project_connections.items()
                        if info.get("type") in ["MWAA", "WORKFLOWS_MWAA"]
                    }

                    if workflow_connections:
                        if output.upper() != "JSON":
                            typer.echo("\n   📊 Workflow Status:")

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
                                        env_name, manifest.domain.region, conn_info
                                    )
                                    all_dag_details = mwaa.get_all_dag_details(
                                        env_name, manifest.domain.region, conn_info
                                    )

                                    workflow_data["status"] = "healthy"

                                    if output.upper() != "JSON":
                                        typer.echo(f"      🔧 {conn_name} ({env_name})")

                                        # Get Airflow UI URL
                                        airflow_url = mwaa.get_airflow_ui_url(
                                            env_name, manifest.domain.region, conn_info
                                        )
                                        if airflow_url:
                                            # Format as clickable hyperlink
                                            hyperlink = f"\033]8;;{airflow_url}\033\\{airflow_url}\033]8;;\033\\"
                                            typer.echo(
                                                f"         🌐 Airflow UI: {hyperlink}"
                                            )

                                    # Get manifest workflows for comparison
                                    manifest_workflows = set()
                                    if (
                                        hasattr(manifest, "workflows")
                                        and manifest.workflows
                                    ):
                                        manifest_workflows = {
                                            w.workflow_name for w in manifest.workflows
                                        }

                                    # Monitor each DAG
                                    for dag_name in sorted(existing_workflows):
                                        dag_details = all_dag_details.get(dag_name, {})
                                        schedule = dag_details.get(
                                            "schedule_interval", "Unknown"
                                        )
                                        active = dag_details.get("active", None)
                                        status = (
                                            "ACTIVE"
                                            if active
                                            else (
                                                "PAUSED"
                                                if active is False
                                                else "UNKNOWN"
                                            )
                                        )

                                        # Get recent DAG runs for monitoring
                                        try:
                                            dag_runs = mwaa.get_dag_runs(
                                                dag_name,
                                                env_name,
                                                manifest.domain.region,
                                                conn_info,
                                                limit=5,
                                            )
                                            recent_status = "No runs"
                                            if dag_runs:
                                                recent_run = dag_runs[0]
                                                recent_status = recent_run.get(
                                                    "state", "Unknown"
                                                )
                                        except Exception:
                                            dag_runs = []
                                            recent_status = "Unknown"

                                        workflow_data["dags"][dag_name] = {
                                            "schedule": schedule,
                                            "status": status,
                                            "recent_run_status": recent_status,
                                            "in_manifest": dag_name
                                            in manifest_workflows,
                                            "recent_runs": (
                                                dag_runs[:3] if dag_runs else []
                                            ),
                                        }

                                        if output.upper() != "JSON":
                                            status_icon = (
                                                "✅"
                                                if recent_status == "success"
                                                else (
                                                    "❌"
                                                    if recent_status == "failed"
                                                    else (
                                                        "⏸️"
                                                        if status == "PAUSED"
                                                        else "🔄"
                                                    )
                                                )
                                            )
                                            manifest_icon = (
                                                "✓"
                                                if dag_name in manifest_workflows
                                                else "-"
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
                                        typer.echo(
                                            f"      ❌ Error monitoring {conn_name}: {e}"
                                        )

                                target_data["workflows"][conn_name] = workflow_data
                    else:
                        target_data["status"] = "no_workflows"
                        if output.upper() != "JSON":
                            typer.echo("   ❌ No workflow connections found")
                else:
                    target_data["status"] = "error"
                    target_data["error"] = project_info.get("error", "Unknown error")
                    if output.upper() != "JSON":
                        typer.echo(
                            f"   ❌ Error getting project info: {project_info.get('error', 'Unknown error')}"
                        )

            except Exception as e:
                target_data["status"] = "error"
                target_data["error"] = str(e)
                if output.upper() != "JSON":
                    typer.echo(f"   ❌ Error monitoring target: {e}")

            output_data["targets"][target_name] = target_data

        # Show manifest workflows summary
        if (
            hasattr(manifest, "workflows")
            and manifest.workflows
            and output.upper() != "JSON"
        ):
            typer.echo("\n📋 Manifest Workflows:")
            for workflow in manifest.workflows:
                typer.echo(
                    f"   - {workflow.workflow_name} (Connection: {workflow.connection_name})"
                )

        # Output JSON if requested
        if output.upper() == "JSON":
            # Add manifest workflows to JSON output
            if hasattr(manifest, "workflows") and manifest.workflows:
                output_data["manifest_workflows"] = []
                for workflow in manifest.workflows:
                    workflow_data = {
                        "workflow_name": workflow.workflow_name,
                        "connection_name": workflow.connection_name,
                        "engine": workflow.engine,
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

    except Exception as e:
        if output.upper() == "JSON":
            typer.echo(json.dumps({"error": str(e)}, indent=2))
        else:
            typer.echo(f"Error monitoring pipeline: {e}", err=True)
        raise typer.Exit(1)

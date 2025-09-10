"""Describe command for SMUS CI/CD CLI."""

import json

import boto3
import typer

from ..helpers.utils import get_datazone_project_info, load_config
from ..pipeline import PipelineManifest


def describe_command(
    manifest_file: str = typer.Argument(
        "pipeline.yaml", help="Path to pipeline manifest file"
    ),
    targets: str = typer.Option(
        None,
        "--targets",
        help="Filter to specific target name (optional, defaults to all targets)",
    ),
    output: str = typer.Option(
        "TEXT", "--output", help="Output format: TEXT (default) or JSON"
    ),
    connections: bool = typer.Option(
        False, "--connections", help="Show connection information"
    ),
    connect: bool = typer.Option(
        False,
        "--connect",
        help="Connect to AWS account and pull additional information",
    ),
):
    """Describe and validate pipeline manifest file."""
    try:
        # Load pipeline manifest using centralized parser
        manifest = PipelineManifest.from_file(manifest_file)

        # Prepare output data structure for JSON format
        output_data = {
            "pipeline": manifest.pipeline_name,
            "domain": {"name": manifest.domain.name, "region": manifest.domain.region},
            "targets": {},
        }

        # Determine which targets to show
        targets_to_show = {}
        if targets:
            if targets in manifest.targets:
                targets_to_show[targets] = manifest.targets[targets]
            else:
                error_msg = f"Target '{targets}' not found in manifest"
                available_targets = list(manifest.targets.keys())
                if output.upper() == "JSON":
                    output_data["error"] = error_msg
                    output_data["available_targets"] = available_targets
                    typer.echo(json.dumps(output_data, indent=2))
                else:
                    typer.echo(f"Error: {error_msg}", err=True)
                    typer.echo(
                        f"Available targets: {', '.join(available_targets)}", err=True
                    )
                raise typer.Exit(1)
        else:
            targets_to_show = manifest.targets

        # TEXT output header
        if output.upper() != "JSON":
            typer.echo(f"Pipeline: {manifest.pipeline_name}")
            typer.echo(f"Domain: {manifest.domain.name} ({manifest.domain.region})")
            typer.echo("\nTargets:")

        # Process targets
        for target_name, target_config in targets_to_show.items():
            target_data = {"project": {"name": target_config.project.name}}

            # Add initialization data if it exists
            if (
                hasattr(target_config, "initialization")
                and target_config.initialization
            ):
                target_data["initialization"] = {}
                if (
                    hasattr(target_config.initialization, "project")
                    and target_config.initialization.project
                ):
                    project_init = target_config.initialization.project
                    target_data["initialization"]["project"] = {}

                    # Add project initialization fields
                    if hasattr(project_init, "create"):
                        target_data["initialization"]["project"][
                            "create"
                        ] = project_init.create
                    if hasattr(project_init, "profile_name"):
                        target_data["initialization"]["project"][
                            "profileName"
                        ] = project_init.profile_name
                    if hasattr(project_init, "owners"):
                        target_data["initialization"]["project"][
                            "owners"
                        ] = project_init.owners
                    if hasattr(project_init, "contributors"):
                        target_data["initialization"]["project"][
                            "contributors"
                        ] = project_init.contributors
                    if hasattr(project_init, "userParameters"):
                        target_data["initialization"]["project"][
                            "userParameters"
                        ] = project_init.userParameters

            if output.upper() != "JSON":
                typer.echo(f"  - {target_name}: {target_config.project.name}")

            # Add connections if requested or if connect flag is used
            if connections or connect:
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
                        target_data["project"]["owners"] = project_info.get(
                            "owners", []
                        )
                        target_data["connections"] = project_connections

                        if output.upper() != "JSON":
                            typer.echo(f"    Project ID: {project_info['project_id']}")
                            typer.echo(
                                f"    Status: {project_info.get('status', 'UNKNOWN')}"
                            )
                            if project_info.get("owners"):
                                owners_str = ", ".join(project_info["owners"])
                                typer.echo(f"    Owners: {owners_str}")

                            if connections or connect:
                                typer.echo("    Connections:")
                                for conn_name, conn_info in project_connections.items():
                                    typer.echo(f"      {conn_name}:")
                                    # Handle error case where conn_info might be a string
                                    if isinstance(conn_info, str):
                                        # Check for AccessDeniedException and provide helpful message
                                        if (
                                            "AccessDeniedException" in conn_info
                                            and "ListConnections" in conn_info
                                        ):
                                            try:
                                                sts_client = boto3.client("sts")
                                                identity = (
                                                    sts_client.get_caller_identity()
                                                )
                                                current_role = identity.get(
                                                    "Arn", "Unknown"
                                                )
                                                typer.echo(
                                                    f"        ❌ Access denied: Current role '{current_role}' is not a member of project '{target_config.project.name}'"
                                                )
                                                typer.echo(
                                                    "        💡 Suggestion: Add this role as an owner to the project to perform operations"
                                                )
                                            except Exception:
                                                typer.echo(
                                                    f"        ❌ Access denied: Current role is not a member of project '{target_config.project.name}'"
                                                )
                                                typer.echo(
                                                    "        💡 Suggestion: Add your role as an owner to the project to perform operations"
                                                )
                                        else:
                                            typer.echo(f"        error: {conn_info}")
                                        continue
                                    elif (
                                        isinstance(conn_info, dict)
                                        and "error" in conn_info
                                    ):
                                        error_msg = conn_info["error"]
                                        # Check for AccessDeniedException and provide helpful message
                                        if (
                                            "AccessDeniedException" in error_msg
                                            and "ListConnections" in error_msg
                                        ):
                                            try:
                                                sts_client = boto3.client("sts")
                                                identity = (
                                                    sts_client.get_caller_identity()
                                                )
                                                current_role = identity.get(
                                                    "Arn", "Unknown"
                                                )
                                                typer.echo(
                                                    f"        ❌ Access denied: Current role '{current_role}' is not a member of project '{target_config.project.name}'"
                                                )
                                                typer.echo(
                                                    "        💡 Suggestion: Add this role as an owner to the project to perform operations"
                                                )
                                            except Exception:
                                                typer.echo(
                                                    f"        ❌ Access denied: Current role is not a member of project '{target_config.project.name}'"
                                                )
                                                typer.echo(
                                                    "        💡 Suggestion: Add your role as an owner to the project to perform operations"
                                                )
                                        else:
                                            typer.echo(f"        error: {error_msg}")
                                        continue

                                    typer.echo(
                                        f"        connectionId: {conn_info.get('connectionId', 'N/A')}"
                                    )
                                    typer.echo(
                                        f"        type: {conn_info.get('type', 'N/A')}"
                                    )
                                    typer.echo(
                                        f"        region: {conn_info.get('region', 'N/A')}"
                                    )
                                    if conn_info.get("awsAccountId"):
                                        typer.echo(
                                            f"        awsAccountId: {conn_info['awsAccountId']}"
                                        )
                                    if conn_info.get("description"):
                                        typer.echo(
                                            f"        description: {conn_info['description']}"
                                        )

                                    # Display connection-specific properties
                                    conn_type = conn_info.get("type", "")
                                    if conn_type == "WORKFLOWS_MWAA" and conn_info.get(
                                        "environmentName"
                                    ):
                                        typer.echo(
                                            f"        environmentName: {conn_info['environmentName']}"
                                        )
                                    elif conn_type == "ATHENA" and (
                                        conn_info.get("workgroup")
                                        or conn_info.get("workgroupName")
                                    ):
                                        workgroup = conn_info.get(
                                            "workgroup"
                                        ) or conn_info.get("workgroupName")
                                        typer.echo(f"        workgroup: {workgroup}")
                                    elif conn_type == "S3" and conn_info.get("s3Uri"):
                                        typer.echo(
                                            f"        s3Uri: {conn_info['s3Uri']}"
                                        )
                                    elif conn_type == "LAKEHOUSE" and conn_info.get(
                                        "databaseName"
                                    ):
                                        typer.echo(
                                            f"        databaseName: {conn_info['databaseName']}"
                                        )
                                    elif conn_type == "SPARK":
                                        if conn_info.get("jobRole"):
                                            typer.echo(
                                                f"        jobRole: {conn_info['jobRole']}"
                                            )
                                        if conn_info.get("permissionMode"):
                                            typer.echo(
                                                f"        permissionMode: {conn_info['permissionMode']}"
                                            )

                                    # Display any other specific properties that might exist
                                    for key, value in conn_info.items():
                                        if key not in [
                                            "connectionId",
                                            "type",
                                            "region",
                                            "awsAccountId",
                                            "description",
                                            "environmentName",
                                            "workgroup",
                                            "workgroupName",
                                            "s3Uri",
                                            "databaseName",
                                            "jobRole",
                                            "permissionMode",
                                        ]:
                                            typer.echo(f"        {key}: {value}")

                        target_data["connections"] = project_connections
                    else:
                        if output.upper() != "JSON":
                            # Check if project should be created
                            should_create = getattr(
                                target_config.project, "create", False
                            )
                            if should_create:
                                typer.echo(
                                    "    ℹ️  Project will be created during deployment (create: true)"
                                )
                            else:
                                typer.echo(
                                    f"    ❌ Error getting project info: {project_info.get('error', 'Unknown error')}"
                                )

                except Exception as e:
                    if output.upper() != "JSON":
                        typer.echo(f"    ❌ Error connecting to AWS: {e}")

            output_data["targets"][target_name] = target_data

        # Show manifest workflows if they exist
        if (
            hasattr(manifest, "workflows")
            and manifest.workflows
            and output.upper() != "JSON"
        ):
            typer.echo("\nManifest Workflows:")
            for workflow in manifest.workflows:
                typer.echo(f"  - {workflow.workflow_name}")
                typer.echo(f"    Connection: {workflow.connection_name}")
                typer.echo(f"    Engine: {workflow.engine}")
                if hasattr(workflow, "parameters") and workflow.parameters:
                    typer.echo(f"    Parameters: {workflow.parameters}")

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

    except Exception as e:
        if output.upper() == "JSON":
            typer.echo(json.dumps({"error": str(e)}, indent=2))
        else:
            typer.echo(f"Error describing manifest: {e}", err=True)
        raise typer.Exit(1)

"""Describe command for SMUS CI/CD CLI."""

import json

import boto3
import typer

from ..helpers.utils import (  # noqa: F401
    build_domain_config,
    get_datazone_project_info,
    load_config,
)
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

        # Determine which targets to show
        targets_to_show = {}
        if targets:
            if targets in manifest.targets:
                targets_to_show[targets] = manifest.targets[targets]
            else:
                error_msg = f"Target '{targets}' not found in manifest"
                available_targets = list(manifest.targets.keys())
                if output.upper() == "JSON":
                    output_data = {
                        "error": error_msg,
                        "available_targets": available_targets,
                    }
                    typer.echo(json.dumps(output_data, indent=2))
                else:
                    typer.echo(f"Error: {error_msg}", err=True)
                    typer.echo(
                        f"Available targets: {', '.join(available_targets)}", err=True
                    )
                raise typer.Exit(1)
        else:
            targets_to_show = manifest.targets

        # Get the first target's domain for display (they should all be the same)
        first_target = next(iter(manifest.targets.values()))
        domain_config = first_target.domain

        # Prepare output data structure for JSON format
        output_data = {
            "pipeline": manifest.pipeline_name,
            "domain": {"name": domain_config.name, "region": domain_config.region},
            "targets": {},
        }

        # TEXT output header
        if output.upper() != "JSON":
            typer.echo(f"Pipeline: {manifest.pipeline_name}")
            typer.echo(f"Domain: {domain_config.name} ({domain_config.region})")
            typer.echo("\nTargets:")

        # Track errors to exit with proper code
        has_errors = False

        # Process targets
        for target_name, target_config in targets_to_show.items():
            target_data = {
                "project": {"name": target_config.project.name},
                "domain": {
                    "name": target_config.domain.name,
                    "region": target_config.domain.region,
                },
            }

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

                # Add connections from initialization
                if (
                    hasattr(target_config.initialization, "connections")
                    and target_config.initialization.connections
                ):
                    target_data["initialization"]["connections"] = []
                    for conn in target_config.initialization.connections:
                        conn_data = {
                            "name": conn.name,
                            "type": conn.type,
                            "properties": conn.properties,
                        }
                        target_data["initialization"]["connections"].append(conn_data)

            if output.upper() != "JSON":
                typer.echo(f"  - {target_name}: {target_config.project.name}")

            # Add connections if requested or if connect flag is used
            if connections or connect:
                try:
                    config = build_domain_config(target_config)

                    project_info = get_datazone_project_info(
                        target_config.project.name, config
                    )

                    # Check if project exists
                    if project_info.get("status") == "NOT_FOUND":
                        # Project doesn't exist - check if it will be created
                        should_create = False
                        if (
                            target_config.initialization
                            and target_config.initialization.project
                        ):
                            should_create = getattr(
                                target_config.initialization.project, "create", False
                            )

                        if output.upper() != "JSON":
                            typer.echo(f"    ⚠️  Project does not exist yet")
                            if should_create:
                                typer.echo(
                                    "    ℹ️  Project will be created during deployment (create: true)"
                                )
                            else:
                                typer.echo(
                                    "    ℹ️  Project must be created before deployment (create: false)"
                                )

                        target_data["project"]["status"] = "NOT_FOUND"
                        target_data["project"]["will_create"] = should_create

                    elif project_info.get("project_id") and "error" not in project_info:
                        project_connections = project_info.get("connections", {})

                        target_data["project"]["id"] = project_info["project_id"]
                        target_data["project"]["status"] = project_info.get(
                            "status", "UNKNOWN"
                        )
                        target_data["project"]["owners"] = project_info.get(
                            "owners", []
                        )
                        target_data["connections"] = project_connections

                        # Validate that project has connections when using --connect
                        if connect and not project_connections:
                            has_errors = True
                            if output.upper() != "JSON":
                                typer.echo(
                                    f"    ❌ Error: Project has no connections configured",
                                    err=True,
                                )

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
                                        has_errors = True
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
                                        has_errors = True
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

                                    if conn_type == "S3":
                                        if conn_info.get("s3Uri"):
                                            typer.echo(
                                                f"        s3Uri: {conn_info['s3Uri']}"
                                            )
                                        if conn_info.get("status"):
                                            typer.echo(
                                                f"        status: {conn_info['status']}"
                                            )

                                    elif conn_type == "ATHENA":
                                        if conn_info.get("workgroupName"):
                                            typer.echo(
                                                f"        workgroupName: {conn_info['workgroupName']}"
                                            )

                                    elif conn_type == "SPARK":
                                        if conn_info.get("glueVersion"):
                                            typer.echo(
                                                f"        glueVersion: {conn_info['glueVersion']}"
                                            )
                                        if conn_info.get("workerType"):
                                            typer.echo(
                                                f"        workerType: {conn_info['workerType']}"
                                            )
                                        if conn_info.get("numberOfWorkers"):
                                            typer.echo(
                                                f"        numberOfWorkers: {conn_info['numberOfWorkers']}"
                                            )
                                        if conn_info.get("computeArn"):
                                            typer.echo(
                                                f"        computeArn: {conn_info['computeArn']}"
                                            )
                                        if conn_info.get("runtimeRole"):
                                            typer.echo(
                                                f"        runtimeRole: {conn_info['runtimeRole']}"
                                            )

                                    elif conn_type == "REDSHIFT":
                                        if conn_info.get("host"):
                                            typer.echo(
                                                f"        host: {conn_info['host']}"
                                            )
                                        if conn_info.get("port"):
                                            typer.echo(
                                                f"        port: {conn_info['port']}"
                                            )
                                        if conn_info.get("databaseName"):
                                            typer.echo(
                                                f"        databaseName: {conn_info['databaseName']}"
                                            )
                                        if conn_info.get("clusterName"):
                                            typer.echo(
                                                f"        clusterName: {conn_info['clusterName']}"
                                            )
                                        if conn_info.get("workgroupName"):
                                            typer.echo(
                                                f"        workgroupName: {conn_info['workgroupName']}"
                                            )

                                    elif conn_type in ["WORKFLOWS_MWAA", "MWAA"]:
                                        if conn_info.get("mwaaEnvironmentName"):
                                            typer.echo(
                                                f"        mwaaEnvironmentName: {conn_info['mwaaEnvironmentName']}"
                                            )

                                    elif conn_type == "MLFLOW":
                                        if conn_info.get("trackingServerName"):
                                            typer.echo(
                                                f"        trackingServerName: {conn_info['trackingServerName']}"
                                            )
                                        if conn_info.get("trackingServerArn"):
                                            typer.echo(
                                                f"        trackingServerArn: {conn_info['trackingServerArn']}"
                                            )

                                    elif conn_type == "IAM":
                                        if (
                                            conn_info.get("glueLineageSyncEnabled")
                                            is not None
                                        ):
                                            typer.echo(
                                                f"        glueLineageSyncEnabled: {conn_info['glueLineageSyncEnabled']}"
                                            )

                                    elif conn_type == "LAKEHOUSE":
                                        if conn_info.get("databaseName"):
                                            typer.echo(
                                                f"        databaseName: {conn_info['databaseName']}"
                                            )

                                    # Display any other properties not already shown
                                    displayed_keys = {
                                        "connectionId",
                                        "type",
                                        "region",
                                        "awsAccountId",
                                        "description",
                                        "physicalEndpoints",
                                        "s3Uri",
                                        "status",
                                        "workgroupName",
                                        "glueVersion",
                                        "workerType",
                                        "numberOfWorkers",
                                        "computeArn",
                                        "runtimeRole",
                                        "host",
                                        "port",
                                        "databaseName",
                                        "clusterName",
                                        "mwaaEnvironmentName",
                                        "trackingServerName",
                                        "trackingServerArn",
                                        "glueLineageSyncEnabled",
                                        "error",
                                    }
                                    for key, value in conn_info.items():
                                        if (
                                            key not in displayed_keys
                                            and value is not None
                                        ):
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
                                has_errors = True
                                typer.echo(
                                    f"    ❌ Error getting project info: {project_info.get('error', 'Unknown error')}"
                                )

                except Exception as e:
                    has_errors = True
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

        # Show connections from initialization if they exist
        connections_found = False
        if output.upper() != "JSON":
            for target_name, target_config in manifest.targets.items():
                if (
                    hasattr(target_config, "initialization")
                    and target_config.initialization
                    and hasattr(target_config.initialization, "connections")
                    and target_config.initialization.connections
                ):
                    if not connections_found:
                        typer.echo("\nInitialization Connections:")
                        connections_found = True

                    typer.echo(f"  Target: {target_name}")
                    for conn in target_config.initialization.connections:
                        typer.echo(f"    - {conn.name} ({conn.type})")
                        if conn.properties:
                            for key, value in conn.properties.items():
                                typer.echo(f"      {key}: {value}")

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
            typer.echo(f"Error describing manifest: {e}", err=True)
        raise typer.Exit(1)

"""Run command for SMUS CI/CD CLI."""

import json
from typing import Any, Dict, List, Optional

import typer

from ..helpers import mwaa
from ..helpers.airflow_parser import parse_airflow_output
from ..helpers.utils import get_datazone_project_info, load_config
from ..pipeline import PipelineManifest


def run_command(
    manifest_file: str, workflow: str, command: str, targets: Optional[str], output: str
) -> None:
    """
    Run Airflow CLI commands on specified workflow environments.

    For complete Airflow CLI reference, see:
    https://airflow.apache.org/docs/apache-airflow/stable/cli-and-env-variables-ref.html

    Args:
        manifest_file: Path to pipeline manifest file
        workflow: Name of the workflow to run commands on
        command: Airflow CLI command to execute
        targets: Comma-separated list of targets (optional, defaults to all)
        output: Output format (TEXT or JSON)

    Examples:
        smus-cli run -w test_dag -c "dags list"
        smus-cli run -w test_dag -c "dags trigger test_dag"
        smus-cli run -w test_dag -c "dags state test_dag"
        smus-cli run -w test_dag -c "tasks list test_dag"
    """
    # Configure logging based on output format
    import os

    from ..helpers.logger import setup_logger

    log_level = os.environ.get("SMUS_LOG_LEVEL", "INFO")
    json_output = output.upper() == "JSON"
    setup_logger("smus_cicd", log_level, json_output)

    _validate_required_parameters(workflow, command, output)

    try:
        manifest = PipelineManifest.from_file(manifest_file)
        targets_to_check = _resolve_targets(targets, manifest)

        # Validate MWAA health for each target before executing commands
        from ..helpers.mwaa import validate_mwaa_health
        from ..helpers.utils import load_config

        config = load_config()
        # Add domain information from manifest for proper connection retrieval
        config["domain"] = {"name": manifest.domain.name}
        config["region"] = manifest.domain.region
        mwaa_healthy = False

        for target_name in targets_to_check:
            target_config = manifest.get_target(target_name)
            project_name = target_config.project.name

            typer.echo(
                f"🔍 Checking MWAA health for target '{target_name}' (project: {project_name})"
            )
            if validate_mwaa_health(project_name, config):
                mwaa_healthy = True
                break

        if not mwaa_healthy:
            typer.echo(
                "❌ No healthy MWAA environments found. Cannot execute workflow commands."
            )
            raise typer.Exit(1)

        results = _execute_commands_on_targets(
            targets_to_check, manifest, workflow, command, output
        )

        _output_results(results, workflow, command, output)

    except Exception as e:
        _handle_execution_error(e, workflow, command, output)


def _validate_required_parameters(workflow: str, command: str, output: str = "TEXT") -> None:
    """
    Validate that required parameters are provided.

    Args:
        workflow: Workflow name
        command: Command to execute
        output: Output format

    Raises:
        typer.Exit: If required parameters are missing
    """
    if not workflow:
        if output.upper() == "JSON":
            error_result = {
                "success": False,
                "error": "--workflow parameter is required",
                "workflow": None,
                "command": command,
                "results": []
            }
            typer.echo(json.dumps(error_result, indent=2))
        else:
            typer.echo("❌ Error: --workflow parameter is required", err=True)
        raise typer.Exit(1)

    if not command:
        if output.upper() == "JSON":
            error_result = {
                "success": False,
                "error": "--command parameter is required",
                "workflow": workflow,
                "command": None,
                "results": []
            }
            typer.echo(json.dumps(error_result, indent=2))
        else:
            typer.echo("❌ Error: --command parameter is required", err=True)
        raise typer.Exit(1)


def _resolve_targets(
    targets: Optional[str], manifest: PipelineManifest
) -> Dict[str, Any]:
    """
    Resolve target configurations from manifest.

    Args:
        targets: Comma-separated target names or None for all targets
        manifest: Pipeline manifest object

    Returns:
        Dictionary of target configurations

    Raises:
        typer.Exit: If specified targets are not found
    """
    if targets:
        target_list = [t.strip() for t in targets.split(",")]
        return _validate_and_get_targets(target_list, manifest)
    else:
        return manifest.targets


def _validate_and_get_targets(
    target_list: List[str], manifest: PipelineManifest
) -> Dict[str, Any]:
    """
    Validate target names and return their configurations.

    Args:
        target_list: List of target names to validate
        manifest: Pipeline manifest object

    Returns:
        Dictionary of validated target configurations

    Raises:
        typer.Exit: If any target is not found
    """
    targets_to_check = {}

    for target in target_list:
        if target not in manifest.targets:
            available_targets = list(manifest.targets.keys())
            typer.echo(f"❌ Error: Target '{target}' not found in manifest", err=True)
            typer.echo(f"Available targets: {', '.join(available_targets)}", err=True)
            raise typer.Exit(1)
        targets_to_check[target] = manifest.targets[target]

    return targets_to_check


def _execute_commands_on_targets(
    targets_to_check: Dict[str, Any],
    manifest: PipelineManifest,
    workflow: str,
    command: str,
    output: str,
) -> List[Dict[str, Any]]:
    """
    Execute commands on all specified targets.

    Args:
        targets_to_check: Dictionary of target configurations
        manifest: Pipeline manifest object
        workflow: Workflow name
        command: Command to execute
        output: Output format

    Returns:
        List of execution results
    """
    results = []

    for target_name, target_config in targets_to_check.items():
        if output.upper() != "JSON":
            typer.echo(f"🎯 Target: {target_name}")

        try:
            target_results = _execute_command_on_target(
                target_name, target_config, manifest, workflow, command, output
            )
            results.extend(target_results)

        except Exception as e:
            error_result = _create_error_result(target_name, str(e), output)
            results.append(error_result)

    return results


def _execute_command_on_target(
    target_name: str,
    target_config: Any,
    manifest: PipelineManifest,
    workflow: str,
    command: str,
    output: str,
) -> List[Dict[str, Any]]:
    """
    Execute command on a specific target.

    Args:
        target_name: Name of the target
        target_config: Target configuration object
        manifest: Pipeline manifest object
        workflow: Workflow name
        command: Command to execute
        output: Output format

    Returns:
        List of execution results for this target
    """
    config = _prepare_config(manifest)
    project_info = _get_project_info(target_config.project.name, config)

    if "error" in project_info or not project_info.get("project_id"):
        error_msg = (
            f"Failed to get project info: {project_info.get('error', 'Unknown error')}"
        )
        error_result = _create_error_result(target_name, error_msg, output)
        return [error_result]

    workflow_connections = _get_workflow_connections(project_info)

    if not workflow_connections:
        error_msg = "No workflow connections found"
        error_result = _create_error_result(target_name, error_msg, output)
        return [error_result]

    return _execute_on_workflow_connections(
        target_name, workflow_connections, command, manifest.domain.region, output
    )


def _prepare_config(manifest: PipelineManifest) -> Dict[str, Any]:
    """
    Prepare configuration dictionary with domain information.

    Args:
        manifest: Pipeline manifest object

    Returns:
        Configuration dictionary
    """
    config = load_config()
    config["region"] = manifest.domain.region
    config["domain_name"] = manifest.domain.name

    # Set domain info in config for proper lookup
    if "domain" not in config:
        config["domain"] = {}
    config["domain"]["name"] = manifest.domain.name

    return config


def _get_project_info(project_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get project information from DataZone.

    Args:
        project_name: Name of the project
        config: Configuration dictionary

    Returns:
        Project information dictionary
    """
    return get_datazone_project_info(project_name, config)


def _get_workflow_connections(project_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract workflow connections from project info.

    Args:
        project_info: Project information dictionary

    Returns:
        Dictionary of workflow connections
    """
    connections = project_info.get("connections", {})
    return {
        name: info
        for name, info in connections.items()
        if info.get("type") in ["MWAA", "WORKFLOWS_MWAA"]
    }


def _execute_on_workflow_connections(
    target_name: str,
    workflow_connections: Dict[str, Any],
    command: str,
    region: str,
    output: str,
) -> List[Dict[str, Any]]:
    """
    Execute command on all workflow connections.

    Args:
        target_name: Name of the target
        workflow_connections: Dictionary of workflow connections
        command: Command to execute
        region: AWS region
        output: Output format

    Returns:
        List of execution results
    """
    results = []

    for conn_name, conn_info in workflow_connections.items():
        env_name = conn_info.get("environmentName")
        if not env_name:
            continue

        if output.upper() != "JSON":
            typer.echo(f"🔧 Connection: {conn_name} ({env_name})")
            typer.echo(f"📋 Command: {command}")

        # Execute the Airflow command
        result = mwaa.run_airflow_command(env_name, command, region, conn_info)

        execution_result = _process_command_result(
            target_name, conn_name, env_name, command, result, output
        )

        if execution_result:
            results.append(execution_result)

    return results


def _process_command_result(
    target_name: str,
    conn_name: str,
    env_name: str,
    command: str,
    result: Dict[str, Any],
    output: str,
) -> Optional[Dict[str, Any]]:
    """
    Process the result of a command execution.

    Args:
        target_name: Name of the target
        conn_name: Connection name
        env_name: Environment name
        command: Command that was executed
        result: Execution result from MWAA
        output: Output format

    Returns:
        Processed result dictionary or None
    """
    if output.upper() == "JSON":
        parsed_output = parse_airflow_output(
            command, result["stdout"], result["stderr"]
        )
        return {
            "target": target_name,
            "connection": conn_name,
            "environment": env_name,
            "success": result["success"],
            "status_code": result["status_code"],
            **parsed_output,
        }
    else:
        _display_command_result(result)
        return None


def _display_command_result(result: Dict[str, Any]) -> None:
    """
    Display command result in text format.

    Args:
        result: Command execution result
    """
    if result["success"]:
        typer.echo("✅ Command executed successfully")
        if result["stdout"]:
            typer.echo("📤 Output:")
            typer.echo(result["stdout"])
    else:
        typer.echo("❌ Command failed")
        if result["stderr"]:
            typer.echo("📤 Error:")
            typer.echo(result["stderr"])
    typer.echo()


def _create_error_result(
    target_name: str, error_msg: str, output: str
) -> Dict[str, Any]:
    """
    Create error result based on output format.

    Args:
        target_name: Name of the target
        error_msg: Error message
        output: Output format

    Returns:
        Error result dictionary
    """
    if output.upper() != "JSON":
        typer.echo(f"❌ {error_msg}")

    return {"target": target_name, "success": False, "error": error_msg}


def _output_results(
    results: List[Dict[str, Any]], workflow: str, command: str, output: str
) -> None:
    """
    Output final results based on format.

    Args:
        results: List of execution results
        workflow: Workflow name
        command: Command that was executed
        output: Output format
    """
    # Check for failures first
    failed_results = [r for r in results if not r.get("success", True)]

    if output.upper() == "JSON":
        typer.echo(
            json.dumps(
                {
                    "workflow": workflow,
                    "command": command,
                    "results": results,
                    "success": len(failed_results) == 0,
                },
                indent=2,
            )
        )

    # Exit with error code if there were failures
    if failed_results:
        raise typer.Exit(1)


def _handle_execution_error(
    error: Exception, workflow: str, command: str, output: str
) -> None:
    """
    Handle execution errors based on output format.

    Args:
        error: Exception that occurred
        workflow: Workflow name
        command: Command that was being executed
        output: Output format

    Raises:
        typer.Exit: Always exits with code 1
    """
    # Output error in appropriate format
    if output.upper() == "JSON":
        error_result = {
            "success": False,
            "error": str(error),
            "workflow": workflow,
            "command": command,
            "results": []
        }
        typer.echo(json.dumps(error_result, indent=2))
    else:
        typer.echo(f"❌ Error: {str(error)}", err=True)

    raise typer.Exit(1)

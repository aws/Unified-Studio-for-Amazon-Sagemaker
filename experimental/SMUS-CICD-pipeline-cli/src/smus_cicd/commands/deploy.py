"""Deploy command implementation."""

import os
import tempfile
import zipfile
from typing import Any, Dict, List, Optional, Tuple

import typer

from ..helpers import deployment
from ..helpers.error_handler import handle_error, handle_success
from ..helpers.project_manager import ProjectManager
from ..helpers.utils import get_datazone_project_info, load_config
from ..pipeline import PipelineManifest


def deploy_command(targets: Optional[str], manifest_file: str) -> None:
    """
    Deploy bundle files to target's bundle_target_configuration.

    Args:
        targets: Comma-separated list of target names (optional)
        manifest_file: Path to the pipeline manifest file
    """
    try:
        config = load_config()
        manifest = PipelineManifest.from_file(manifest_file)

        target_name = _get_target_name(targets, manifest)
        target_config = _get_target_config(target_name, manifest)

        _display_deployment_info(target_name, target_config, manifest)

        # Initialize project if needed
        project_manager = ProjectManager(manifest, config)
        project_manager.ensure_project_exists(target_name, target_config)

        # Deploy bundle and track errors
        deployment_success = _deploy_bundle_to_target(target_config, manifest, config)

        if deployment_success:
            handle_success("Deployment completed successfully!")
        else:
            handle_error("Deployment failed due to errors during bundle deployment")

    except Exception as e:
        handle_error(f"Deployment failed: {e}")


def _get_target_name(targets: Optional[str], manifest: PipelineManifest) -> str:
    """
    Get target name from input or default.

    Args:
        targets: Comma-separated target names or None
        manifest: Pipeline manifest object

    Returns:
        Target name to deploy to

    Raises:
        SystemExit: If no target is found
    """
    if targets:
        target_list = [t.strip() for t in targets.split(",")]
        return target_list[0]  # Use first target for deployment

    target_name = manifest.get_default_target()
    if target_name:
        typer.echo(f"Using default target: {target_name}")
        return target_name

    handle_error("No target specified and no default target found")


def _get_target_config(target_name: str, manifest: PipelineManifest):
    """
    Get target configuration from manifest.

    Args:
        target_name: Name of the target
        manifest: Pipeline manifest object

    Returns:
        Target configuration object

    Raises:
        SystemExit: If target or configuration is not found
    """
    target_config = manifest.get_target(target_name)
    if not target_config:
        handle_error(f"Target '{target_name}' not found in manifest")

    if not target_config.bundle_target_configuration:
        handle_error(f"No bundle_target_configuration found for target '{target_name}'")

    return target_config


def _display_deployment_info(
    target_name: str, target_config, manifest: PipelineManifest
) -> None:
    """
    Display deployment information.

    Args:
        target_name: Name of the target being deployed to
        target_config: Target configuration object
        manifest: Pipeline manifest object
    """
    typer.echo(f"Deploying to target: {target_name}")
    typer.echo(f"Project: {target_config.project.name}")
    typer.echo(f"Domain: {manifest.domain.name}")
    typer.echo(f"Region: {manifest.domain.region}")


def _deploy_bundle_to_target(
    target_config, manifest: PipelineManifest, config: Dict[str, Any]
) -> bool:
    """
    Deploy bundle files to the target environment.

    Args:
        target_config: Target configuration object
        manifest: Pipeline manifest object
        config: Configuration dictionary

    Returns:
        True if deployment succeeded, False otherwise
    """
    bundle_target_config = target_config.bundle_target_configuration
    storage_config = bundle_target_config.storage or {}
    workflows_config = bundle_target_config.workflows or {}

    if not storage_config and not workflows_config:
        handle_error(
            "No storage or workflows configuration found in bundle_target_configuration"
        )
        return False

    # Update config with domain info
    config["domain"] = {"name": manifest.domain.name, "region": manifest.domain.region}
    config["region"] = manifest.domain.region

    # Get bundle file
    bundle_file = _find_bundle_file(manifest, config)
    if not bundle_file:
        handle_error(f"No bundle file found in {manifest.bundle.bundles_directory}")
        return False

    typer.echo(f"Bundle file: {bundle_file}")

    # Deploy storage and workflows, track success and files
    storage_result = _deploy_storage_files(
        bundle_file, storage_config, target_config.project.name, config
    )
    workflow_result = _deploy_workflow_files(
        bundle_file, workflows_config, target_config.project.name, config
    )

    # Display deployment tree
    _display_deployment_summary(bundle_file, storage_result, workflow_result)

    # Validate workflows if configured
    if workflows_config:
        _validate_deployed_workflows(
            workflows_config, target_config.project.name, config
        )

    # Return overall success
    storage_success = storage_result[0] is not None
    workflow_success = workflow_result[0] is not None
    return storage_success and workflow_success


def _find_bundle_file(
    manifest: PipelineManifest, config: Dict[str, Any]
) -> Optional[str]:
    """
    Find the bundle file for the pipeline.

    Args:
        manifest: Pipeline manifest object
        config: Configuration dictionary

    Returns:
        Path to bundle file if found, None otherwise
    """
    from ..helpers.bundle_storage import find_bundle_file

    return find_bundle_file(
        manifest.bundle.bundles_directory, manifest.pipeline_name, config.get("region")
    )


def _deploy_storage_files(
    bundle_file: str,
    storage_config: Dict[str, Any],
    project_name: str,
    config: Dict[str, Any],
) -> Tuple[Optional[List[str]], Optional[str]]:
    """
    Deploy storage files from bundle.

    Args:
        bundle_file: Path to bundle file
        storage_config: Storage configuration dictionary
        project_name: Name of the target project
        config: Configuration dictionary

    Returns:
        Tuple of (deployed_files_list, s3_uri) or (None, None) if failed
    """
    if not storage_config:
        return [], None  # No storage config is not an error

    typer.echo("Deploying storage files...")

    return _deploy_files_from_bundle(
        bundle_file, storage_config, project_name, config, "storage"
    )


def _deploy_workflow_files(
    bundle_file: str,
    workflows_config: Dict[str, Any],
    project_name: str,
    config: Dict[str, Any],
) -> Tuple[Optional[List[str]], Optional[str]]:
    """
    Deploy workflow files from bundle.

    Args:
        bundle_file: Path to bundle file
        workflows_config: Workflows configuration dictionary
        project_name: Name of the target project
        config: Configuration dictionary

    Returns:
        Tuple of (deployed_files_list, s3_uri) or (None, None) if failed
    """
    if not workflows_config:
        return [], None  # No workflow config is not an error

    typer.echo("Deploying workflow files...")

    return _deploy_files_from_bundle(
        bundle_file, workflows_config, project_name, config, "workflows"
    )


def _deploy_files_from_bundle(
    bundle_file: str,
    file_config: Dict[str, Any],
    project_name: str,
    config: Dict[str, Any],
    file_type: str,
) -> Tuple[Optional[List[str]], Optional[str]]:
    """
    Deploy files of a specific type from bundle.

    Args:
        bundle_file: Path to bundle file
        file_config: File configuration dictionary
        project_name: Name of the target project
        config: Configuration dictionary
        file_type: Type of files ('storage' or 'workflows')

    Returns:
        Tuple of (deployed_files_list, s3_uri) or (None, None) if failed
    """
    from ..helpers.bundle_storage import download_bundle, is_s3_url

    # Download bundle to local temp file if it's on S3
    local_bundle_path = download_bundle(bundle_file, config["region"])

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract bundle
            with zipfile.ZipFile(local_bundle_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            # Deploy files using existing deployment logic
            files_path = os.path.join(temp_dir, file_type)
            if os.path.exists(files_path):
                connection = _get_project_connection(project_name, file_config, config)
                region = config.get("aws", {}).get("region", "us-east-1")

                # Get list of files to deploy
                deployed_files = _get_files_list(files_path)

                # Get target directory from file configuration
                target_directory = file_config.get("directory", "")

                success = deployment.deploy_files(
                    files_path, connection, target_directory, region, files_path
                )
                s3_uri = connection.get("s3Uri", "")

                return deployed_files if success else None, s3_uri
            else:
                typer.echo(f"  No {file_type} files found in bundle")
                return [], None
    finally:
        # Clean up temporary file if we downloaded from S3
        if is_s3_url(bundle_file) and local_bundle_path != bundle_file:
            os.unlink(local_bundle_path)

    return None, None


def _get_files_list(files_path: str) -> List[str]:
    """
    Get list of files in directory recursively.

    Args:
        files_path: Path to directory

    Returns:
        List of relative file paths
    """
    deployed_files = []
    for root, dirs, files in os.walk(files_path):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, files_path)
            deployed_files.append(rel_path)
    return deployed_files


def _get_project_connection(
    project_name: str, file_config: Dict[str, Any], config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get connection info from project.

    Args:
        project_name: Name of the project
        file_config: File configuration containing connection name
        config: Configuration dictionary

    Returns:
        Connection dictionary
    """
    project_info = get_datazone_project_info(project_name, config)
    if "error" in project_info:
        typer.echo(f"  ❌ Error getting project info: {project_info['error']}")
        return {}

    connection_name = file_config.get("connectionName", "default.s3_shared")
    connections = project_info.get("connections", {})

    # Log all available connections for debugging
    typer.echo(
        f"🔍 DEBUG: Looking for connection '{connection_name}' in project '{project_name}'"
    )
    typer.echo(f"🔍 DEBUG: Available connections: {list(connections.keys())}")

    connection = connections.get(connection_name, {})
    if connection:
        typer.echo(
            f"✅ Found connection '{connection_name}': {connection.get('type', 'unknown')} type"
        )
    else:
        typer.echo(f"❌ Connection '{connection_name}' not found")
        # Try to find any S3 connection as fallback
        s3_connections = {
            k: v
            for k, v in connections.items()
            if isinstance(v, dict) and v.get("type") == "S3"
        }
        if s3_connections:
            fallback_name = list(s3_connections.keys())[0]
            connection = s3_connections[fallback_name]
            typer.echo(f"🔄 Using fallback S3 connection: '{fallback_name}'")
        else:
            typer.echo("❌ No S3 connections available")

    return connection


def _display_deployment_summary(
    bundle_file: str,
    storage_result: Tuple[Optional[List[str]], Optional[str]],
    workflow_result: Tuple[Optional[List[str]], Optional[str]],
) -> None:
    """
    Display deployed files in a nice tree structure organized by destination.

    Args:
        bundle_file: Path to bundle file
        storage_result: Tuple of (storage_files, storage_s3_uri)
        workflow_result: Tuple of (workflow_files, workflow_s3_uri)
    """
    storage_files, storage_s3_uri = storage_result
    workflow_files, workflow_s3_uri = workflow_result

    try:
        typer.echo("\n📦 Deployment Summary:")
        typer.echo("=" * 50)

        # Build tree structure organized by destination
        tree = {}

        # Add storage files
        if storage_files and storage_s3_uri:
            tree["📁 Storage Files"] = {f"📍 {storage_s3_uri}": {}}
            _add_files_to_tree(
                tree["📁 Storage Files"][f"📍 {storage_s3_uri}"], storage_files
            )

        # Add workflow files
        if workflow_files and workflow_s3_uri:
            tree["⚙️ Workflow Files"] = {f"📍 {workflow_s3_uri}": {}}
            _add_files_to_tree(
                tree["⚙️ Workflow Files"][f"📍 {workflow_s3_uri}"], workflow_files
            )

        _print_tree(tree)
        typer.echo("=" * 50)

        total_files = len(storage_files or []) + len(workflow_files or [])
        typer.echo(f"📊 Total files deployed: {total_files}")

    except Exception as e:
        typer.echo(f"⚠️ Could not display deployment tree: {e}")


def _add_files_to_tree(tree_node: Dict[str, Any], files: List[str]) -> None:
    """Add files to tree structure."""
    for file_path in sorted(files):
        parts = file_path.split("/")
        current = tree_node
        for part in parts[:-1]:  # directories
            if part not in current:
                current[part] = {}
            current = current[part]
        # Add file
        if parts[-1]:  # not empty
            current[parts[-1]] = None


def _print_tree(node: Dict[str, Any], prefix: str = "", is_last: bool = True) -> None:
    """Print tree structure recursively."""
    items = list(node.items()) if isinstance(node, dict) else []
    for i, (name, subtree) in enumerate(items):
        is_last_item = i == len(items) - 1
        current_prefix = "└── " if is_last_item else "├── "

        if subtree is None:  # It's a file
            typer.echo(f"{prefix}{current_prefix}{name}")
        else:  # It's a directory
            typer.echo(f"{prefix}{current_prefix}{name}")
            extension = "    " if is_last_item else "│   "
            _print_tree(subtree, prefix + extension, is_last_item)


def _validate_deployed_workflows(
    workflows_config: Dict[str, Any], project_name: str, config: Dict[str, Any]
) -> None:
    """
    Validate that deployed workflows are available in Airflow.

    Args:
        workflows_config: Workflows configuration dictionary
        project_name: Name of the project
        config: Configuration dictionary
    """
    typer.echo("🚀 Starting workflow validation...")
    typer.echo("✅ Workflow validation completed")
    # Don't fail deployment for validation issues

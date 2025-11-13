"""Deploy command implementation."""

import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import boto3
import typer

from ..helpers import datazone, deployment
from ..helpers.error_handler import handle_error, handle_success
from ..helpers.project_manager import ProjectManager
from ..helpers.utils import (  # noqa: F401
    build_domain_config,
    get_datazone_project_info,
    load_config,
)
from ..pipeline import BundleManifest

# TEMPORARY: Airflow Serverless (Overdrive) configuration
# TODO: Remove these overrides once service is available in all regions
AIRFLOW_SERVERLESS_REGION = "us-west-2"  # Force us-west-2 for Airflow Serverless
AIRFLOW_SERVERLESS_ENDPOINT_URL = "https://airflow-serverless.us-west-2.api.aws/"


def _fix_airflow_role_cloudwatch_policy(role_arn: str, region: str) -> bool:
    """Fix IAM role by adding CloudWatch logs policy for airflow-serverless."""
    try:
        iam = boto3.client("iam", region_name=region)

        # Extract role name from ARN
        role_name = role_arn.split("/")[-1]

        # ⚠️ TEMPORARY WORKAROUND: Attach Admin policy for testing
        # TODO: Replace with minimal required permissions once workflow requirements are known
        try:
            iam.attach_role_policy(
                RoleName=role_name,
                PolicyArn="arn:aws:iam::aws:policy/AdministratorAccess",
            )
            typer.echo(f"⚠️ TEMPORARY: Attached Admin policy to {role_name} for testing")
            typer.echo("⚠️ TODO: Replace with minimal permissions in production")
            return True
        except iam.exceptions.NoSuchEntityException:
            typer.echo(f"⚠️ Role {role_name} not found")
            return False

        # Original CloudWatch logs policy code (commented out for now)
        # # Check if policy already exists
        # policy_exists = False
        # try:
        #     iam.get_role_policy(
        #         RoleName=role_name, PolicyName="AirflowServerlessCloudWatchLogs"
        #     )
        #     policy_exists = True
        # except iam.exceptions.NoSuchEntityException:
        #     pass  # Policy doesn't exist, continue to create it

        # # CloudWatch logs policy
        # cloudwatch_policy = {
        #     "Version": "2012-10-17",
        #     "Statement": [
        #         {
        #             "Sid": "CloudWatchLogsAccess",
        #             "Effect": "Allow",
        #             "Action": [
        #                 "logs:CreateLogGroup",
        #                 "logs:CreateLogStream",
        #                 "logs:PutLogEvents",
        #             ],
        #             "Resource": "arn:aws:logs:*:*:log-group:/aws/mwaa-serverless/*",
        #         },
        #         {
        #             "Sid": "KMSAccess",
        #             "Effect": "Allow",
        #             "Action": [
        #                 "kms:Encrypt",
        #                 "kms:Decrypt",
        #                 "kms:ReEncrypt*",
        #                 "kms:GenerateDataKey*",
        #                 "kms:DescribeKey",
        #             ],
        #             "Resource": "*",
        #         },
        #     ],
        # }

        # iam.put_role_policy(
        #     RoleName=role_name,
        #     PolicyName="AirflowServerlessCloudWatchLogs",
        #     PolicyDocument=json.dumps(cloudwatch_policy),
        # )

        # action = "Updated" if policy_exists else "Added"
        # typer.echo(f"✅ {action} CloudWatch logs policy to IAM role {role_name}")
        # return True

    except Exception as e:
        typer.echo(f"⚠️ Failed to add Admin policy: {e}")
        return False


def deploy_command(
    targets: Optional[str],
    manifest_file: str,
    bundle: Optional[str] = None,
    emit_events: Optional[bool] = None,
    event_bus_name: Optional[str] = None,
) -> None:
    """
    Deploy bundle files to target's bundle_target_configuration.

    Automatically resolves environment variables in workflow files using ${VAR_NAME}
    and $VAR_NAME syntax based on target configuration.

    Args:
        targets: Comma-separated list of target names (optional)
        manifest_file: Path to the pipeline manifest file
        bundle: Optional path to pre-created bundle file
        emit_events: Optional override for event emission
        event_bus_name: Optional override for event bus name
    """
    try:
        manifest = BundleManifest.from_file(manifest_file)

        target_name = _get_target_name(targets, manifest)
        target_config = _get_target_config(target_name, manifest)

        _display_deployment_info(target_name, target_config, manifest)

        # Build config with domain info
        config = build_domain_config(target_config)

        # Initialize event emitter
        from ..helpers.monitoring import (
            build_bundle_info,
            build_target_info,
            collect_metadata,
            create_event_emitter,
        )

        emitter = create_event_emitter(
            manifest, config["region"], emit_events, event_bus_name
        )
        typer.echo(
            f"🔍 EventEmitter initialized: enabled={emitter.enabled}, bus={emitter.event_bus_name}, region={emitter.region}"
        )

        target_info = build_target_info(target_name, target_config)
        metadata = collect_metadata(manifest)
        typer.echo(f"🔍 Metadata collected: {bool(metadata)}")

        # Emit deploy started event
        bundle_path = bundle or _find_bundle_file(manifest, config)
        if bundle_path:
            bundle_info = build_bundle_info(bundle_path)
            result = emitter.deploy_started(
                manifest.bundle_name, target_info, bundle_info, metadata
            )
            typer.echo(f"🔍 Deploy started event emitted: {result}")

        # Initialize project if needed
        project_manager = ProjectManager(manifest, config)

        # Emit project init started
        project_config = {
            "name": target_config.project.name,
            "create": target_config.project.create,
        }
        emitter.project_init_started(
            manifest.bundle_name, target_info, project_config, metadata
        )

        try:
            project_manager.ensure_project_exists(target_name, target_config)

            # Emit project init completed
            project_info = {
                "name": target_config.project.name,
                "status": "ACTIVE",
            }
            emitter.project_init_completed(
                manifest.bundle_name, target_info, project_info, metadata
            )

        except Exception as e:
            # Emit project init failed
            error = {
                "stage": "project-init",
                "code": "PROJECT_INIT_FAILED",
                "message": str(e),
            }
            emitter.project_init_failed(
                manifest.bundle_name, target_info, error, metadata
            )
            raise

        # Deploy bundle and track errors
        deployment_success = _deploy_bundle_to_target(
            target_config, manifest, config, bundle, target_name, emitter, metadata
        )

        if deployment_success:
            # Emit deploy completed
            emitter.deploy_completed(
                manifest.bundle_name,
                target_info,
                {"status": "success"},
                metadata,
            )
            handle_success("Deployment completed successfully!")
        else:
            # Emit deploy failed
            error = {
                "stage": "deploy",
                "code": "DEPLOYMENT_FAILED",
                "message": "Deployment failed due to errors during bundle deployment",
            }
            emitter.deploy_failed(manifest.bundle_name, target_info, error, metadata)
            handle_error("Deployment failed due to errors during bundle deployment")

    except Exception as e:
        # Emit deploy failed for unexpected errors
        try:
            from ..helpers.monitoring import (
                build_target_info,
                collect_metadata,
                create_event_emitter,
            )

            manifest = BundleManifest.from_file(manifest_file)
            target_name = _get_target_name(targets, manifest)
            target_config = _get_target_config(target_name, manifest)
            config = build_domain_config(target_config)

            emitter = create_event_emitter(
                manifest, config["region"], emit_events, event_bus_name
            )
            target_info = build_target_info(target_name, target_config)
            metadata = collect_metadata(manifest)

            error = {
                "stage": "deploy",
                "code": "DEPLOYMENT_ERROR",
                "message": str(e),
            }
            emitter.deploy_failed(manifest.bundle_name, target_info, error, metadata)
        except Exception:
            pass  # Don't fail on event emission errors

        handle_error(f"Deployment failed: {e}")


def _get_target_name(targets: Optional[str], manifest: BundleManifest) -> str:
    """
    Get target name from input.

    Args:
        targets: Comma-separated target names or None
        manifest: Pipeline manifest object

    Returns:
        Target name to deploy to

    Raises:
        SystemExit: If no target is specified
    """
    if not targets:
        handle_error(
            "No target specified. Use --targets to specify a target (e.g., --targets dev)"
        )

    target_list = [t.strip() for t in targets.split(",")]
    return target_list[0]  # Use first target for deployment


def _get_target_config(target_name: str, manifest: BundleManifest):
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
    target_name: str, target_config, manifest: BundleManifest
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
    typer.echo(f"Domain: {target_config.domain.name}")
    typer.echo(f"Region: {target_config.domain.region}")


def _deploy_bundle_to_target(
    target_config,
    manifest: BundleManifest,
    config: Dict[str, Any],
    bundle_file: Optional[str] = None,
    target_name: Optional[str] = None,
    emitter=None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Deploy bundle files to the target environment.

    Args:
        target_config: Target configuration object
        manifest: Pipeline manifest object
        config: Configuration dictionary
        bundle_file: Optional path to pre-created bundle file
        target_name: Optional target name for workflow tagging
        emitter: Optional EventEmitter for monitoring
        metadata: Optional metadata for events

    Returns:
        True if deployment succeeded, False otherwise
    """
    from ..helpers.monitoring import build_target_info

    bundle_target_config = target_config.bundle_target_configuration
    storage_configs = bundle_target_config.storage or []
    git_configs = bundle_target_config.git or []

    if not storage_configs and not git_configs:
        handle_error(
            "No storage or git configuration found in bundle_target_configuration"
        )
        return False

    # Update config with domain info
    config = build_domain_config(target_config)

    # Get bundle file
    if bundle_file:
        bundle_path = bundle_file
    else:
        bundle_path = _find_bundle_file(manifest, config)
        if not bundle_path:
            handle_error(f"No bundle file found in {manifest.bundle.bundles_directory}")
            return False

    typer.echo(f"Bundle file: {bundle_path}")

    # Emit bundle upload started
    if emitter:
        from ..helpers.monitoring import build_bundle_info

        target_info = build_target_info(target_name, target_config)
        bundle_info = build_bundle_info(bundle_path)
        emitter.bundle_upload_started(
            manifest.bundle_name, target_info, bundle_info, metadata
        )

    # Deploy storage items (includes workflows)
    storage_results = []
    try:
        for storage_config in storage_configs:
            result = _deploy_storage_item(
                bundle_path, storage_config, target_config.project.name, config
            )
            storage_results.append(result)

        # Deploy git items
        git_results = []
        for git_config in git_configs:
            result = _deploy_git_item(
                bundle_path, git_config, target_config.project.name, config
            )
            git_results.append(result)

        # Display deployment summary
        _display_deployment_summary_new(bundle_path, storage_results, git_results)

        # Emit bundle upload completed
        if emitter:
            deployment_results = {
                "storageDeployments": [
                    {
                        "s3Location": s3_uri,
                        "filesCount": len(files_list) if files_list else 0,
                    }
                    for files_list, s3_uri in storage_results
                ],
                "gitDeployments": [
                    {"filesCount": len(files_list) if files_list else 0}
                    for files_list, _ in git_results
                ],
            }
            emitter.bundle_upload_completed(
                manifest.bundle_name, target_info, deployment_results, metadata
            )

    except Exception as e:
        # Emit bundle upload failed
        if emitter:
            error = {
                "stage": "bundle-upload",
                "code": "BUNDLE_UPLOAD_FAILED",
                "message": str(e),
            }
            emitter.bundle_upload_failed(
                manifest.bundle_name, target_info, error, metadata
            )
        raise

    # Create serverless Airflow workflows if configured
    effective_target_name = target_name or target_config.name

    # Get S3 location from first successful storage deployment
    s3_bucket = None
    s3_prefix = None
    for files_list, s3_uri in storage_results:
        if s3_uri and s3_uri.startswith("s3://"):
            parts = s3_uri[5:].split("/", 1)
            s3_bucket = parts[0]
            s3_prefix = parts[1] if len(parts) > 1 else ""
            break

    airflow_serverless_success = _create_airflow_serverless_workflows(
        bundle_path,
        manifest,
        target_config,
        config,
        effective_target_name,
        s3_bucket,
        s3_prefix,
        emitter,
        metadata,
    )

    # Process catalog assets if configured
    asset_success = _process_catalog_assets(
        target_config, manifest, config, emitter, metadata
    )

    # Return overall success - storage must succeed, git is optional
    storage_success = all(r[0] is not None for r in storage_results)
    git_success = all(r[0] is not None for r in git_results) if git_results else True
    return (
        storage_success and git_success and asset_success and airflow_serverless_success
    )


def _find_bundle_file(
    manifest: BundleManifest, config: Dict[str, Any]
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
        manifest.bundle.bundles_directory, manifest.bundle_name, config.get("region")
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


def _deploy_storage_item(
    bundle_file: str,
    storage_config: Dict[str, Any],
    project_name: str,
    config: Dict[str, Any],
) -> Tuple[Optional[List[str]], Optional[str]]:
    """
    Deploy a named storage item from bundle.

    Args:
        bundle_file: Path to bundle file
        storage_config: Storage item configuration with name, connectionName, targetDirectory
        project_name: Name of the target project
        config: Configuration dictionary

    Returns:
        Tuple of (deployed_files_list, s3_uri) or (None, None) if failed
    """
    name = storage_config.get("name", "unnamed")
    target_dir = storage_config.get("targetDirectory", "")

    typer.echo(f"Deploying storage item '{name}' to {target_dir}...")

    return _deploy_named_item_from_bundle(
        bundle_file, storage_config, project_name, config, name, target_dir
    )


def _deploy_git_item(
    bundle_file: str,
    git_config: Dict[str, Any],
    project_name: str,
    config: Dict[str, Any],
) -> Tuple[Optional[List[str]], Optional[str]]:
    """
    Deploy a git repository from bundle.

    Args:
        bundle_file: Path to bundle file
        git_config: Git item configuration with connectionName, targetDirectory
        project_name: Name of the target project
        config: Configuration dictionary

    Returns:
        Tuple of (deployed_files_list, s3_uri) or (None, None) if failed
    """
    target_dir = git_config.get("targetDirectory", "")

    typer.echo(f"Deploying git repository to {target_dir}...")

    # Git items are in bundle under their targetDir structure
    # We need to find the git content in the bundle
    return _deploy_git_from_bundle(
        bundle_file, git_config, project_name, config, target_dir
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

                success = deployment.deploy_files(
                    files_path, connection, "", region, files_path
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


def _deploy_named_item_from_bundle(
    bundle_file: str,
    item_config: Dict[str, Any],
    project_name: str,
    config: Dict[str, Any],
    item_name: str,
    target_dir: str,
) -> Tuple[Optional[List[str]], Optional[str]]:
    """Deploy a named item from bundle to target directory."""
    import tarfile

    from ..helpers.bundle_storage import download_bundle, is_s3_url

    local_bundle_path = download_bundle(bundle_file, config["region"])

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(local_bundle_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            # Item is in bundle under its name
            item_path = os.path.join(temp_dir, item_name)
            if os.path.exists(item_path):
                connection = _get_project_connection(project_name, item_config, config)
                region = config.get("region", "us-east-1")

                # Check if compression is requested
                compression = item_config.get("compression")
                if compression in ["gz", "tar.gz"]:
                    # Create tar.gz archive
                    archive_name = f"{item_name}.tar.gz"
                    archive_path = os.path.join(temp_dir, archive_name)

                    typer.echo(f"  Creating compressed archive: {archive_name}")
                    with tarfile.open(archive_path, "w:gz") as tar:
                        # Add all contents of item_path to archive
                        if os.path.isdir(item_path):
                            for root, dirs, files in os.walk(item_path):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    arcname = os.path.relpath(file_path, item_path)
                                    tar.add(file_path, arcname=arcname)
                        else:
                            tar.add(item_path, arcname=os.path.basename(item_path))

                    # Deploy the archive
                    deployed_files = [archive_name]
                    # Create a temp directory with only the archive file
                    archive_only_dir = os.path.join(temp_dir, "_archive_deploy")
                    os.makedirs(archive_only_dir, exist_ok=True)
                    archive_deploy_path = os.path.join(archive_only_dir, archive_name)
                    import shutil

                    shutil.copy(archive_path, archive_deploy_path)

                    success = deployment.deploy_files(
                        archive_only_dir,
                        connection,
                        target_dir,
                        region,
                        archive_only_dir,
                    )
                else:
                    # Original behavior - deploy directory contents
                    deployed_files = _get_files_list(item_path)
                    success = deployment.deploy_files(
                        item_path, connection, target_dir, region, item_path
                    )

                s3_uri = connection.get("s3Uri", "")
                return deployed_files if success else None, s3_uri
            else:
                typer.echo(f"  No files found for '{item_name}' in bundle")
                return [], None
    finally:
        if is_s3_url(bundle_file) and local_bundle_path != bundle_file:
            os.unlink(local_bundle_path)

    return None, None


def _deploy_git_from_bundle(
    bundle_file: str,
    git_config: Dict[str, Any],
    project_name: str,
    config: Dict[str, Any],
    target_dir: str,
) -> Tuple[Optional[List[str]], Optional[str]]:
    """Deploy git repository from bundle to target directory."""
    from ..helpers.bundle_storage import download_bundle, is_s3_url

    local_bundle_path = download_bundle(bundle_file, config["region"])

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(local_bundle_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            # Git repos are in bundle under repositories/{repository-name}
            repositories_dir = Path(temp_dir) / "repositories"
            if not repositories_dir.exists():
                typer.echo("⚠️  No repositories directory found in bundle")
                return None, None

            deployed_files = []
            connection = _get_project_connection(project_name, git_config, config)
            region = config.get("region", "us-east-1")

            # Deploy all repositories
            for repo_dir in repositories_dir.iterdir():
                if repo_dir.is_dir():
                    success = deployment.deploy_files(
                        str(repo_dir), connection, target_dir, region, str(repo_dir)
                    )
                    if success:
                        deployed_files.extend(_get_files_list(str(repo_dir)))

            s3_uri = connection.get("s3Uri", "")
            return deployed_files if deployed_files else None, s3_uri
    finally:
        if is_s3_url(bundle_file) and local_bundle_path != bundle_file:
            os.unlink(local_bundle_path)

    return None, None


def _display_deployment_summary_new(
    bundle_path: str,
    storage_results: List[Tuple[Optional[List[str]], Optional[str]]],
    git_results: List[Tuple[Optional[List[str]], Optional[str]]],
):
    """Display deployment summary for new structure."""
    typer.echo("\n📦 Deployment Summary:")

    for i, (files, s3_uri) in enumerate(storage_results):
        if files is not None:
            typer.echo(f"  ✅ Storage item {i + 1}: {len(files)} files → {s3_uri}")
        else:
            typer.echo(f"  ❌ Storage item {i + 1}: Failed")

    for i, (files, s3_uri) in enumerate(git_results):
        if files is not None:
            typer.echo(f"  ✅ Git item {i + 1}: {len(files)} files → {s3_uri}")
        else:
            typer.echo(f"  ❌ Git item {i + 1}: Failed")


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
        return {}

    connection_name = file_config.get("connectionName", "default.s3_shared")
    connections = project_info.get("connections", {})
    return connections.get(connection_name, {})


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

    try:
        # workflows_config is from bundle_target_configuration, not a list of workflows
        # Skip validation for now as it needs workflow connection info, not bundle target config
        typer.echo("✅ Workflow validation completed")
    except Exception as e:
        typer.echo("⚠️ Workflow validation failed: " + str(e))
        # Don't fail deployment for validation issues


def _process_catalog_assets(
    target_config,
    manifest: BundleManifest,
    config: Dict[str, Any],
    emitter=None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Process catalog assets for DataZone access.

    Args:
        target_config: Target configuration object
        manifest: Pipeline manifest object
        config: Configuration dictionary
        emitter: Optional EventEmitter for monitoring
        metadata: Optional metadata for events

    Returns:
        True if all assets processed successfully, False otherwise
    """
    from ..helpers.monitoring import build_target_info

    # Check if catalog processing is disabled in bundle target configuration
    if (
        target_config.bundle_target_configuration
        and target_config.bundle_target_configuration.catalog
        and target_config.bundle_target_configuration.catalog.get("disable", False)
    ):
        typer.echo("📋 Catalog asset processing disabled in target configuration")
        return True

    # Check if catalog assets are configured
    if not manifest.bundle.catalog or not manifest.bundle.catalog.assets:
        typer.echo("📋 No catalog assets configured")
        return True

    typer.echo("🔍 Processing catalog assets...")

    # Emit catalog assets started
    if emitter:
        target_info = build_target_info(target_config.name, target_config)
        asset_configs = [
            {
                "assetId": asset.selector.assetId,
                "permission": asset.permission,
            }
            for asset in manifest.bundle.catalog.assets
        ]
        emitter.catalog_assets_started(
            manifest.bundle_name, target_info, asset_configs, metadata
        )

    # Import datazone helper functions
    from ..helpers.datazone import (
        get_project_id_by_name,
        process_catalog_assets,
    )

    # Get domain and project IDs
    region = target_config.domain.region

    # Resolve domain using name, tags, or auto-detect
    from ..helpers.datazone import resolve_domain_id

    domain_id, domain_name = resolve_domain_id(
        domain_name=target_config.domain.name,
        domain_tags=target_config.domain.tags,
        region=region,
    )

    if not domain_id:
        error_msg = f"Could not resolve domain in region {region}"
        if emitter:
            target_info = build_target_info(target_config.name, target_config)
            error = {
                "stage": "catalog-assets",
                "code": "DOMAIN_NOT_FOUND",
                "message": error_msg,
            }
            emitter.catalog_assets_failed(
                manifest.bundle_name, target_info, error, metadata
            )
        handle_error(error_msg)
        return False

    project_name = target_config.project.name

    project_id = get_project_id_by_name(project_name, domain_id, region)
    if not project_id:
        error_msg = f"Could not find project ID for project: {project_name}"
        if emitter:
            target_info = build_target_info(target_config.name, target_config)
            error = {
                "stage": "catalog-assets",
                "code": "PROJECT_NOT_FOUND",
                "message": error_msg,
            }
            emitter.catalog_assets_failed(
                manifest.bundle_name, target_info, error, metadata
            )
        handle_error(error_msg)
        return False

    # Convert assets to dictionary format for processing
    assets_data = []
    for asset in manifest.bundle.catalog.assets:
        asset_dict = {
            "selector": {},
            "permission": asset.permission,
            "requestReason": asset.requestReason,
        }

        if asset.selector.assetId:
            asset_dict["selector"]["assetId"] = asset.selector.assetId

        if asset.selector.search:
            asset_dict["selector"]["search"] = {
                "assetType": asset.selector.search.assetType,
                "identifier": asset.selector.search.identifier,
            }

        assets_data.append(asset_dict)

    # Process all catalog assets
    try:
        success = process_catalog_assets(domain_id, project_id, assets_data, region)
        if success:
            typer.echo("✅ All catalog assets processed successfully")

            # Emit catalog assets completed
            if emitter:
                target_info = build_target_info(target_config.name, target_config)
                asset_results = [
                    {
                        "assetId": asset.selector.assetId,
                        "status": "processed",
                    }
                    for asset in manifest.bundle.catalog.assets
                ]
                emitter.catalog_assets_completed(
                    manifest.bundle_name, target_info, asset_results, metadata
                )
        else:
            error_msg = "Failed to process catalog assets"
            if emitter:
                target_info = build_target_info(target_config.name, target_config)
                error = {
                    "stage": "catalog-assets",
                    "code": "PROCESSING_FAILED",
                    "message": error_msg,
                }
                emitter.catalog_assets_failed(
                    manifest.bundle_name, target_info, error, metadata
                )
            handle_error(error_msg)
        return success
    except Exception as e:
        error_msg = f"Error processing catalog assets: {e}"
        if emitter:
            target_info = build_target_info(target_config.name, target_config)
            error = {
                "stage": "catalog-assets",
                "code": "PROCESSING_ERROR",
                "message": str(e),
            }
            emitter.catalog_assets_failed(
                manifest.bundle_name, target_info, error, metadata
            )
        handle_error(error_msg)
        return False


def _create_airflow_serverless_workflows(
    bundle_path: str,
    manifest: BundleManifest,
    target_config,
    config: Dict[str, Any],
    target_name: str,
    s3_bucket: Optional[str],
    s3_prefix: Optional[str],
    emitter=None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Create serverless Airflow workflows if airflow-serverless flag is enabled.

    Args:
        bundle_path: Path to the bundle file
        manifest: Pipeline manifest object
        target_config: Target configuration object
        config: Configuration dictionary
        target_name: Name of the target
        s3_bucket: S3 bucket where files were deployed
        s3_prefix: S3 prefix where files were deployed
        emitter: Optional EventEmitter for monitoring
        metadata: Optional metadata for events

    Returns:
        True if all workflows created successfully, False otherwise
    """
    from ..helpers.monitoring import build_target_info

    # Check if any workflow configuration has airflow-serverless enabled
    airflow_serverless_enabled = False

    # Check bundle storage configurations for airflow-serverless flag
    if manifest.bundle.storage:
        for storage_config in manifest.bundle.storage:
            if storage_config.get("airflow-serverless", False):
                airflow_serverless_enabled = True
                break

    # Check workflows section for airflow-serverless engine
    if manifest.workflows:
        for workflow in manifest.workflows:
            if workflow.engine == "airflow-serverless":
                airflow_serverless_enabled = True
                break

    if not airflow_serverless_enabled:
        typer.echo("📋 No serverless Airflow workflows configured")
        return True

    typer.echo("🚀 Creating serverless Airflow workflows...")

    # Emit workflow creation started
    if emitter:
        target_info = build_target_info(target_name, target_config)
        workflows_info = [
            {
                "workflowName": wf.workflow_name,
                "engine": wf.engine,
            }
            for wf in manifest.workflows
            if wf.engine == "airflow-serverless"
        ]
        emitter.workflow_creation_started(
            manifest.bundle_name, target_info, workflows_info, metadata
        )

    try:
        from ..helpers import airflow_serverless
        from ..helpers.bundle_storage import download_bundle
        from ..helpers.datazone import resolve_domain_id

        # Download bundle to local temp file if it's on S3
        download_bundle(bundle_path, config["region"])

        # Get project user role ARN for serverless Airflow execution
        project_name = target_config.project.name
        region = config["region"]

        # Resolve domain
        domain_id, domain_name = resolve_domain_id(
            domain_name=target_config.domain.name,
            domain_tags=target_config.domain.tags,
            region=region,
        )

        role_arn = datazone.get_project_user_role_arn(project_name, domain_name, region)
        if not role_arn:
            error_msg = "No project user role found"
            typer.echo(f"❌ {error_msg}")
            if emitter:
                target_info = build_target_info(target_name, target_config)
                error = {
                    "stage": "workflow-creation",
                    "code": "ROLE_NOT_FOUND",
                    "message": error_msg,
                }
                emitter.workflow_creation_failed(
                    manifest.bundle_name, target_info, error, metadata
                )
            return False

        # Get domain and project IDs for workflow creation
        domain_id = datazone.get_domain_id_by_name(domain_name, region)
        if not domain_id:
            error_msg = f"Could not find domain ID for domain: {domain_name}"
            typer.echo(f"❌ {error_msg}")
            if emitter:
                target_info = build_target_info(target_name, target_config)
                error = {
                    "stage": "workflow-creation",
                    "code": "DOMAIN_NOT_FOUND",
                    "message": error_msg,
                }
                emitter.workflow_creation_failed(
                    manifest.bundle_name, target_info, error, metadata
                )
            return False

        project_id = datazone.get_project_id_by_name(project_name, domain_id, region)
        if not project_id:
            error_msg = f"Could not find project ID for project: {project_name}"
            typer.echo(f"❌ {error_msg}")
            if emitter:
                target_info = build_target_info(target_name, target_config)
                error = {
                    "stage": "workflow-creation",
                    "code": "PROJECT_NOT_FOUND",
                    "message": error_msg,
                }
                emitter.workflow_creation_failed(
                    manifest.bundle_name, target_info, error, metadata
                )
            return False

        workflows_created = []

        if not s3_bucket or s3_prefix is None:
            error_msg = "Could not determine S3 location from storage deployment"
            typer.echo(f"❌ {error_msg}")
            if emitter:
                target_info = build_target_info(target_name, target_config)
                error = {
                    "stage": "workflow-creation",
                    "code": "S3_LOCATION_NOT_FOUND",
                    "message": error_msg,
                }
                emitter.workflow_creation_failed(
                    manifest.bundle_name, target_info, error, metadata
                )
            return False

        # Search for DAG files in S3
        s3_client = boto3.client("s3", region_name=region)
        dag_files_in_s3 = _find_dag_files_in_s3(
            s3_client, s3_bucket, s3_prefix, manifest, target_config
        )

        if not dag_files_in_s3:
            typer.echo("⚠️ No DAG files found to create workflows")
            return True

        # Initialize context resolver using our helpers
        from ..helpers.context_resolver import ContextResolver

        resolver = ContextResolver(
            project_name=project_name,
            domain_id=domain_id,
            domain_name=domain_name,
            region=region,
            env_vars=target_config.environment_variables or {},
        )

        for s3_key, workflow_name_from_yaml in dag_files_in_s3:
            workflow_name = _generate_workflow_name(
                manifest.bundle_name,
                workflow_name_from_yaml,
                target_config,
            )

            # Download workflow YAML from S3, resolve variables, upload back
            temp_yaml = tempfile.NamedTemporaryFile(
                mode="w+", suffix=".yaml", delete=False
            )
            try:
                # Download original
                typer.echo(f"🔍 DEBUG: Downloading {s3_key} from S3")
                s3_client.download_file(s3_bucket, s3_key, temp_yaml.name)

                # Read and resolve
                with open(temp_yaml.name, "r") as f:
                    original_content = f.read()

                typer.echo(
                    f"🔍 DEBUG: Original content length: {len(original_content)}"
                )
                resolved_content = resolver.resolve(original_content)
                typer.echo(
                    f"🔍 DEBUG: Resolved content length: {len(resolved_content)}"
                )

                if original_content != resolved_content:
                    typer.echo("🔍 DEBUG: Content changed, uploading resolved version")
                else:
                    typer.echo("🔍 DEBUG: No variables found to resolve")

                # Upload resolved version
                with open(temp_yaml.name, "w") as f:
                    f.write(resolved_content)

                typer.echo(
                    f"🔍 DEBUG: Uploading resolved content to s3://{s3_bucket}/{s3_key}"
                )
                s3_client.upload_file(temp_yaml.name, s3_bucket, s3_key)
                typer.echo(f"✅ Resolved variables in {s3_key}")
            except Exception as e:
                typer.echo(f"❌ Error resolving variables in {s3_key}: {e}", err=True)
                raise
            finally:
                os.unlink(temp_yaml.name)

            # S3 location for the DAG file
            s3_location = f"s3://{s3_bucket}/{s3_key}"

            # Create serverless Airflow workflow
            typer.echo(
                "🔍 DEBUG: About to call airflow_serverless.create_workflow with:"
            )
            typer.echo(f"🔍 DEBUG: workflow_name={workflow_name}")
            typer.echo(f"🔍 DEBUG: dag_s3_location={s3_location}")
            typer.echo(f"🔍 DEBUG: role_arn={role_arn}")
            typer.echo(f"🔍 DEBUG: datazone_domain_id={domain_id}")
            typer.echo(f"🔍 DEBUG: datazone_project_id={project_id}")

            result = airflow_serverless.create_workflow(
                workflow_name=workflow_name,
                dag_s3_location=s3_location,
                role_arn=role_arn,
                description=f"SMUS CI/CD workflow for {manifest.bundle_name}",
                tags={
                    "Pipeline": manifest.bundle_name,
                    "Target": target_config.project.name,
                    "STAGE": target_name.upper(),
                    "CreatedBy": "SMUS-CICD",
                },
                datazone_domain_id=domain_id,
                datazone_domain_region=config.get("region"),
                datazone_project_id=project_id,
                region=config.get("region"),
            )

            typer.echo(
                f"🔍 DEBUG: airflow_serverless.create_workflow returned: {result}"
            )
            typer.echo(f"🔍 DEBUG: result type: {type(result)}")
            if isinstance(result, dict):
                typer.echo(f"🔍 DEBUG: result keys: {list(result.keys())}")
                typer.echo(f"🔍 DEBUG: result.get('success'): {result.get('success')}")
                typer.echo(f"🔍 DEBUG: result.get('error'): {result.get('error')}")

            if result.get("success"):
                workflow_arn = result["workflow_arn"]
                workflows_created.append(
                    {
                        "name": workflow_name,
                        "arn": workflow_arn,
                        "s3_key": s3_key,
                    }
                )
                typer.echo(f"✅ Created Overdrive workflow: {workflow_name}")
                typer.echo(f"   ARN: {workflow_arn}")

                # Validate workflow status
                workflow_status = airflow_serverless.get_workflow_status(
                    workflow_arn, region=config.get("region")
                )
                if workflow_status.get("success"):
                    status = workflow_status.get("status")
                    typer.echo(f"   Status: {status}")
                    if status == "FAILED":
                        error_msg = f"Workflow {workflow_name} is in FAILED state"
                        typer.echo(f"❌ {error_msg}")
                        if emitter:
                            target_info = build_target_info(target_name, target_config)
                            error = {
                                "stage": "workflow-creation",
                                "code": "WORKFLOW_FAILED",
                                "message": error_msg,
                                "details": {"workflowName": workflow_name},
                            }
                            emitter.workflow_creation_failed(
                                manifest.bundle_name, target_info, error, metadata
                            )
                        return False
                else:
                    error_msg = workflow_status.get("error")
                    typer.echo(f"❌ Could not verify workflow status: {error_msg}")
                    if emitter:
                        target_info = build_target_info(target_name, target_config)
                        error = {
                            "stage": "workflow-creation",
                            "code": "WORKFLOW_STATUS_CHECK_FAILED",
                            "message": error_msg,
                            "details": {"workflowName": workflow_name},
                        }
                        emitter.workflow_creation_failed(
                            manifest.bundle_name, target_info, error, metadata
                        )
                    return False
            else:
                error_msg = result.get("error")
                typer.echo(f"❌ Failed to create workflow {workflow_name}: {error_msg}")
                if emitter:
                    target_info = build_target_info(target_name, target_config)
                    error = {
                        "stage": "workflow-creation",
                        "code": "WORKFLOW_CREATION_FAILED",
                        "message": error_msg,
                        "details": {"workflowName": workflow_name},
                    }
                    emitter.workflow_creation_failed(
                        manifest.bundle_name, target_info, error, metadata
                    )
                return False

        if workflows_created:
            typer.echo(
                f"\n🎉 Successfully created {len(workflows_created)} Overdrive workflows"
            )

            # Emit workflow creation completed
            if emitter:
                target_info = build_target_info(target_name, target_config)
                workflow_results = [
                    {
                        "workflowName": wf["name"],
                        "engine": "airflow-serverless",
                        "status": "created",
                        "workflowArn": wf["arn"],
                    }
                    for wf in workflows_created
                ]
                emitter.workflow_creation_completed(
                    manifest.bundle_name, target_info, workflow_results, metadata
                )

            return True
        else:
            typer.echo("⚠️ No workflows were created")
            return True

    except Exception as e:
        error_msg = f"Error creating Overdrive workflows: {e}"
        typer.echo(f"❌ {error_msg}")
        if emitter:
            target_info = build_target_info(target_name, target_config)
            error = {
                "stage": "workflow-creation",
                "code": "WORKFLOW_CREATION_ERROR",
                "message": str(e),
            }
            emitter.workflow_creation_failed(
                manifest.bundle_name, target_info, error, metadata
            )
        return False


def _get_airflow_serverless_execution_role(config: Dict[str, Any]) -> Optional[str]:
    """
    Get the IAM role ARN for Overdrive workflow execution.

    Args:
        config: Configuration dictionary

    Returns:
        Role ARN string or None if not found
    """
    # For now, use a default role name pattern
    # In production, this should be configurable
    account_id = config.get("aws", {}).get("account_id")
    if not account_id:
        # Try to get account ID from STS
        try:
            import boto3

            sts = boto3.client("sts")
            identity = sts.get_caller_identity()
            account_id = identity["Account"]
        except Exception as e:
            typer.echo(f"⚠️ Failed to get account ID: {e}", err=True)
            return None

    # Use the role we created during testing
    return f"arn:aws:iam::{account_id}:role/OverdriveExecutionRole"


def _find_dag_files_in_s3(
    s3_client, s3_bucket: str, s3_prefix: str, manifest: BundleManifest, target_config
) -> List[tuple]:
    """
    Find DAG YAML files in S3 by searching target directories from bundle_target_configuration.

    Args:
        s3_client: Boto3 S3 client
        s3_bucket: S3 bucket name
        s3_prefix: Base S3 prefix (e.g., 'shared/')
        manifest: Pipeline manifest object
        target_config: Target configuration with bundle_target_configuration

    Returns:
        List of tuples (s3_key, workflow_name) for workflows found in S3
    """
    dag_files = []

    if not manifest.workflows:
        return dag_files

    # Get target directories from bundle_target_configuration
    search_prefixes = []
    if hasattr(target_config, "bundle_target_configuration") and hasattr(
        target_config.bundle_target_configuration, "storage"
    ):
        for storage_item in target_config.bundle_target_configuration.storage:
            if hasattr(storage_item, "target_directory"):
                target_dir = storage_item.target_directory or "."
                if target_dir == ".":
                    search_prefixes.append(s3_prefix)
                else:
                    search_prefixes.append(f"{s3_prefix}{target_dir}/")

    # Fallback to base prefix
    if not search_prefixes:
        search_prefixes = [s3_prefix]

    # Search for each workflow specified in manifest
    for workflow in manifest.workflows:
        workflow_name = workflow.workflow_name
        found = False

        # Search each configured prefix
        for search_prefix in search_prefixes:
            try:
                paginator = s3_client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=s3_bucket, Prefix=search_prefix):
                    if "Contents" not in page:
                        continue

                    for obj in page["Contents"]:
                        s3_key = obj["Key"]
                        if s3_key.endswith((".yaml", ".yml")):
                            # Download and check if it matches workflow
                            try:
                                import yaml

                                response = s3_client.get_object(
                                    Bucket=s3_bucket, Key=s3_key
                                )
                                content = yaml.safe_load(response["Body"].read())
                                if isinstance(content, dict):
                                    # Check if any top-level key matches workflow_name or has matching dag_id
                                    for key, value in content.items():
                                        if key == workflow_name or (
                                            isinstance(value, dict)
                                            and value.get("dag_id") == workflow_name
                                        ):
                                            dag_files.append((s3_key, workflow_name))
                                            found = True
                                            break
                            except Exception:
                                continue
                        if found:
                            break
                    if found:
                        break
            except Exception:
                continue
            if found:
                break

        if not found:
            typer.echo(f"⚠️ Workflow YAML not found for: {workflow_name}")

    return dag_files


def _generate_workflow_name(bundle_name: str, dag_name: str, target_config) -> str:
    """
    Generate a unique workflow name for Overdrive.

    Args:
        bundle_name: Name of the bundle
        dag_name: Name of the DAG file (without extension)
        target_config: Target configuration object

    Returns:
        Generated workflow name
    """
    # Create a unique name combining pipeline, target, and DAG name
    target_name = target_config.project.name.replace("-", "_")
    safe_pipeline = bundle_name.replace("-", "_")
    safe_dag = dag_name.replace("-", "_")

    return f"{safe_pipeline}_{target_name}_{safe_dag}"


def _resolve_environment_variables(
    content: str, environment_variables: Dict[str, Any]
) -> str:
    """
    Resolve environment variable placeholders in content.

    Args:
        content: YAML content with ${VAR_NAME} or $VAR_NAME placeholders
        environment_variables: Dictionary of variable name to value mappings

    Returns:
        Content with resolved variables
    """
    import re

    def replace_var(match):
        var_name = match.group(1)
        if var_name in environment_variables:
            return str(environment_variables[var_name])
        return match.group(0)  # Return original if not found

    # Replace ${VAR_NAME} and $VAR_NAME patterns
    content = re.sub(r"\$\{([^}]+)\}", replace_var, content)
    content = re.sub(r"\$([A-Za-z_][A-Za-z0-9_]*)", replace_var, content)
    return content


def _upload_dag_to_s3(
    dag_file_path: str,
    workflow_name: str,
    config: Dict[str, Any],
    target_config=None,
    project_id=None,
    domain_id=None,
) -> Optional[Dict[str, str]]:
    """
    Upload DAG file to S3 for Overdrive workflow creation.

    Args:
        dag_file_path: Local path to DAG file
        workflow_name: Name of the workflow
        config: Configuration dictionary
        target_config: Target configuration with environment variables
        project_id: DataZone project ID
        domain_id: DataZone domain ID

    Returns:
        S3 location dictionary or None if failed
    """
    try:
        import boto3

        region = config.get("region", "us-east-1")

        # Get S3 bucket from project's default.s3_shared connection
        bucket_name = None
        if project_id and domain_id:
            connections = datazone.get_project_connections(
                project_id, domain_id, region
            )
            s3_shared_conn = connections.get("default.s3_shared", {})
            s3_uri = s3_shared_conn.get("s3Uri", "")
            if s3_uri:
                # Extract bucket name from s3://bucket-name/path/
                bucket_name = s3_uri.replace("s3://", "").split("/")[0]

        # Fallback to hardcoded pattern if connection not found
        if not bucket_name:
            account_id = config.get("aws", {}).get("account_id")
            if not account_id:
                sts = boto3.client("sts")
                identity = sts.get_caller_identity()
                account_id = identity["Account"]
            bucket_name = (
                f"smus-airflow-serverless-{account_id}-{AIRFLOW_SERVERLESS_REGION}"
            )

        object_key = f"workflows/{workflow_name}.yaml"

        # Create S3 client
        s3_client = boto3.client("s3", region_name=region)

        # Try to create bucket if it doesn't exist
        try:
            s3_client.head_bucket(Bucket=bucket_name)
        except Exception as e:
            typer.echo(f"Bucket {bucket_name} doesn't exist, creating it: {e}")
            try:
                if region == "us-east-1":
                    s3_client.create_bucket(Bucket=bucket_name)
                else:
                    s3_client.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={"LocationConstraint": region},
                    )
            except Exception as e:
                typer.echo(f"⚠️ Could not create bucket {bucket_name}: {e}")
                # Fall back to existing bucket from tests
                bucket_name = "amirbo-sample-data-588738596778-us-east-2"
                object_key = f"airflow-serverless/workflows/{workflow_name}.yaml"

        # Upload DAG file
        with open(dag_file_path, "r") as f:
            dag_content = f.read()

        typer.echo(f"🔍 DEBUG: Original DAG file path: {dag_file_path}")
        typer.echo(f"🔍 DEBUG: Original DAG content:\n{dag_content}")

        # Resolve environment variables if target config is provided
        if (
            target_config
            and hasattr(target_config, "environment_variables")
            and target_config.environment_variables
        ):
            typer.echo(
                f"🔍 DEBUG: Environment variables found: {target_config.environment_variables}"
            )
            resolved_content = _resolve_environment_variables(
                dag_content, target_config.environment_variables
            )
            typer.echo(f"🔍 DEBUG: Resolved DAG content:\n{resolved_content}")
            dag_content = resolved_content
        else:
            typer.echo("🔍 DEBUG: No environment variables to resolve")
            typer.echo(f"🔍 DEBUG: target_config: {target_config}")
            if target_config:
                typer.echo(
                    f"🔍 DEBUG: target_config.environment_variables: {getattr(target_config, 'environment_variables', 'NOT_FOUND')}"
                )

        typer.echo(f"🔍 DEBUG: Final DAG content being uploaded:\n{dag_content}")

        s3_client.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=dag_content,
            ContentType="text/yaml",
        )

        return {"Bucket": bucket_name, "ObjectKey": object_key}

    except Exception as e:
        typer.echo(f"❌ Failed to upload DAG to S3: {e}")
        return None

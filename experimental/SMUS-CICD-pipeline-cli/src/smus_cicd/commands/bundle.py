"""Bundle command implementation."""

import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from typing import Optional

import boto3
import typer

from ..helpers import deployment
from ..helpers.utils import get_datazone_project_info, load_config, load_yaml


def display_bundle_tree(zip_path: str, output: str):
    """Display bundle contents in a nice tree structure."""
    if output.upper() == "JSON":
        return  # Skip tree display for JSON output

    try:
        with zipfile.ZipFile(zip_path, "r") as zipf:
            file_list = sorted(zipf.namelist())

        if not file_list:
            return

        typer.echo("\n📦 Bundle Contents:")
        typer.echo("=" * 50)

        # Build tree structure
        tree = {}
        for file_path in file_list:
            parts = file_path.split("/")
            current = tree
            for part in parts[:-1]:  # directories
                if part not in current:
                    current[part] = {}
                current = current[part]
            # Add file
            if parts[-1]:  # not empty (avoid trailing slashes)
                current[parts[-1]] = None

        def print_tree(node, prefix="", is_last=True):
            items = list(node.items()) if isinstance(node, dict) else []
            for i, (name, subtree) in enumerate(items):
                is_last_item = i == len(items) - 1
                current_prefix = "└── " if is_last_item else "├── "

                if subtree is None:  # It's a file
                    typer.echo(f"{prefix}{current_prefix}{name}")
                else:  # It's a directory
                    typer.echo(f"{prefix}{current_prefix}{name}/")
                    extension = "    " if is_last_item else "│   "
                    print_tree(subtree, prefix + extension, is_last_item)

        print_tree(tree)
        typer.echo("=" * 50)
        typer.echo(f"📊 Total files: {len(file_list)}")

    except Exception as e:
        typer.echo(f"⚠️ Could not display bundle contents: {e}")


def bundle_command(
    targets: Optional[str], manifest_file: str, output_dir: str, output: str
):
    """Create bundle zip files by downloading from S3 connection locations."""
    try:
        config = load_config()
        manifest = load_yaml(manifest_file)

        # Parse targets - handle single target or comma-separated list
        target_list = []
        if targets:
            target_list = [t.strip() for t in targets.split(",")]

        # Use first target for now (bundle command typically works with single target)
        target_name = target_list[0] if target_list else None
        if "domain" in manifest:
            config["domain"] = manifest["domain"]
            config["region"] = manifest["domain"].get("region")
            if not config["region"]:
                raise ValueError(
                    "Region must be specified in manifest domain configuration"
                )

        region = config.get("region")
        if not region:
            raise ValueError("Region must be specified in configuration or manifest")

        # Check if bundle section exists
        bundle_config = manifest.get("bundle", {})
        if not bundle_config:
            typer.echo("Error: No bundle section found in pipeline manifest", err=True)
            raise typer.Exit(1)

        # Get target configuration
        targets = manifest.get("targets", {})

        # If no target specified, find the default target
        if not target_name:
            for name, target_config in targets.items():
                if target_config.get("default", False):
                    target_name = name
                    typer.echo(f"Using default target: {target_name}")
                    break

            if not target_name:
                typer.echo(
                    "Error: No target specified and no default target found", err=True
                )
                raise typer.Exit(1)

        if target_name not in targets:
            typer.echo(f"Error: Target '{target_name}' not found in manifest", err=True)
            raise typer.Exit(1)

        target_config = targets[target_name]
        project_name = target_config.get("project", {}).get("name")

        typer.echo(f"Creating bundle for target: {target_name}")
        typer.echo(f"Project: {project_name}")

        # Get project connections to find S3 locations
        project_info = get_datazone_project_info(project_name, config)
        connections = project_info.get("connections", {})

        # Get bundles directory from manifest or use default
        bundle_config = manifest.get("bundle", {})
        bundles_directory = bundle_config.get("bundlesDirectory", "./bundles")

        # Import bundle storage helper
        from ..helpers.bundle_storage import (
            ensure_bundle_directory_exists,
            is_s3_url,
            upload_bundle,
        )

        # Ensure bundle directory exists (create local or validate S3)
        ensure_bundle_directory_exists(bundles_directory, region)

        # Create zip file path (always create locally first, then upload if S3)
        pipeline_name = manifest.get("pipelineName", "pipeline")
        zip_filename = f"{pipeline_name}.zip"

        if is_s3_url(bundles_directory):
            # Create temporary local file for S3 upload
            temp_dir = tempfile.mkdtemp(prefix="smus_bundle_output_")
            zip_path = os.path.join(temp_dir, zip_filename)
        else:
            # Expand user home directory if needed for local paths
            bundles_directory = os.path.expanduser(bundles_directory)
            os.makedirs(bundles_directory, exist_ok=True)
            zip_path = os.path.join(bundles_directory, zip_filename)

        # Create temporary directory for all bundle content
        with tempfile.TemporaryDirectory(prefix="smus_bundle_") as temp_bundle_dir:
            total_files_added = 0

            s3_client = boto3.client("s3", region_name=region)

            # Process workflow bundles
            workflow_config = bundle_config.get("workflow", [])
            if isinstance(workflow_config, list):
                workflow_bundles = workflow_config
            else:
                workflow_bundles = [workflow_config] if workflow_config else []

            for bundle_def in workflow_bundles:
                connection_name = bundle_def.get("connectionName")
                include_patterns = bundle_def.get("include", [])
                append_flag = bundle_def.get("append", True)

                if not connection_name or connection_name not in connections:
                    continue

                connection = connections[connection_name]
                s3_uri = connection.get("s3Uri")
                if not s3_uri:
                    continue

                typer.echo(
                    f"Downloading workflows from S3: {connection_name} (append: {append_flag})"
                )

                # List S3 contents first
                deployment.list_s3_contents(s3_client, s3_uri, "Workflows")

                files_added = deployment.download_s3_files(
                    s3_client, s3_uri, include_patterns, temp_bundle_dir, ""
                )
                total_files_added += files_added
                typer.echo(f"  Downloaded {files_added} workflow files from S3")

            # Process storage bundles
            storage_config = bundle_config.get("storage", [])
            if isinstance(storage_config, list):
                storage_bundles = storage_config
            else:
                storage_bundles = [storage_config] if storage_config else []

            for bundle_def in storage_bundles:
                connection_name = bundle_def.get("connectionName")
                include_patterns = bundle_def.get("include", [])
                append_flag = bundle_def.get("append", False)

                if not connection_name or connection_name not in connections:
                    continue

                connection = connections[connection_name]
                s3_uri = connection.get("s3Uri")
                if not s3_uri:
                    continue

                typer.echo(
                    f"Downloading storage from S3: {connection_name} (append: {append_flag})"
                )

                # List S3 contents first
                deployment.list_s3_contents(s3_client, s3_uri, "Storage")

                files_added = deployment.download_s3_files(
                    s3_client, s3_uri, include_patterns, temp_bundle_dir, "storage"
                )
                total_files_added += files_added
                typer.echo(f"  Downloaded {files_added} storage files from S3")

            # Process Git repositories
            git_config = bundle_config.get("git", {})
            if git_config:
                repository = git_config.get("repository")
                url = git_config.get("url")
                target_dir = git_config.get("targetDir", "git")

                if url:
                    typer.echo(f"Cloning Git repository: {repository or url}")

                    try:
                        clone_path = os.path.join(
                            temp_bundle_dir, target_dir.lstrip("./")
                        )
                        os.makedirs(os.path.dirname(clone_path), exist_ok=True)

                        subprocess.run(
                            ["git", "clone", "--depth", "1", url, clone_path],
                            check=True,
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )

                        # Remove .git directory
                        git_dir = os.path.join(clone_path, ".git")
                        if os.path.exists(git_dir):
                            shutil.rmtree(git_dir)

                        # Count files
                        git_files_added = 0
                        for root, dirs, files in os.walk(clone_path):
                            git_files_added += len(files)

                        total_files_added += git_files_added
                        typer.echo(
                            f"  Cloned {git_files_added} files from Git repository"
                        )

                    except subprocess.TimeoutExpired:
                        typer.echo(
                            "Error: Git clone timed out after 60 seconds", err=True
                        )
                    except Exception as e:
                        typer.echo(f"Error cloning Git repository: {str(e)}", err=True)

            # Create or update zip archive from temp directory
            if total_files_added > 0:
                typer.echo(f"Creating archive: {zip_filename}")

                # Remove existing zip if it exists
                if os.path.exists(zip_path):
                    os.remove(zip_path)

                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(temp_bundle_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arc_name = os.path.relpath(file_path, temp_bundle_dir)
                            zipf.write(file_path, arc_name)

                # Upload to final location (S3 or local)
                final_bundle_path = upload_bundle(
                    zip_path, bundles_directory, pipeline_name, region
                )

                file_size = os.path.getsize(zip_path)
                typer.echo(
                    f"✅ Bundle created: {final_bundle_path} ({file_size} bytes)"
                )

                # Display bundle contents in tree structure
                display_bundle_tree(zip_path, output)

                # Clean up temporary directory if we used one for S3
                if is_s3_url(bundles_directory):
                    shutil.rmtree(os.path.dirname(zip_path))
            else:
                typer.echo("❌ No files found", err=True)
                raise typer.Exit(1)

        typer.echo(f"Bundle creation complete for target: {target_name}")

    except Exception as e:
        if output.upper() == "JSON":
            error_result = {
                "success": False,
                "error": str(e),
                "target": target_name,
                "manifest_file": manifest_file,
            }
            typer.echo(json.dumps(error_result, indent=2))
        else:
            typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)

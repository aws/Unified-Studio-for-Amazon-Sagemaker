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

from ..application import ApplicationManifest
from ..helpers import deployment
from ..helpers.utils import get_datazone_project_info, load_config


def display_bundle_tree(zip_path: str, output: str):
    """Display bundle contents in a nice tree structure."""
    if output.upper() == "JSON":
        return  # Skip tree display for JSON output

    try:
        with zipfile.ZipFile(zip_path, "r") as zipf:
            # Filter out Python cache files and dot directories
            file_list = sorted(
                [
                    f
                    for f in zipf.namelist()
                    if not f.endswith(".pyc")
                    and "__pycache__" not in f
                    and ".ipynb_checkpoints" not in f
                    and not any(part.startswith(".") for part in f.split("/"))
                ]
            )

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
        manifest = ApplicationManifest.from_file(manifest_file)

        # Parse targets - handle single target or comma-separated list
        target_list = []
        if targets:
            target_list = [t.strip() for t in targets.split(",")]

        # Use first target for now (bundle command typically works with single target)
        stage_name = target_list[0] if target_list else None

        # If no target specified, default to target with STAGE=DEV
        if not stage_name:
            for name in manifest.stages.keys():
                target_config = manifest.get_stage(name)
                if target_config.stage and target_config.stage.upper() == "DEV":
                    stage_name = name
                    typer.echo(
                        f"No target specified, defaulting to DEV target: {stage_name}"
                    )
                    break

        # Require target to be specified or found
        if not stage_name:
            typer.echo(
                "Error: No target specified and no DEV stage target found. Use --targets to specify a target (e.g., --targets dev)",
                err=True,
            )
            raise typer.Exit(1)

        if stage_name not in manifest.stages:
            typer.echo(f"Error: Target '{stage_name}' not found in manifest", err=True)
            raise typer.Exit(1)

        target_config = manifest.get_stage(stage_name)
        project_name = target_config.project.name

        # Get region and domain name from target's domain configuration
        if target_config.domain:
            if "domain" not in config:
                config["domain"] = {}
            config["domain"]["region"] = target_config.domain.region
            if target_config.domain.name:
                config["domain"]["name"] = target_config.domain.name
            if target_config.domain.tags:
                config["domain"]["tags"] = target_config.domain.tags

        region = config.get("domain", {}).get("region") or config.get("aws", {}).get(
            "region"
        )
        if not region:
            raise ValueError(
                "Region must be specified in target domain configuration or AWS config"
            )

        typer.echo(f"Creating bundle for target: {stage_name}")
        typer.echo(f"Project: {project_name}")

        # Get project connections to find S3 locations
        project_info = get_datazone_project_info(project_name, config)
        connections = project_info.get("connections", {})

        # Use output_dir parameter as bundles directory
        bundles_directory = output_dir

        # Import bundle storage helper
        from ..helpers.bundle_storage import (
            ensure_bundle_directory_exists,
            is_s3_url,
            upload_bundle,
        )

        # Ensure bundle directory exists (create local or validate S3)
        ensure_bundle_directory_exists(bundles_directory, region)

        # Create zip file path (always create locally first, then upload if S3)
        bundle_name = manifest.application_name
        zip_filename = f"{bundle_name}.zip"

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

            # Process storage bundles (unified - includes workflows)
            storage_bundles = (
                manifest.content.storage
                if manifest.content and manifest.content.storage
                else []
            )

            for bundle_def in storage_bundles:
                name = bundle_def.name
                connection_name = bundle_def.connectionName
                include_patterns = bundle_def.include if bundle_def.include else []
                append_flag = bundle_def.append if hasattr(bundle_def, "append") else False

                if not connection_name or connection_name not in connections:
                    continue

                connection = connections[connection_name]
                s3_uri = connection.get("s3Uri")
                if not s3_uri:
                    continue

                typer.echo(
                    f"Downloading '{name}' from S3: {connection_name} (append: {append_flag})"
                )

                # List S3 contents first
                deployment.list_s3_contents(s3_client, s3_uri, f"Storage[{name}]")

                # Download to bundle root with name as subdirectory
                files_added = deployment.download_s3_files(
                    s3_client, s3_uri, include_patterns, temp_bundle_dir, name
                )
                total_files_added += files_added
                typer.echo(f"  Downloaded {files_added} files for '{name}'")

            # Process Git repositories (supports both dict and list formats)
            git_repos = (
                manifest.content.git
                if manifest.content and manifest.content.git
                else []
            )

            for repo_config in git_repos:
                repository = (
                    repo_config.get("repository")
                    if isinstance(repo_config, dict)
                    else repo_config.repository
                )
                url = (
                    repo_config.get("url")
                    if isinstance(repo_config, dict)
                    else repo_config.url
                )

                if url and repository:
                    typer.echo(f"Cloning Git repository: {repository}")

                    try:
                        # Always clone to repositories/{repository-name}
                        clone_path = os.path.join(
                            temp_bundle_dir, "repositories", repository
                        )
                        os.makedirs(os.path.dirname(clone_path), exist_ok=True)

                        subprocess.run(
                            ["git", "clone", "--depth", "1", url, clone_path],
                            check=True,
                            capture_output=True,
                            text=True,
                            timeout=180,
                        )

                        # Remove .git directory and Python cache files
                        git_dir = os.path.join(clone_path, ".git")
                        if os.path.exists(git_dir):
                            shutil.rmtree(git_dir)

                        # Remove Python cache files and directories
                        for root, dirs, files in os.walk(clone_path, topdown=False):
                            # Remove __pycache__ and dot directories
                            dirs_to_remove = [
                                d
                                for d in dirs
                                if d == "__pycache__"
                                or d == ".ipynb_checkpoints"
                                or d.startswith(".")
                            ]
                            for d in dirs_to_remove:
                                shutil.rmtree(os.path.join(root, d))
                                dirs.remove(d)

                            # Remove .pyc and .DS_Store files
                            files_to_remove = [
                                f
                                for f in files
                                if f.endswith(".pyc") or f == ".DS_Store"
                            ]
                            for f in files_to_remove:
                                os.remove(os.path.join(root, f))

                        # Count files (after cleanup)
                        git_files_added = 0
                        for root, dirs, files in os.walk(clone_path):
                            git_files_added += len(files)

                        total_files_added += git_files_added
                        typer.echo(
                            f"  Cloned {git_files_added} files from {repository}"
                        )

                    except subprocess.TimeoutExpired:
                        typer.echo(
                            "Error: Git clone timed out after 180 seconds", err=True
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
                        # Filter out __pycache__ and dot directories
                        dirs[:] = [
                            d
                            for d in dirs
                            if d != "__pycache__"
                            and d != ".ipynb_checkpoints"
                            and not d.startswith(".")
                        ]

                        for file in files:
                            # Skip .pyc and .DS_Store files
                            if file.endswith(".pyc") or file == ".DS_Store":
                                continue

                            file_path = os.path.join(root, file)
                            arc_name = os.path.relpath(file_path, temp_bundle_dir)
                            zipf.write(file_path, arc_name)

                # Upload to final location (S3 or local)
                final_bundle_path = upload_bundle(
                    zip_path, bundles_directory, bundle_name, region
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

        typer.echo(f"Bundle creation complete for target: {stage_name}")

    except Exception as e:
        if output.upper() == "JSON":
            error_result = {
                "success": False,
                "error": str(e),
                "target": stage_name,
                "manifest_file": manifest_file,
            }
            typer.echo(json.dumps(error_result, indent=2))
        else:
            typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)

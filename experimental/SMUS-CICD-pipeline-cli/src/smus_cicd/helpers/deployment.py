"""
Deployment and S3 functions for SMUS CI/CD CLI.
"""

import os
import typer
from pathlib import Path


def deploy_files(
    temp_dir,
    connection,
    target_directory,
    region,
    source_folder,
    append_flag=True,
    connection_info=None,
):
    """Helper method to deploy files to S3 connection using AWS CLI."""
    import subprocess

    s3_uri = connection.get("s3Uri")
    if not s3_uri:
        conn_id = connection.get("connectionId", "unknown")
        conn_type = connection.get("type", "unknown")
        typer.echo(f"  ❌ No S3 URI found for connection {conn_id} (type: {conn_type})")
        return False  # Return False to indicate failure

    # Construct full S3 path
    full_s3_path = f"{s3_uri.rstrip('/')}/{target_directory}/"
    typer.echo(f"  S3 Location: {full_s3_path}")

    # Parse S3 URI for clearing if needed
    s3_parts = s3_uri.replace("s3://", "").split("/")
    bucket_name = s3_parts[0]
    s3_prefix = "/".join(s3_parts[1:])
    if s3_prefix and not s3_prefix.endswith("/"):
        s3_prefix += "/"
    s3_prefix += f"{target_directory}/"

    # Clear directory if append is False
    if not append_flag:
        typer.echo(f"  Clearing target directory (append: {append_flag})")
        try:
            from . import s3

            # List and delete existing objects using connection info
            objects = s3.list_objects(bucket_name, s3_prefix, connection_info)
            if objects:
                object_keys = [obj["Key"] for obj in objects]
                success = s3.delete_objects(bucket_name, object_keys, connection_info)
                if success:
                    typer.echo(f"    Cleared {len(object_keys)} existing files")
                else:
                    typer.echo("    Warning: Could not clear directory")
        except Exception as e:
            typer.echo(f"    Warning: Could not clear directory: {str(e)}")

    # Upload files using AWS CLI sync
    source_path = Path(temp_dir) / source_folder
    files_synced = 0

    if source_path.exists():
        try:
            # Use AWS CLI sync for bulk upload
            cmd = [
                "aws",
                "s3",
                "sync",
                str(source_path),
                full_s3_path,
                "--exclude",
                "*.pyc",
                "--exclude",
                "__pycache__/*",
                "--exclude",
                ".ipynb_checkpoints/*",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                # Count uploaded files from output and show them
                lines = (
                    result.stdout.strip().split("\n") if result.stdout.strip() else []
                )
                uploaded_files = [line for line in lines if "upload:" in line]
                files_synced = len(uploaded_files)

                for line in uploaded_files:
                    # Extract filename from AWS CLI output
                    parts = line.split(" to ")
                    if len(parts) > 1:
                        s3_path = parts[1]
                        # Extract relative filename
                        filename = s3_path.split("/")[-1]
                        typer.echo(f"    Synced: {filename}")

                if files_synced == 0 and not uploaded_files:
                    # No files to sync (already up to date)
                    # Count existing files in source
                    existing_files = []
                    for root, dirs, files in os.walk(source_path):
                        for file in files:
                            if (
                                not file.endswith(".pyc")
                                and "__pycache__" not in root
                                and ".ipynb_checkpoints" not in root
                            ):
                                existing_files.append(file)
                    files_synced = len(existing_files)
                    typer.echo(f"    All {files_synced} files already up to date")
            else:
                typer.echo(f"    Error syncing files: {result.stderr}", err=True)

        except Exception as e:
            typer.echo(f"    Error syncing files: {str(e)}", err=True)
    else:
        typer.echo(f"  ⚠️  Source folder {source_folder} not found in bundle")

    return files_synced


def list_s3_contents(s3_client, s3_uri, section_name=""):
    """List S3 contents in a tree structure."""
    from botocore.exceptions import ClientError

    # Parse S3 URI
    s3_parts = s3_uri.replace("s3://", "").split("/")
    bucket_name = s3_parts[0]
    s3_prefix = "/".join(s3_parts[1:]) if len(s3_parts) > 1 else ""

    if not s3_prefix.endswith("/") and s3_prefix:
        s3_prefix += "/"

    try:
        # List objects in S3
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket_name, Prefix=s3_prefix)

        files = []
        for page in pages:
            if "Contents" in page:
                for obj in page["Contents"]:
                    # Remove the prefix to get relative path
                    relative_path = obj["Key"][len(s3_prefix) :]
                    if relative_path:  # Skip empty paths
                        files.append(relative_path)

        if files:
            typer.echo(f"\n📂 S3 Source Content ({section_name}):")
            typer.echo(f"📍 Location: {s3_uri}")
            typer.echo("=" * 50)

            # Build tree structure
            tree = {}
            for file_path in sorted(files):
                parts = file_path.split("/")
                current = tree
                for part in parts[:-1]:  # directories
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                # Add file
                if parts[-1]:  # not empty
                    current[parts[-1]] = None

            # Print tree
            _print_tree(tree)
            typer.echo("=" * 50)
            typer.echo(f"📊 Total files found: {len(files)}\n")
        else:
            typer.echo(f"\n📂 S3 Source Content ({section_name}):")
            typer.echo(f"📍 Location: {s3_uri}")
            typer.echo("=" * 50)
            typer.echo("❌ No files found in S3 location")
            typer.echo("=" * 50)
            typer.echo("📊 Total files found: 0\n")

        return len(files)

    except ClientError as e:
        typer.echo(f"❌ Error accessing S3: {e}")
        return 0


def _print_tree(node, prefix="", is_last=True):
    """Print tree structure recursively."""
    items = list(node.items()) if isinstance(node, dict) else []
    for i, (name, subtree) in enumerate(items):
        is_last_item = i == len(items) - 1
        current_prefix = "└── " if is_last_item else "├── "

        if subtree is None:  # It's a file
            typer.echo(f"{prefix}{current_prefix}📄 {name}")
        else:  # It's a directory
            typer.echo(f"{prefix}{current_prefix}📁 {name}/")
            extension = "    " if is_last_item else "│   "
            _print_tree(subtree, prefix + extension, is_last_item)


def download_s3_files(
    s3_client, s3_uri, include_patterns, temp_bundle_dir, section_type
):
    """Helper method to download S3 files based on patterns using AWS CLI."""
    import subprocess
    import os

    # Parse S3 URI
    s3_parts = s3_uri.replace("s3://", "").split("/")
    bucket_name = s3_parts[0]
    s3_prefix = "/".join(s3_parts[1:]) if len(s3_parts) > 1 else ""

    downloaded_files = 0

    try:
        # Create target directory
        target_dir = Path(temp_bundle_dir) / section_type
        target_dir.mkdir(parents=True, exist_ok=True)

        # Build AWS CLI sync command
        if include_patterns:
            # Check if we have a wildcard pattern
            if "*" in include_patterns or include_patterns == ["*"]:
                # Wildcard - sync everything from root
                source_s3_uri = f"s3://{bucket_name}/{s3_prefix}"

                cmd = [
                    "aws",
                    "s3",
                    "sync",
                    source_s3_uri,
                    str(target_dir),
                    "--exclude",
                    "*.pyc",
                    "--exclude",
                    "__pycache__/*",
                    "--exclude",
                    ".ipynb_checkpoints/*",
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode == 0:
                    lines = (
                        result.stdout.strip().split("\n")
                        if result.stdout.strip()
                        else []
                    )
                    downloaded_files = len(
                        [line for line in lines if "download:" in line]
                    )

                    # Show downloaded files
                    for line in lines:
                        if "download:" in line:
                            parts = line.split(" to ")
                            if len(parts) > 1:
                                local_path = parts[1]
                                relative_path = os.path.relpath(
                                    local_path, str(target_dir)
                                )
                                typer.echo(f"  Downloaded: {relative_path}")
                else:
                    typer.echo(f"  Error syncing: {result.stderr}", err=True)
            else:
                # Specific patterns - sync each directory
                for pattern in include_patterns:
                    pattern_clean = pattern.rstrip("/")
                    source_s3_uri = f"s3://{bucket_name}/{s3_prefix}{pattern_clean}/"
                    target_path = target_dir / pattern_clean
                    target_path.mkdir(parents=True, exist_ok=True)

                    # Use AWS CLI sync
                    cmd = [
                        "aws",
                        "s3",
                        "sync",
                        source_s3_uri,
                        str(target_path),
                        "--exclude",
                        "*.pyc",
                        "--exclude",
                        "__pycache__/*",
                        "--exclude",
                        ".ipynb_checkpoints/*",
                    ]

                    result = subprocess.run(cmd, capture_output=True, text=True)

                    if result.returncode == 0:
                        # Count downloaded files from output
                        lines = (
                            result.stdout.strip().split("\n")
                            if result.stdout.strip()
                            else []
                        )
                        pattern_files = len(
                            [line for line in lines if "download:" in line]
                        )
                        downloaded_files += pattern_files

                        # Show downloaded files
                        for line in lines:
                            if "download:" in line:
                                # Extract relative path from AWS CLI output
                                parts = line.split(" to ")
                                if len(parts) > 1:
                                    local_path = parts[1]
                                    relative_path = os.path.relpath(
                                        local_path, str(target_dir)
                                    )
                                    typer.echo(f"  Downloaded: {relative_path}")
                    else:
                        typer.echo(
                            f"  Error syncing {pattern_clean}: {result.stderr}",
                            err=True,
                        )
        else:
            # No include patterns - sync everything
            source_s3_uri = f"s3://{bucket_name}/{s3_prefix}"

            cmd = [
                "aws",
                "s3",
                "sync",
                source_s3_uri,
                str(target_dir),
                "--exclude",
                "*.pyc",
                "--exclude",
                "__pycache__/*",
                "--exclude",
                ".ipynb_checkpoints/*",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                lines = (
                    result.stdout.strip().split("\n") if result.stdout.strip() else []
                )
                downloaded_files = len([line for line in lines if "download:" in line])

                for line in lines:
                    if "download:" in line:
                        parts = line.split(" to ")
                        if len(parts) > 1:
                            local_path = parts[1]
                            relative_path = os.path.relpath(local_path, str(target_dir))
                            typer.echo(f"  Downloaded: {relative_path}")
            else:
                typer.echo(f"  Error syncing: {result.stderr}", err=True)

    except Exception as e:
        typer.echo(f"Error downloading S3 files: {str(e)}", err=True)

    return downloaded_files


def clone_git_repository(git_config, temp_bundle_dir):
    """Clone Git repository with timeout protection."""
    import subprocess

    repository_name = git_config.get("repository", "unknown")
    git_url = git_config.get("url")
    target_dir = git_config.get("targetDir", "./src")

    if not git_url:
        typer.echo(f"⚠️  No Git URL specified for repository {repository_name}")
        return 0

    typer.echo(f"Cloning Git repository: {repository_name}")

    # Create target directory in temp bundle
    git_target_path = Path(temp_bundle_dir) / target_dir.lstrip("./")
    git_target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Use subprocess with timeout
        result = subprocess.run(
            ["git", "clone", "--depth", "1", git_url, str(git_target_path)],
            timeout=60,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            # Count files in cloned repository
            file_count = sum(1 for _ in git_target_path.rglob("*") if _.is_file())
            typer.echo(f"  Cloned {file_count} files from Git repository")
            return file_count
        else:
            typer.echo(f"Error cloning Git repository: {result.stderr}", err=True)
            return 0

    except subprocess.TimeoutExpired:
        typer.echo(
            f"Git clone timeout (60s) for repository {repository_name}", err=True
        )
        return 0
    except Exception as e:
        typer.echo(f"Error cloning Git repository: {str(e)}", err=True)
        return 0

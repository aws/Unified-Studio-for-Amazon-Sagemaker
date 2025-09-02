"""Bundle storage helper functions for local and S3 storage."""

import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse
import boto3
from .s3 import create_s3_client


def is_s3_url(path: str) -> bool:
    """Check if path is an S3 URL."""
    return path.startswith("s3://")


def parse_s3_url(s3_url: str) -> Tuple[str, str]:
    """Parse S3 URL into bucket and key."""
    parsed = urlparse(s3_url)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    return bucket, key


def get_bundle_path(bundles_directory: str, pipeline_name: str) -> str:
    """Get the full path to the bundle file."""
    bundle_filename = f"{pipeline_name}.zip"

    if is_s3_url(bundles_directory):
        # For S3, join with forward slash
        return f"{bundles_directory.rstrip('/')}/{bundle_filename}"
    else:
        # For local, use os.path.join
        return os.path.join(bundles_directory, bundle_filename)


def ensure_bundle_directory_exists(bundles_directory: str, region: str = None) -> None:
    """Ensure bundle directory exists (create if local, validate if S3)."""
    if is_s3_url(bundles_directory):
        # For S3, just validate the bucket exists
        bucket, _ = parse_s3_url(bundles_directory)
        s3_client = create_s3_client(region=region)
        try:
            s3_client.head_bucket(Bucket=bucket)
        except Exception as e:
            raise ValueError(f"S3 bucket '{bucket}' not accessible: {e}")
    else:
        # For local, create directory
        os.makedirs(bundles_directory, exist_ok=True)


def upload_bundle(
    local_bundle_path: str,
    bundles_directory: str,
    pipeline_name: str,
    region: str = None,
) -> str:
    """Upload bundle to storage location and return the final path."""
    if is_s3_url(bundles_directory):
        # Upload to S3
        bucket, prefix = parse_s3_url(bundles_directory)
        bundle_filename = f"{pipeline_name}.zip"
        s3_key = f"{prefix}/{bundle_filename}" if prefix else bundle_filename

        s3_client = create_s3_client(region=region)
        s3_client.upload_file(local_bundle_path, bucket, s3_key)

        return f"s3://{bucket}/{s3_key}"
    else:
        # Move to local directory
        bundle_filename = f"{pipeline_name}.zip"
        final_path = os.path.join(bundles_directory, bundle_filename)

        # If source and destination are different, move the file
        if os.path.abspath(local_bundle_path) != os.path.abspath(final_path):
            import shutil

            shutil.move(local_bundle_path, final_path)

        return final_path


def download_bundle(bundle_path: str, region: str = None) -> str:
    """Download bundle from storage location to a temporary file and return local path."""
    if is_s3_url(bundle_path):
        # Download from S3 to temporary file
        bucket, key = parse_s3_url(bundle_path)

        # Create temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix=".zip", prefix="smus_bundle_")
        os.close(temp_fd)  # Close the file descriptor, we just need the path

        s3_client = create_s3_client(region=region)
        s3_client.download_file(bucket, key, temp_path)

        return temp_path
    else:
        # Return local path as-is
        if not os.path.exists(bundle_path):
            raise FileNotFoundError(f"Bundle file not found: {bundle_path}")
        return bundle_path


def find_bundle_file(
    bundles_directory: str, pipeline_name: str, region: str = None
) -> Optional[str]:
    """Find the bundle file for the pipeline in the storage location."""
    if is_s3_url(bundles_directory):
        # Search in S3
        bucket, prefix = parse_s3_url(bundles_directory)
        s3_client = create_s3_client(region=region)

        try:
            # List objects with the prefix
            response = s3_client.list_objects_v2(
                Bucket=bucket, Prefix=prefix + "/" if prefix else "", MaxKeys=100
            )

            if "Contents" not in response:
                return None

            # Look for bundle file matching pipeline name
            for obj in response["Contents"]:
                key = obj["Key"]
                filename = os.path.basename(key)
                if (
                    filename.endswith(".zip")
                    and pipeline_name.lower() in filename.lower()
                ):
                    return f"s3://{bucket}/{key}"

            # Fallback to any zip file
            for obj in response["Contents"]:
                key = obj["Key"]
                filename = os.path.basename(key)
                if filename.endswith(".zip"):
                    return f"s3://{bucket}/{key}"

        except Exception:
            return None
    else:
        # Search locally
        if not os.path.exists(bundles_directory):
            return None

        # Look for bundle file matching pipeline name
        for file in os.listdir(bundles_directory):
            if file.endswith(".zip") and pipeline_name.lower() in file.lower():
                return os.path.join(bundles_directory, file)

        # Fallback to any zip file
        for file in os.listdir(bundles_directory):
            if file.endswith(".zip"):
                return os.path.join(bundles_directory, file)

    return None

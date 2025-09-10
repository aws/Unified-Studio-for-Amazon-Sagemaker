"""S3 helper functions."""

from typing import Any, Dict, List

from . import boto3_client


def upload_file(
    local_file_path: str,
    bucket_name: str,
    s3_key: str,
    connection_info: Dict[str, Any] = None,
    region: str = None,
) -> bool:
    """Upload a file to S3."""
    try:
        s3_client = boto3_client.create_client("s3", connection_info, region)
        s3_client.upload_file(local_file_path, bucket_name, s3_key)
        return True
    except Exception:
        return False


def list_objects(
    bucket_name: str,
    prefix: str,
    connection_info: Dict[str, Any] = None,
    region: str = None,
) -> List[Dict[str, Any]]:
    """List objects in S3 bucket with given prefix."""
    try:
        s3_client = boto3_client.create_client("s3", connection_info, region)
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

        objects = []
        for page in pages:
            if "Contents" in page:
                objects.extend(page["Contents"])

        return objects
    except Exception:
        return []


def delete_objects(
    bucket_name: str,
    object_keys: List[str],
    connection_info: Dict[str, Any] = None,
    region: str = None,
) -> bool:
    """Delete multiple objects from S3."""
    try:
        if not object_keys:
            return True

        s3_client = boto3_client.create_client("s3", connection_info, region)
        objects_to_delete = [{"Key": key} for key in object_keys]

        s3_client.delete_objects(
            Bucket=bucket_name, Delete={"Objects": objects_to_delete}
        )
        return True
    except Exception:
        return False


def create_s3_client(connection_info: Dict[str, Any] = None, region: str = None):
    """Create S3 client using connection info or region."""
    return boto3_client.create_client("s3", connection_info, region)

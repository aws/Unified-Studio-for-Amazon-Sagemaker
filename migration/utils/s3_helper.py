import boto3
import os


def download_s3_directory_recursive(s3_uri, local_dir):
    # Create the local directory if it doesn't exist
    os.makedirs(local_dir, exist_ok=True)
    # For the given S3 URI, recursively download all files to the local directory
    s3 = boto3.client('s3')
    bucket, key = s3_uri.replace("s3://", "").split("/", 1)
    paginator = s3.get_paginator('list_objects_v2')
    for result in paginator.paginate(Bucket=bucket, Prefix=key):
        if 'Contents' in result:
            for obj in result['Contents']:
                if obj['Key'].endswith('/'):
                    continue
                local_file_path = os.path.join(local_dir, obj['Key'].replace(key, ""))
                os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                s3.download_file(bucket, obj['Key'], local_file_path)
                print(f"Downloaded {obj['Key']} to {local_file_path}")

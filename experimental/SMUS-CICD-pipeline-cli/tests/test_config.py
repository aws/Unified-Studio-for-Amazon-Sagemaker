"""Test configuration using environment variables.

All test files should import from this module instead of hardcoding values.

Environment Variables:
    AWS_REGION: AWS region for tests (default: us-east-2)
    TEST_ACCOUNT_ID: AWS account ID (auto-detected if not set)
    TEST_S3_BUCKET: S3 bucket for test data
    TEST_MLFLOW_ARN: MLflow tracking server ARN
    TEST_WORKFLOW_ARN: Airflow workflow ARN for tests
"""

import os
import boto3


def get_account_id():
    """Get AWS account ID from environment or STS."""
    account_id = os.environ.get('TEST_ACCOUNT_ID')
    if not account_id:
        sts = boto3.client('sts')
        account_id = sts.get_caller_identity()['Account']
    return account_id


def get_region():
    """Get AWS region from environment."""
    return os.environ.get('AWS_REGION', 'us-east-2')


def get_s3_bucket():
    """Get test S3 bucket name."""
    bucket = os.environ.get('TEST_S3_BUCKET')
    if not bucket:
        account_id = get_account_id()
        region = get_region()
        bucket = f"amazon-sagemaker-{account_id}-{region}-test"
    return bucket


def get_s3_uri(path=''):
    """Get S3 URI for test data."""
    bucket = get_s3_bucket()
    if path:
        return f"s3://{bucket}/{path.lstrip('/')}"
    return f"s3://{bucket}/"


def get_mlflow_arn():
    """Get MLflow tracking server ARN."""
    arn = os.environ.get('TEST_MLFLOW_ARN')
    if not arn:
        account_id = get_account_id()
        region = get_region()
        arn = f"arn:aws:sagemaker:{region}:{account_id}:mlflow-tracking-server/test-mlflow"
    return arn


def get_workflow_arn():
    """Get Airflow workflow ARN for tests."""
    arn = os.environ.get('TEST_WORKFLOW_ARN')
    if not arn:
        account_id = get_account_id()
        region = get_region()
        arn = f"arn:aws:airflow-serverless:{region}:{account_id}:workflow/test-workflow"
    return arn


def get_iam_role_arn(role_name):
    """Get IAM role ARN."""
    account_id = get_account_id()
    return f"arn:aws:iam::{account_id}:role/{role_name}"

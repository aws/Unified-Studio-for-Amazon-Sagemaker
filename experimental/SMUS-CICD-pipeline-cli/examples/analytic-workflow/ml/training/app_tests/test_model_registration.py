"""Test that the ML training model artifacts were created."""
import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta, timezone


def test_model_registered():
    """Verify that model artifacts were created in S3 and registered in SageMaker Model Registry."""
    region = os.environ.get("DOMAIN_REGION", "us-east-1")
    s3_client = boto3.client("s3", region_name=region)
    sagemaker_client = boto3.client("sagemaker", region_name=region)
    
    # Check for model artifacts at the expected path
    model_key = "shared/ml/output/model-artifacts/latest/output/model.tar.gz"
    
    # Find the project bucket by checking which one has the model artifacts
    response = s3_client.list_buckets()
    project_bucket = None
    for bucket in response["Buckets"]:
        if "amazon-sagemaker" in bucket["Name"] and region in bucket["Name"]:
            try:
                s3_client.head_object(Bucket=bucket["Name"], Key=model_key)
                project_bucket = bucket["Name"]
                break
            except ClientError:
                continue
    
    assert project_bucket, f"No SageMaker bucket with model artifacts found at {model_key}"
    
    obj = s3_client.head_object(Bucket=project_bucket, Key=model_key)
    last_modified = obj["LastModified"]
    size = obj["ContentLength"]
    
    # Verify model was created recently (within last 2 hours)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=2)
    
    print(f"✓ Model artifact found: s3://{project_bucket}/{model_key}")
    print(f"✓ Last modified: {last_modified}")
    print(f"✓ Size: {size:,} bytes")
    print(f"✓ Region: {region}")
    
    assert last_modified > cutoff_time, f"Model artifact is too old: {last_modified}"
    assert size > 0, "Model artifact is empty"
    
    print(f"✓ Model artifact is recent and valid")
    
    # Verify model is registered in SageMaker Model Registry
    model_groups = sagemaker_client.list_model_package_groups(
        SortBy="CreationTime",
        SortOrder="Descending",
        MaxResults=10
    )
    
    assert len(model_groups["ModelPackageGroupSummaryList"]) > 0, "No model package groups found"
    
    latest_group = model_groups["ModelPackageGroupSummaryList"][0]
    
    model_packages = sagemaker_client.list_model_packages(
        ModelPackageGroupName=latest_group["ModelPackageGroupName"],
        SortBy="CreationTime",
        SortOrder="Descending"
    )
    
    assert len(model_packages["ModelPackageSummaryList"]) > 0, "No models in package group"
    
    latest_model = model_packages["ModelPackageSummaryList"][0]
    model_created = latest_model["CreationTime"]
    
    print(f"✓ Model registered in SageMaker Model Registry")
    print(f"✓ Model Package: {latest_model['ModelPackageArn']}")
    print(f"✓ Created: {model_created}")
    print(f"✓ Status: {latest_model['ModelPackageStatus']}")
    
    assert model_created > cutoff_time, f"Latest model package is too old: {model_created}"
    assert latest_model["ModelPackageStatus"] == "Completed", f"Model status is {latest_model['ModelPackageStatus']}"

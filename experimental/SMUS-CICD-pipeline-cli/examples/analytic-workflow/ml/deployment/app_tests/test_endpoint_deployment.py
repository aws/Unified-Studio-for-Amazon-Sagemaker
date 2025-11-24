"""Test that the ML deployment created a SageMaker inference endpoint."""
import os
import boto3
from datetime import datetime, timedelta, timezone


def test_endpoint_deployed():
    """Verify that a SageMaker inference endpoint was created and is in service."""
    region = os.environ.get("DOMAIN_REGION", "us-east-1")
    sagemaker_client = boto3.client("sagemaker", region_name=region)
    
    # List endpoints with the expected naming pattern
    response = sagemaker_client.list_endpoints(
        NameContains="sagemaker-scikit-learn",
        SortBy="CreationTime",
        SortOrder="Descending",
        MaxResults=10
    )
    
    assert len(response["Endpoints"]) > 0, "No SageMaker endpoints found with pattern 'sagemaker-scikit-learn'"
    
    # Get the most recent endpoint
    latest_endpoint = response["Endpoints"][0]
    endpoint_name = latest_endpoint["EndpointName"]
    
    # Get detailed endpoint information
    endpoint_details = sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
    
    endpoint_status = endpoint_details["EndpointStatus"]
    creation_time = endpoint_details["CreationTime"]
    
    # Verify endpoint was created recently (within last 2 hours)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=2)
    
    print(f"✓ Endpoint found: {endpoint_name}")
    print(f"✓ Status: {endpoint_status}")
    print(f"✓ Created: {creation_time}")
    print(f"✓ Region: {region}")
    print(f"✓ Endpoint ARN: {endpoint_details['EndpointArn']}")
    
    assert creation_time > cutoff_time, f"Endpoint is too old: {creation_time}"
    assert endpoint_status == "InService", f"Endpoint status is {endpoint_status}, expected InService"
    
    # Verify endpoint configuration exists
    endpoint_config_name = endpoint_details["EndpointConfigName"]
    config_details = sagemaker_client.describe_endpoint_config(
        EndpointConfigName=endpoint_config_name
    )
    
    print(f"✓ Endpoint config: {endpoint_config_name}")
    print(f"✓ Production variants: {len(config_details['ProductionVariants'])}")
    
    # Verify at least one production variant
    assert len(config_details["ProductionVariants"]) > 0, "No production variants configured"
    
    variant = config_details["ProductionVariants"][0]
    print(f"✓ Instance type: {variant['InstanceType']}")
    print(f"✓ Initial instance count: {variant['InitialInstanceCount']}")
    print(f"✓ Model name: {variant['ModelName']}")
    
    # Verify the model exists
    model_details = sagemaker_client.describe_model(ModelName=variant["ModelName"])
    print(f"✓ Model ARN: {model_details['ModelArn']}")
    print(f"✓ Execution role: {model_details['ExecutionRoleArn']}")
    
    print(f"\n✅ Endpoint deployment verified successfully")

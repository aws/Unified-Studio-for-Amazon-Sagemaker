"""Test that the ML training model was registered in SageMaker."""
import boto3
from datetime import datetime, timedelta


def test_model_registered():
    """Verify that a model was registered in SageMaker recently."""
    client = boto3.client("sagemaker")
    
    # List models created in the last hour
    cutoff_time = datetime.now() - timedelta(hours=1)
    
    response = client.list_models(
        SortBy="CreationTime",
        SortOrder="Descending",
        MaxResults=10
    )
    
    models = response.get("Models", [])
    assert len(models) > 0, "No models found in SageMaker"
    
    # Check the most recent model
    latest_model = models[0]
    model_name = latest_model["ModelName"]
    creation_time = latest_model["CreationTime"]
    
    # Verify model was created recently (within last hour)
    assert creation_time > cutoff_time, f"Latest model {model_name} is too old: {creation_time}"
    
    print(f"✓ Model registered: {model_name}")
    print(f"✓ Creation time: {creation_time}")

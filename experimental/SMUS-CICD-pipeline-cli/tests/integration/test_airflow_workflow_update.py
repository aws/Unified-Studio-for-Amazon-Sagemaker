"""Test Airflow Serverless workflow update on conflict."""
# TODO: Replace {account_id} placeholders with test_config.get_account_id()
import pytest
from smus_cicd.helpers import airflow_serverless


@pytest.fixture
def workflow_config():
    return {
        "workflow_name": "test-workflow-update-conflict",
        "dag_s3_location": "s3://amazon-sagemaker-{account_id}-us-east-2-5330xnk7amt221/shared/ml/bundle/training-workflows/ml_training_workflow.yaml",
        "role_arn": "arn:aws:iam::{account_id}:role/SMUSCICDTestRole",
        "region": "us-east-2",
        "description": "Test workflow for conflict handling",
    }


def test_workflow_create_then_update(workflow_config):
    """Test that creating a workflow twice updates it instead of failing."""
    
    # First creation
    result1 = airflow_serverless.create_workflow(**workflow_config)
    assert result1["success"] is True
    assert "workflow_arn" in result1
    workflow_arn = result1["workflow_arn"]
    
    # Second creation with same name - should update
    result2 = airflow_serverless.create_workflow(**workflow_config)
    assert result2["success"] is True
    assert result2.get("updated") is True or result2.get("recreated") is True
    assert result2["workflow_arn"] == workflow_arn
    
    # Cleanup
    airflow_serverless.delete_workflow(workflow_arn, region=workflow_config["region"])


def test_workflow_update_with_datazone(workflow_config):
    """Test workflow update when DataZone environment variables are present."""
    
    config_with_datazone = {
        **workflow_config,
        "workflow_name": "test-workflow-update-datazone",
        "datazone_domain_id": "dzd-614fzsz5nulxm1",
        "datazone_project_id": "5330xnk7amt221",
        "datazone_domain_region": "us-east-2",
    }
    
    # First creation
    result1 = airflow_serverless.create_workflow(**config_with_datazone)
    assert result1["success"] is True
    workflow_arn = result1["workflow_arn"]
    
    # Second creation - should delete and recreate due to EnvironmentVariables
    result2 = airflow_serverless.create_workflow(**config_with_datazone)
    assert result2["success"] is True
    assert result2.get("recreated") is True
    
    # Cleanup - workflow ARN changed after recreation
    try:
        airflow_serverless.delete_workflow(result2["workflow_arn"], region=config_with_datazone["region"])
    except Exception:
        pass  # Already deleted

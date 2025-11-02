"""Unit tests for context resolver."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from smus_cicd.helpers.context_resolver import ContextResolver


@patch('smus_cicd.helpers.connections.get_project_connections')
@patch('smus_cicd.helpers.datazone.get_project_user_role_arn')
@patch('smus_cicd.helpers.datazone.get_project_id_by_name')
def test_resolve_env_variables(mock_get_project_id, mock_get_role, mock_get_connections):
    """Test resolving environment variables."""
    mock_get_project_id.return_value = "proj123"
    mock_get_role.return_value = "arn:aws:iam::123:role/TestRole"
    mock_get_connections.return_value = {}
    
    env_vars = {"AWS_REGION": "us-east-1", "S3_PREFIX": "test"}
    resolver = ContextResolver(
        project_name="test-project",
        domain_id="domain456",
        domain_name="test-domain",
        region="us-east-1",
        env_vars=env_vars
    )
    
    content = "Region: {env.AWS_REGION}, Prefix: {env.S3_PREFIX}"
    result = resolver.resolve(content)
    
    assert result == "Region: us-east-1, Prefix: test"


@patch('smus_cicd.helpers.connections.get_project_connections')
@patch('smus_cicd.helpers.datazone.get_project_user_role_arn')
@patch('smus_cicd.helpers.datazone.get_project_id_by_name')
def test_resolve_project_properties(mock_get_project_id, mock_get_role, mock_get_connections):
    """Test resolving project properties."""
    mock_get_project_id.return_value = "proj123"
    mock_get_role.return_value = "arn:aws:iam::123:role/TestRole"
    mock_get_connections.return_value = {}
    
    resolver = ContextResolver(
        project_name="test-project",
        domain_id="domain456",
        domain_name="test-domain",
        region="us-east-1",
        env_vars={}
    )
    
    content = "Project: {proj.name}, Role: {proj.iam_role}, RoleName: {proj.iam_role_name}"
    result = resolver.resolve(content)
    
    assert result == "Project: test-project, Role: arn:aws:iam::123:role/TestRole, RoleName: TestRole"


@patch('smus_cicd.helpers.connections.get_project_connections')
@patch('smus_cicd.helpers.datazone.get_project_user_role_arn')
@patch('smus_cicd.helpers.datazone.get_project_id_by_name')
def test_resolve_connection_properties(mock_get_project_id, mock_get_role, mock_get_connections):
    """Test resolving connection properties."""
    mock_get_project_id.return_value = "proj123"
    mock_get_role.return_value = "arn:aws:iam::123:role/TestRole"
    
    # Mock S3 connection
    mock_get_connections.return_value = {
        "default.s3_shared": {
            "s3Uri": "s3://my-bucket/path/",
            "environmentUserRole": "arn:aws:iam::123:role/S3Role"
        }
    }
    
    resolver = ContextResolver(
        project_name="test-project",
        domain_id="domain456",
        domain_name="test-domain",
        region="us-east-1",
        env_vars={}
    )
    
    content = "S3 Path: {proj.connection.default.s3_shared.s3Uri}"
    result = resolver.resolve(content)
    
    assert result == "S3 Path: s3://my-bucket/path/"


@patch('smus_cicd.helpers.connections.get_project_connections')
@patch('smus_cicd.helpers.datazone.get_project_user_role_arn')
@patch('smus_cicd.helpers.datazone.get_project_id_by_name')
def test_resolve_mlflow_connection(mock_get_project_id, mock_get_role, mock_get_connections):
    """Test resolving MLflow connection properties."""
    mock_get_project_id.return_value = "proj123"
    mock_get_role.return_value = "arn:aws:iam::123:role/TestRole"
    
    # Mock MLflow connection
    mock_get_connections.return_value = {
        "project.mlflow-server.mlflow": {
            "trackingServerArn": "arn:aws:sagemaker:us-east-1:123:mlflow-tracking-server/test",
            "trackingServerName": "test-mlflow",
            "environmentUserRole": "arn:aws:iam::123:role/MLRole"
        }
    }
    
    resolver = ContextResolver(
        project_name="test-project",
        domain_id="domain456",
        domain_name="test-domain",
        region="us-east-1",
        env_vars={}
    )
    
    content = "MLflow ARN: {proj.connection.project.mlflow-server.mlflow.trackingServerArn}"
    result = resolver.resolve(content)
    
    assert result == "MLflow ARN: arn:aws:sagemaker:us-east-1:123:mlflow-tracking-server/test"


@patch('smus_cicd.helpers.connections.get_project_connections')
@patch('smus_cicd.helpers.datazone.get_project_user_role_arn')
@patch('smus_cicd.helpers.datazone.get_project_id_by_name')
def test_resolve_missing_variable(mock_get_project_id, mock_get_role, mock_get_connections):
    """Test that missing variables are left unchanged."""
    mock_get_project_id.return_value = "proj123"
    mock_get_role.return_value = "arn:aws:iam::123:role/TestRole"
    mock_get_connections.return_value = {}
    
    resolver = ContextResolver(
        project_name="test-project",
        domain_id="domain456",
        domain_name="test-domain",
        region="us-east-1",
        env_vars={}
    )
    
    content = "Missing: {env.DOES_NOT_EXIST}"
    result = resolver.resolve(content)
    
    assert result == "Missing: {env.DOES_NOT_EXIST}"


@patch('smus_cicd.helpers.connections.get_project_connections')
@patch('smus_cicd.helpers.datazone.get_project_user_role_arn')
@patch('smus_cicd.helpers.datazone.get_project_id_by_name')
def test_resolve_complex_yaml(mock_get_project_id, mock_get_role, mock_get_connections):
    """Test resolving a complex YAML-like structure."""
    mock_get_project_id.return_value = "proj123"
    mock_get_role.return_value = "arn:aws:iam::123:role/TestRole"
    
    mock_get_connections.return_value = {
        "default.s3_shared": {
            "s3Uri": "s3://my-bucket/",
            "environmentUserRole": "arn:aws:iam::123:role/S3Role"
        }
    }
    
    resolver = ContextResolver(
        project_name="test-project",
        domain_id="domain456",
        domain_name="test-domain",
        region="us-east-1",
        env_vars={"AWS_REGION": "us-east-1"}
    )
    
    content = """
    script_location: '{proj.connection.default.s3_shared.s3Uri}etl/script.py'
    iam_role_name: '{proj.iam_role}'
    region_name: '{env.AWS_REGION}'
    """
    
    result = resolver.resolve(content)
    
    assert "s3://my-bucket/etl/script.py" in result
    assert "arn:aws:iam::123:role/TestRole" in result
    assert "us-east-1" in result

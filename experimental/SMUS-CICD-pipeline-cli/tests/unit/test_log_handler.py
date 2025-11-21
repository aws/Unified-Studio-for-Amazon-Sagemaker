"""Unit tests for log handler."""

import pytest
from unittest.mock import patch
from smus_cicd.bootstrap.handlers.log_handler import debug_action
from smus_cicd.bootstrap.models import BootstrapAction


@pytest.fixture
def mock_aws_calls():
    """Mock all AWS API calls."""
    with patch('smus_cicd.helpers.datazone.get_project_id_by_name') as mock_proj_id, \
         patch('smus_cicd.helpers.datazone.get_project_user_role_arn') as mock_role, \
         patch('smus_cicd.helpers.connections.get_project_connections') as mock_conns:
        
        mock_proj_id.return_value = "proj123"
        mock_role.return_value = "arn:aws:iam::123:role/TestRole"
        mock_conns.return_value = {
            "default.s3_shared": {
                "s3Uri": "s3://test-bucket/shared/"
            }
        }
        
        yield


def test_log_debug_simple_variable(mock_aws_calls):
    """Test log.debug with simple variable."""
    action = BootstrapAction(
        type="log.debug",
        parameters={"message": "Project: {proj.name}"}
    )
    
    context = {
        "project_name": "test-project",
        "domain_id": "domain123",
        "domain_name": "test-domain",
        "region": "us-east-1",
        "stage_name": "dev",
        "env_vars": {}
    }
    
    result = debug_action(action, context)
    
    assert result["status"] == "success"
    assert result["original"] == "Project: {proj.name}"
    assert result["resolved"] == "Project: test-project"


def test_log_debug_connection_variable(mock_aws_calls):
    """Test log.debug with connection variable."""
    action = BootstrapAction(
        type="log.debug",
        parameters={"message": "Bucket: {proj.connection.default.s3_shared.s3Uri}"}
    )
    
    context = {
        "project_name": "test-project",
        "domain_id": "domain123",
        "domain_name": "test-domain",
        "region": "us-east-1",
        "stage_name": "dev",
        "env_vars": {}
    }
    
    result = debug_action(action, context)
    
    assert result["status"] == "success"
    assert result["resolved"] == "Bucket: s3://test-bucket/shared/"


def test_log_debug_multiple_variables(mock_aws_calls):
    """Test log.debug with multiple variables."""
    action = BootstrapAction(
        type="log.debug",
        parameters={
            "message": "Project: {proj.name}, Stage: {stage.name}, Bucket: {proj.connection.default.s3_shared.s3Uri}"
        }
    )
    
    context = {
        "project_name": "test-project",
        "domain_id": "domain123",
        "domain_name": "test-domain",
        "region": "us-east-1",
        "stage_name": "dev",
        "env_vars": {}
    }
    
    result = debug_action(action, context)
    
    assert result["status"] == "success"
    assert "test-project" in result["resolved"]
    assert "dev" in result["resolved"]
    assert "s3://test-bucket/shared/" in result["resolved"]


def test_log_debug_empty_message(mock_aws_calls):
    """Test log.debug with empty message."""
    action = BootstrapAction(
        type="log.debug",
        parameters={}
    )
    
    context = {
        "project_name": "test-project",
        "domain_id": "domain123",
        "domain_name": "test-domain",
        "region": "us-east-1",
        "env_vars": {}
    }
    
    result = debug_action(action, context)
    
    assert result["status"] == "success"
    assert result["message"] == ""

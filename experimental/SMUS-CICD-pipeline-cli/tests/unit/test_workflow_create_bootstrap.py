"""Unit tests for workflow.create bootstrap action."""

import pytest
from unittest.mock import MagicMock, patch

from smus_cicd.bootstrap.handlers.workflow_create_handler import handle_workflow_create
from smus_cicd.bootstrap.models import BootstrapAction


@pytest.fixture
def mock_action():
    """Mock bootstrap action."""
    action = MagicMock(spec=BootstrapAction)
    action.parameters = {}
    return action


@pytest.fixture
def mock_context():
    """Mock execution context."""
    manifest = MagicMock()
    manifest.application_name = "TestApp"
    manifest.content.workflows = [
        {"workflowName": "test_workflow", "connectionName": "default.workflow_serverless"}
    ]
    
    target_config = MagicMock()
    target_config.project.name = "test-project"
    target_config.domain.name = "test-domain"
    
    return {
        "manifest": manifest,
        "target_config": target_config,
        "config": {"region": "us-east-1", "stage_name": "test"},
        "metadata": {
            "project_info": {
                "project_id": "project-123",
                "domain_id": "domain-123",
            },
            "s3_bucket": "test-bucket",
            "s3_prefix": "test-prefix",
            "bundle_path": None,
        },
    }


def test_handle_workflow_create_no_workflows(mock_action):
    """Test workflow.create with no workflows in manifest."""
    manifest = MagicMock()
    manifest.content.workflows = None
    
    context = {
        "manifest": manifest,
        "target_config": MagicMock(),
        "config": {"region": "us-east-1"},
        "metadata": {},
    }
    
    result = handle_workflow_create(mock_action, context)
    
    assert result is True


def test_handle_workflow_create_missing_s3_location(mock_action, mock_context):
    """Test workflow.create fails without S3 location."""
    mock_context["metadata"] = {}  # No S3 location
    
    result = handle_workflow_create(mock_action, mock_context)
    
    assert result is False


def test_handle_workflow_create_missing_project_info(mock_action, mock_context):
    """Test workflow.create fails without project info."""
    mock_context["metadata"]["project_info"] = {}  # No project_id/domain_id
    
    result = handle_workflow_create(mock_action, mock_context)
    
    assert result is False


def test_handle_workflow_create_specific_workflow(mock_action, mock_context):
    """Test workflow.create with specific workflow name."""
    mock_action.parameters = {"workflowName": "test_workflow"}
    
    with patch("smus_cicd.bootstrap.handlers.workflow_create_handler.datazone") as mock_dz:
        mock_dz.get_project_user_role_arn.return_value = "arn:aws:iam::123:role/test"
        
        with patch("smus_cicd.commands.deploy._find_dag_files_in_s3") as mock_find:
            mock_find.return_value = []  # No DAG files
            
            result = handle_workflow_create(mock_action, mock_context)
            
            # Verify get_project_user_role_arn called with domain_name, not domain_id
            mock_dz.get_project_user_role_arn.assert_called_once_with(
                "test-project",
                "test-domain",  # Should be domain_name from target_config.domain.name
                "us-east-1"
            )
            
            assert result is True


def test_handle_workflow_create_role_lookup_failure(mock_action, mock_context):
    """Test workflow.create fails when project user role not found."""
    with patch("smus_cicd.bootstrap.handlers.workflow_create_handler.datazone") as mock_dz:
        mock_dz.get_project_user_role_arn.return_value = None  # Role not found
        
        result = handle_workflow_create(mock_action, mock_context)
        
        # Should fail when role not found
        assert result is False
        
        # Verify it was called with correct parameters
        mock_dz.get_project_user_role_arn.assert_called_once_with(
            "test-project",
            "test-domain",
            "us-east-1"
        )


def test_handle_workflow_create_workflow_not_found(mock_action, mock_context):
    """Test workflow.create with non-existent workflow name."""
    mock_action.parameters = {"workflowName": "nonexistent_workflow"}
    
    result = handle_workflow_create(mock_action, mock_context)
    
    assert result is False

"""Unit tests for workflow.create bootstrap action."""

import pytest
from unittest.mock import MagicMock, patch

from smus_cicd.bootstrap.handlers.workflow_create_handler import handle_workflow_create


@pytest.fixture
def mock_manifest():
    """Mock manifest with workflows."""
    manifest = MagicMock()
    manifest.application_name = "TestApp"
    manifest.content.workflows = [
        {"workflowName": "test_workflow", "connectionName": "default.workflow_serverless"}
    ]
    return manifest


@pytest.fixture
def mock_target_config():
    """Mock target configuration."""
    config = MagicMock()
    config.project.name = "test-project"
    config.domain.name = "test-domain"
    config.domain.tags = {}
    config.environment_variables = {}
    return config


@pytest.fixture
def mock_config():
    """Mock deployment configuration."""
    return {
        "region": "us-east-1",
        "stage_name": "test",
    }


@pytest.fixture
def mock_metadata():
    """Mock metadata with S3 location."""
    return {
        "s3_bucket": "test-bucket",
        "s3_prefix": "test-prefix",
        "bundle_path": None,
    }


def test_handle_workflow_create_no_workflows(mock_target_config, mock_config):
    """Test workflow.create with no workflows in manifest."""
    manifest = MagicMock()
    manifest.content.workflows = None
    
    action = {}
    
    result = handle_workflow_create(
        action, mock_target_config, mock_config, manifest
    )
    
    assert result is True


def test_handle_workflow_create_missing_s3_location(
    mock_manifest, mock_target_config, mock_config
):
    """Test workflow.create fails without S3 location."""
    action = {}
    metadata = {}  # No S3 location
    
    result = handle_workflow_create(
        action, mock_target_config, mock_config, mock_manifest, metadata=metadata
    )
    
    assert result is False


def test_handle_workflow_create_specific_workflow(
    mock_manifest, mock_target_config, mock_config, mock_metadata
):
    """Test workflow.create with specific workflow name."""
    action = {"workflowName": "test_workflow"}
    
    with patch("smus_cicd.bootstrap.handlers.workflow_create_handler.resolve_domain_id") as mock_resolve:
        mock_resolve.return_value = ("domain-123", "test-domain")
        
        with patch("smus_cicd.bootstrap.handlers.workflow_create_handler.datazone") as mock_dz:
            mock_dz.get_project_user_role_arn.return_value = "arn:aws:iam::123:role/test"
            mock_dz.get_project_id_by_name.return_value = "project-123"
            
            with patch("smus_cicd.commands.deploy._find_dag_files_in_s3") as mock_find:
                mock_find.return_value = []  # No DAG files
                
                result = handle_workflow_create(
                    action, mock_target_config, mock_config, mock_manifest, metadata=mock_metadata
                )
                
                assert result is True


def test_handle_workflow_create_workflow_not_found(
    mock_manifest, mock_target_config, mock_config, mock_metadata
):
    """Test workflow.create with non-existent workflow name."""
    action = {"workflowName": "nonexistent_workflow"}
    
    result = handle_workflow_create(
        action, mock_target_config, mock_config, mock_manifest, metadata=mock_metadata
    )
    
    assert result is False

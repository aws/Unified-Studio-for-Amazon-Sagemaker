"""
Unit test to reproduce the IAM role name resolution issue.

This test verifies that {proj.iam_role_name} variables are correctly resolved
in workflow YAML files.
"""

import pytest
from unittest.mock import Mock, patch
from smus_cicd.helpers.context_resolver import ContextResolver


def test_iam_role_name_resolution():
    """Test that {proj.iam_role_name} is correctly resolved to the role name."""
    
    # Mock the datazone module functions
    with patch('smus_cicd.helpers.datazone.get_project_id_by_name') as mock_get_project_id, \
         patch('smus_cicd.helpers.datazone.get_project_user_role_arn') as mock_get_role_arn, \
         patch('smus_cicd.helpers.connections.get_project_connections') as mock_get_connections:
        
        # Setup mocks
        mock_get_project_id.return_value = "test-project-id"
        mock_get_role_arn.return_value = "arn:aws:iam::123456789:role/service-role/AmazonSageMakerUserIAMExecutionRole"
        mock_get_connections.return_value = {}
        
        # Create resolver
        resolver = ContextResolver(
            project_name="test-project",
            domain_id="test-domain-id",
            region="us-east-1",
            domain_name="test-domain",
            stage_name="test",
            env_vars={}
        )
        
        # Test YAML content with {proj.iam_role_name} variable
        yaml_content = """
workflow_combined:
  dag_id: 'test_workflow'
  tasks:
    test_task:
      operator: airflow.providers.amazon.aws.operators.glue.GlueJobOperator
      iam_role_name: '{proj.iam_role_name}'
      region_name: '{domain.region}'
"""
        
        # Resolve variables
        resolved_content = resolver.resolve(yaml_content)
        
        # Verify the role name was resolved correctly
        assert "AmazonSageMakerUserIAMExecutionRole" in resolved_content, \
            f"Expected 'AmazonSageMakerUserIAMExecutionRole' in resolved content, got:\n{resolved_content}"
        
        # Verify the placeholder was replaced
        assert "{proj.iam_role_name}" not in resolved_content, \
            f"Variable placeholder still present in resolved content:\n{resolved_content}"
        
        # Verify no hardcoded test role
        assert "SMUSCICDTestRole" not in resolved_content, \
            f"Hardcoded test role found in resolved content:\n{resolved_content}"
        
        print("✅ Test passed: IAM role name correctly resolved")
        print(f"Resolved content:\n{resolved_content}")


def test_context_has_correct_iam_role_name():
    """Test that the context is built with the correct iam_role_name."""
    
    with patch('smus_cicd.helpers.datazone.get_project_id_by_name') as mock_get_project_id, \
         patch('smus_cicd.helpers.datazone.get_project_user_role_arn') as mock_get_role_arn, \
         patch('smus_cicd.helpers.connections.get_project_connections') as mock_get_connections:
        
        # Setup mocks
        mock_get_project_id.return_value = "test-project-id"
        mock_get_role_arn.return_value = "arn:aws:iam::123456789:role/service-role/AmazonSageMakerUserIAMExecutionRole"
        mock_get_connections.return_value = {}
        
        # Create resolver
        resolver = ContextResolver(
            project_name="test-project",
            domain_id="test-domain-id",
            region="us-east-1",
            domain_name="test-domain",
            stage_name="test",
            env_vars={}
        )
        
        # Build context
        context = resolver._build_context()
        
        # Verify context has correct values
        assert context['proj']['iam_role_name'] == "AmazonSageMakerUserIAMExecutionRole", \
            f"Expected 'AmazonSageMakerUserIAMExecutionRole', got: {context['proj'].get('iam_role_name')}"
        
        assert context['proj']['iam_role_arn'] == "arn:aws:iam::123456789:role/service-role/AmazonSageMakerUserIAMExecutionRole", \
            f"Expected full ARN, got: {context['proj'].get('iam_role_arn')}"
        
        print("✅ Test passed: Context has correct IAM role name")
        print(f"Context proj.iam_role_name: {context['proj']['iam_role_name']}")


if __name__ == "__main__":
    print("Running IAM role name resolution tests...\n")
    test_context_has_correct_iam_role_name()
    print()
    test_iam_role_name_resolution()

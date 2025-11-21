"""Comprehensive tests for all documented variable substitutions."""

import pytest
from unittest.mock import patch
from smus_cicd.helpers.context_resolver import ContextResolver


@pytest.fixture
def mock_aws_calls():
    """Mock all AWS API calls."""
    with patch('smus_cicd.helpers.datazone.get_project_id_by_name') as mock_proj_id, \
         patch('smus_cicd.helpers.datazone.get_project_user_role_arn') as mock_role, \
         patch('smus_cicd.helpers.connections.get_project_connections') as mock_conns:
        
        mock_proj_id.return_value = "5vqwb22pn2da5j"
        mock_role.return_value = "arn:aws:iam::123456789012:role/ProjectRole"
        mock_conns.return_value = {}
        
        yield {
            'mock_proj_id': mock_proj_id,
            'mock_role': mock_role,
            'mock_conns': mock_conns
        }


def test_env_variables(mock_aws_calls):
    """Test environment variable substitutions."""
    env_vars = {
        "AWS_REGION": "us-east-1",
        "S3_PREFIX": "test",
        "CUSTOM_VAR": "value123"
    }
    
    resolver = ContextResolver(
        project_name="test-project",
        domain_id="dzd-abc123",
        domain_name="test-domain",
        region="us-east-1",
        env_vars=env_vars
    )
    
    # Test single env var
    assert resolver.resolve("{env.AWS_REGION}") == "us-east-1"
    assert resolver.resolve("{env.S3_PREFIX}") == "test"
    assert resolver.resolve("{env.CUSTOM_VAR}") == "value123"
    
    # Test multiple env vars
    result = resolver.resolve("Region: {env.AWS_REGION}, Prefix: {env.S3_PREFIX}")
    assert result == "Region: us-east-1, Prefix: test"


def test_stage_properties(mock_aws_calls):
    """Test stage property substitutions."""
    resolver = ContextResolver(
        project_name="test-project",
        domain_id="dzd-abc123",
        domain_name="test-domain",
        region="us-east-1",
        stage_name="dev",
        env_vars={}
    )
    
    assert resolver.resolve("{stage.name}") == "dev"
    assert resolver.resolve("env-{stage.name}") == "env-dev"


def test_project_properties(mock_aws_calls):
    """Test all project property substitutions from docs."""
    resolver = ContextResolver(
        project_name="test-marketing",
        domain_id="dzd-5b6m4h6c1yfch3",
        domain_name="test-domain",
        region="us-east-1",
        env_vars={}
    )
    
    # {proj.id}
    assert resolver.resolve("{proj.id}") == "5vqwb22pn2da5j"
    
    # {proj.name}
    assert resolver.resolve("{proj.name}") == "test-marketing"
    
    # {proj.domain_id}
    assert resolver.resolve("{proj.domain_id}") == "dzd-5b6m4h6c1yfch3"
    
    # {proj.iam_role} and {proj.iam_role_arn}
    expected_role = "arn:aws:iam::123456789012:role/ProjectRole"
    assert resolver.resolve("{proj.iam_role}") == expected_role
    assert resolver.resolve("{proj.iam_role_arn}") == expected_role
    
    # {proj.iam_role_name}
    assert resolver.resolve("{proj.iam_role_name}") == "ProjectRole"


def test_domain_properties(mock_aws_calls):
    """Test all domain property substitutions from docs."""
    resolver = ContextResolver(
        project_name="test-project",
        domain_id="dzd-5b6m4h6c1yfch3",
        domain_name="MyDomain",
        region="us-east-1",
        env_vars={}
    )
    
    # {domain.id}
    assert resolver.resolve("{domain.id}") == "dzd-5b6m4h6c1yfch3"
    
    # {domain.name}
    assert resolver.resolve("{domain.name}") == "MyDomain"
    
    # {domain.region}
    assert resolver.resolve("{domain.region}") == "us-east-1"


def test_s3_shared_connection(mock_aws_calls):
    """Test S3 shared connection substitutions from docs."""
    mock_aws_calls['mock_conns'].return_value = {
        "default.s3_shared": {
            "s3Uri": "s3://my-bucket/shared/",
            "bucket_name": "my-bucket",
            "environmentUserRole": "arn:aws:iam::123:role/S3Role"
        }
    }
    
    resolver = ContextResolver(
        project_name="test-project",
        domain_id="dzd-abc",
        domain_name="test-domain",
        region="us-east-1",
        env_vars={}
    )
    
    # {proj.connection.default.s3_shared.s3Uri}
    assert resolver.resolve("{proj.connection.default.s3_shared.s3Uri}") == "s3://my-bucket/shared/"
    
    # {proj.connection.default.s3_shared.bucket_name}
    assert resolver.resolve("{proj.connection.default.s3_shared.bucket_name}") == "my-bucket"
    
    # {proj.connection.default.s3_shared.environmentUserRole}
    assert resolver.resolve("{proj.connection.default.s3_shared.environmentUserRole}") == "arn:aws:iam::123:role/S3Role"


def test_spark_connection(mock_aws_calls):
    """Test Spark connection substitutions from docs."""
    mock_aws_calls['mock_conns'].return_value = {
        "default.spark": {
            "sparkGlueProperties": {
                "glueVersion": "4.0",
                "workerType": "G.1X",
                "numberOfWorkers": "10"
            }
        }
    }
    
    resolver = ContextResolver(
        project_name="test-project",
        domain_id="dzd-abc",
        domain_name="test-domain",
        region="us-east-1",
        env_vars={}
    )
    
    # {proj.connection.default.spark.glueVersion}
    assert resolver.resolve("{proj.connection.default.spark.glueVersion}") == "4.0"
    
    # {proj.connection.default.spark.workerType}
    assert resolver.resolve("{proj.connection.default.spark.workerType}") == "G.1X"
    
    # {proj.connection.default.spark.numberOfWorkers}
    assert resolver.resolve("{proj.connection.default.spark.numberOfWorkers}") == "10"


def test_athena_connection(mock_aws_calls):
    """Test Athena connection substitutions from docs."""
    mock_aws_calls['mock_conns'].return_value = {
        "default.sql": {
            "workgroupName": "sagemaker-studio-workgroup-abc"
        }
    }
    
    resolver = ContextResolver(
        project_name="test-project",
        domain_id="dzd-abc",
        domain_name="test-domain",
        region="us-east-1",
        env_vars={}
    )
    
    # {proj.connection.default.sql.workgroupName}
    assert resolver.resolve("{proj.connection.default.sql.workgroupName}") == "sagemaker-studio-workgroup-abc"


def test_mlflow_connection(mock_aws_calls):
    """Test MLflow connection substitutions from docs."""
    mock_aws_calls['mock_conns'].return_value = {
        "project.mlflow-server.mlflow": {
            "trackingServerArn": "arn:aws:sagemaker:us-east-1:123:mlflow-tracking-server/my-server",
            "trackingServerName": "my-mlflow-server"
        }
    }
    
    resolver = ContextResolver(
        project_name="test-project",
        domain_id="dzd-abc",
        domain_name="test-domain",
        region="us-east-1",
        env_vars={}
    )
    
    # {proj.connection.project.mlflow-server.mlflow.trackingServerArn}
    result = resolver.resolve("{proj.connection.project.mlflow-server.mlflow.trackingServerArn}")
    assert result == "arn:aws:sagemaker:us-east-1:123:mlflow-tracking-server/my-server"
    
    # {proj.connection.project.mlflow-server.mlflow.trackingServerName}
    result = resolver.resolve("{proj.connection.project.mlflow-server.mlflow.trackingServerName}")
    assert result == "my-mlflow-server"


def test_complex_workflow_yaml(mock_aws_calls):
    """Test complex workflow YAML with multiple substitutions."""
    mock_aws_calls['mock_conns'].return_value = {
        "default.s3_shared": {
            "s3Uri": "s3://my-bucket/shared/",
        },
        "default.spark": {
            "sparkGlueProperties": {
                "glueVersion": "4.0"
            }
        }
    }
    
    resolver = ContextResolver(
        project_name="test-project",
        domain_id="dzd-abc",
        domain_name="test-domain",
        region="us-east-1",
        stage_name="dev",
        env_vars={"AWS_REGION": "us-east-1"}
    )
    
    yaml_content = """
    tasks:
      process_data:
        script_location: '{proj.connection.default.s3_shared.s3Uri}scripts/process.py'
        iam_role_name: '{proj.iam_role_name}'
        region_name: '{env.AWS_REGION}'
        create_job_kwargs:
          GlueVersion: '{proj.connection.default.spark.glueVersion}'
          Tags:
            Environment: '{stage.name}'
    """
    
    result = resolver.resolve(yaml_content)
    
    assert "s3://my-bucket/shared/scripts/process.py" in result
    assert "ProjectRole" in result
    assert "us-east-1" in result
    assert "4.0" in result
    assert "dev" in result


def test_connection_with_dots_in_name(mock_aws_calls):
    """Test connections with dots in their names."""
    mock_aws_calls['mock_conns'].return_value = {
        "mlflow-server": {
            "trackingServerArn": "arn:aws:sagemaker:us-east-1:123:mlflow-tracking-server/test"
        }
    }
    
    resolver = ContextResolver(
        project_name="test-project",
        domain_id="dzd-abc",
        domain_name="test-domain",
        region="us-east-1",
        env_vars={}
    )
    
    # Connection name with hyphen
    result = resolver.resolve("{proj.connection.mlflow-server.trackingServerArn}")
    assert result == "arn:aws:sagemaker:us-east-1:123:mlflow-tracking-server/test"


def test_s3_bucket_extraction_from_uri(mock_aws_calls):
    """Test automatic bucket extraction from s3Uri."""
    mock_aws_calls['mock_conns'].return_value = {
        "default.s3_shared": {
            "s3Uri": "s3://my-bucket/path/to/data/"
        }
    }
    
    resolver = ContextResolver(
        project_name="test-project",
        domain_id="dzd-abc",
        domain_name="test-domain",
        region="us-east-1",
        env_vars={}
    )
    
    # Should extract bucket name from s3Uri
    result = resolver.resolve("{proj.connection.default.s3_shared.bucket}")
    assert result == "my-bucket"

"""Integration tests for pipeline project validation."""
import os
import pytest
import yaml
from pathlib import Path
from smus_cicd.helpers.utils import load_config, get_datazone_project_info


def _load_test_config():
    """Load integration test configuration."""
    config_path = Path(__file__).parent.parent.parent / "config.local.yaml"
    if not config_path.exists():
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def test_environment_variables_available():
    """Test that required configuration is available from config.yaml."""
    test_config = _load_test_config()
    
    # Check that test configuration has required fields
    assert 'test_environment' in test_config, "test_environment should be in config"
    assert 'domain_name' in test_config['test_environment'], "domain_name should be in test_environment"
    assert 'project_prefix' in test_config['test_environment'], "project_prefix should be in test_environment"
    
    # Check AWS configuration
    assert 'aws' in test_config, "aws configuration should be present"
    assert 'region' in test_config['aws'], "aws.region should be configured"
    
    domain_name = test_config['test_environment']['domain_name']
    project_prefix = test_config['test_environment']['project_prefix']
    region = test_config['aws']['region']
    
    # Test environment variables that would be available during test execution
    # These are set by the test framework, not necessarily in the config file
    print("Environment variables available during test:")
    print(f"SMUS_DOMAIN_ID: {os.environ.get('SMUS_DOMAIN_ID', 'Not set')}")
    print(f"SMUS_PROJECT_ID: {os.environ.get('SMUS_PROJECT_ID', 'Not set')}")
    
    assert domain_name, "Domain name should not be empty"
    assert project_prefix, "Project prefix should not be empty"
    assert region in ['us-east-1', 'us-west-2', 'eu-west-1'], f"Region {region} should be valid"


def test_project_context():
    """Test project context information from config."""
    test_config = _load_test_config()
    
    domain_name = test_config['test_environment']['domain_name']
    project_prefix = test_config['test_environment']['project_prefix']
    region = test_config['aws']['region']
    
    # Basic validation
    assert domain_name, "Domain name should not be empty"
    assert project_prefix, "Project prefix should not be empty"
    assert region in ['us-east-1', 'us-west-2', 'eu-west-1'], f"Region {region} should be valid"
    
    # Test project naming convention
    test_project_name = f"{project_prefix}-test"
    assert 'test' in test_project_name.lower(), "Test project should have test in name"


def test_domain_and_project_ids():
    """Test that domain and project can be resolved from config."""
    test_config = _load_test_config()
    
    domain_name = test_config['test_environment']['domain_name']
    project_prefix = test_config['test_environment']['project_prefix']
    
    # Basic format validation
    assert len(domain_name) > 0, "Domain name should not be empty"
    assert len(project_prefix) > 0, "Project prefix should not be empty"
    
    # Test that we can construct valid project names
    test_project_name = f"{project_prefix}-test"
    assert len(test_project_name) <= 64, "Project name should be within length limits"
    assert test_project_name.replace('-', '').replace('_', '').isalnum(), "Project name should be alphanumeric with dashes/underscores"


@pytest.mark.slow
def test_aws_connectivity():
    """Test AWS connectivity (marked as slow test)."""
    import boto3
    from botocore.exceptions import ClientError
    
    test_config = _load_test_config()
    region = test_config['aws']['region']
    
    try:
        # Test basic AWS connectivity
        sts = boto3.client('sts', region_name=region)
        identity = sts.get_caller_identity()
        
        assert 'Account' in identity, "Should be able to get AWS account info"
        assert 'UserId' in identity, "Should be able to get AWS user info"
        
        # Test DataZone connectivity (this might fail if no access, which is expected)
        try:
            datazone = boto3.client('datazone', region_name=region)
            domains = datazone.list_domains(maxResults=1)
            print(f"✅ DataZone access available, found {len(domains.get('items', []))} domains")
        except ClientError as e:
            if 'AccessDenied' in str(e) or 'UnauthorizedOperation' in str(e):
                print("⚠️ DataZone access denied (expected if no permissions)")
            else:
                print(f"⚠️ DataZone error: {e}")
                
    except ClientError as e:
        if 'InvalidUserID.NotFound' in str(e):
            pytest.fail("AWS credentials not configured properly")
        else:
            pytest.fail(f"AWS connectivity failed: {e}")
        
    except ClientError as e:
        pytest.skip(f"AWS connectivity test skipped: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error in AWS connectivity test: {e}")

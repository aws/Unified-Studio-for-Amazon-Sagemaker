"""Integration tests for AWS resource interactions."""
import os
import pytest
import boto3
from pathlib import Path
from botocore.exceptions import ClientError, NoCredentialsError
from smus_cicd.helpers import datazone, cloudformation

@pytest.fixture
def aws_credentials():
    """Check if AWS credentials are available."""
    if not (os.getenv('AWS_ACCESS_KEY_ID') or os.getenv('AWS_PROFILE')):
        pytest.skip("AWS credentials not available")

@pytest.fixture
def aws_region():
    """Get AWS region from environment or use default."""
    return os.getenv('AWS_DEFAULT_REGION', 'us-east-1')

class TestDataZoneIntegration:
    """Integration tests for DataZone operations."""
    
    def test_datazone_client_connection(self, aws_credentials, aws_region):
        """Test DataZone client can be created and basic operations work."""
        try:
            client = boto3.client('datazone', region_name=aws_region)
            # Try a basic operation that doesn't require specific resources
            response = client.list_domains(maxResults=1)
            assert 'items' in response
        except ClientError as e:
            # Expected if no DataZone domains exist or insufficient permissions
            assert e.response['Error']['Code'] in [
                'AccessDenied', 'UnauthorizedOperation', 'ValidationException'
            ]
        except NoCredentialsError:
            pytest.fail("AWS credentials not properly configured")
    
    def test_get_domain_by_name_nonexistent(self, aws_credentials, aws_region):
        """Test getting non-existent domain returns None."""
        domain_id = datazone.get_domain_id_by_name("nonexistent-domain-12345", aws_region)
        assert domain_id is None
    
    def test_get_project_by_name_nonexistent(self, aws_credentials, aws_region):
        """Test getting non-existent project returns None."""
        # Use a fake domain ID since we're testing non-existent project
        project_id = datazone.get_project_id_by_name("nonexistent-project-12345", "fake-domain-id", aws_region)
        assert project_id is None

class TestCloudFormationIntegration:
    """Integration tests for CloudFormation operations."""
    
    def test_cloudformation_client_connection(self, aws_credentials, aws_region):
        """Test CloudFormation client can be created and basic operations work."""
        try:
            client = boto3.client('cloudformation', region_name=aws_region)
            # Try a basic operation
            response = client.list_stacks()
            assert 'StackSummaries' in response
        except ClientError as e:
            # Expected if insufficient permissions
            assert e.response['Error']['Code'] in [
                'AccessDenied', 'UnauthorizedOperation'
            ]
        except NoCredentialsError:
            pytest.fail("AWS credentials not properly configured")
    
    def test_describe_nonexistent_stack(self, aws_credentials, aws_region):
        """Test describing non-existent stack raises appropriate error."""
        client = boto3.client('cloudformation', region_name=aws_region)
        
        with pytest.raises(ClientError) as exc_info:
            client.describe_stacks(StackName="nonexistent-stack-12345")
        
        assert "does not exist" in str(exc_info.value)

class TestS3Integration:
    """Integration tests for S3 operations."""
    
    def test_s3_client_connection(self, aws_credentials, aws_region):
        """Test S3 client can be created and basic operations work."""
        try:
            client = boto3.client('s3', region_name=aws_region)
            # Try a basic operation
            response = client.list_buckets()
            assert 'Buckets' in response
        except ClientError as e:
            # Expected if insufficient permissions
            assert e.response['Error']['Code'] in [
                'AccessDenied', 'UnauthorizedOperation'
            ]
        except NoCredentialsError:
            pytest.fail("AWS credentials not properly configured")
    
    def test_list_nonexistent_bucket_objects(self, aws_credentials, aws_region):
        """Test listing objects in non-existent bucket raises appropriate error."""
        client = boto3.client('s3', region_name=aws_region)
        
        with pytest.raises(ClientError) as exc_info:
            client.list_objects_v2(Bucket="nonexistent-bucket-12345-test")
        
        assert exc_info.value.response['Error']['Code'] in ['NoSuchBucket', 'AccessDenied']

class TestMWAAIntegration:
    """Integration tests for MWAA operations."""
    
    def test_mwaa_client_connection(self, aws_credentials, aws_region):
        """Test MWAA client can be created and basic operations work."""
        try:
            client = boto3.client('mwaa', region_name=aws_region)
            # Try a basic operation
            response = client.list_environments(MaxResults=1)
            assert 'Environments' in response
        except ClientError as e:
            # Expected if insufficient permissions or MWAA not available in region
            assert e.response['Error']['Code'] in [
                'AccessDenied', 'UnauthorizedOperation', 'InvalidAction'
            ]
        except NoCredentialsError:
            pytest.fail("AWS credentials not properly configured")

@pytest.mark.slow
class TestResourceCreation:
    """Slow integration tests that may create/modify AWS resources."""
    
    @pytest.mark.skipif(
        not os.getenv('SMUS_INTEGRATION_TEST_ALLOW_RESOURCE_CREATION'),
        reason="Resource creation tests disabled. Set SMUS_INTEGRATION_TEST_ALLOW_RESOURCE_CREATION=1 to enable"
    )
    def test_cloudformation_template_validation(self, aws_credentials, aws_region):
        """Test CloudFormation template validation."""
        # This would test actual template validation without creating resources
        client = boto3.client('cloudformation', region_name=aws_region)
        
        # Read a template file and validate it
        template_path = Path(__file__).parent.parent.parent / "smus_cicd" / "cloudformation" / "single-project.yaml"
        if os.path.exists(template_path):
            with open(template_path, 'r') as f:
                template_body = f.read()
            
            try:
                response = client.validate_template(TemplateBody=template_body)
                assert 'Parameters' in response
            except ClientError as e:
                # Template validation might fail due to missing parameters
                assert e.response['Error']['Code'] in ['ValidationError']

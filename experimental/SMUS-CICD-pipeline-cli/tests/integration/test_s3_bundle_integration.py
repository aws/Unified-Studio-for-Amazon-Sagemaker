"""Integration test for S3 bundle storage with DataZone domain bucket."""
import os
import tempfile
import pytest
from src.smus_cicd.helpers.bundle_storage import (
    get_bundle_path,
    ensure_bundle_directory_exists,
    upload_bundle,
    find_bundle_file
)


class TestS3BundleIntegration:
    """Integration tests for S3 bundle storage using DataZone domain bucket."""
    
    @pytest.fixture
    def datazone_s3_bucket(self):
        """Get DataZone domain S3 bucket for testing.
        
        This uses the standard DataZone S3 bucket naming pattern:
        sagemaker-unified-studio-{account-id}-{region}-{domain-name}
        """
        # Example DataZone domain bucket with bundles prefix
        return "s3://sagemaker-unified-studio-<aws-account-id>-us-east-1-test-domain/bundles"
    
    def test_s3_bundle_path_generation(self, datazone_s3_bucket):
        """Test S3 bundle path generation with DataZone bucket."""
        bundle_path = get_bundle_path(datazone_s3_bucket, "MarketingPipeline")
        expected = f"{datazone_s3_bucket}/MarketingPipeline.zip"
        assert bundle_path == expected
        
        # Test with trailing slash
        bundle_path = get_bundle_path(f"{datazone_s3_bucket}/", "MarketingPipeline")
        assert bundle_path == expected
    
    @pytest.mark.skip(reason="Requires actual AWS credentials and DataZone setup")
    def test_s3_bundle_workflow_live(self, datazone_s3_bucket):
        """Test complete S3 bundle workflow with live DataZone bucket.
        
        This test is skipped by default as it requires:
        1. Valid AWS credentials
        2. Access to a DataZone domain S3 bucket
        3. S3 read/write permissions
        
        To run this test:
        1. Set up AWS credentials
        2. Replace the bucket name with your actual DataZone domain bucket
        3. Remove the @pytest.mark.skip decorator
        """
        region = "us-east-1"
        pipeline_name = "TestS3Pipeline"
        
        # Step 1: Ensure bucket exists and is accessible
        ensure_bundle_directory_exists(datazone_s3_bucket, region)
        
        # Step 2: Create a test bundle
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
            temp_file.write(b"Test bundle content for S3 storage")
            temp_file.flush()
            
            try:
                # Step 3: Upload bundle to S3
                s3_bundle_path = upload_bundle(
                    temp_file.name,
                    datazone_s3_bucket,
                    pipeline_name,
                    region
                )
                
                expected_s3_path = f"{datazone_s3_bucket}/{pipeline_name}.zip"
                assert s3_bundle_path == expected_s3_path
                
                # Step 4: Verify bundle can be found
                found_bundle = find_bundle_file(datazone_s3_bucket, pipeline_name, region)
                assert found_bundle == expected_s3_path
                
                print(f"✅ Successfully tested S3 bundle workflow with: {s3_bundle_path}")
                
            finally:
                # Clean up local temp file
                os.unlink(temp_file.name)
    
    def test_datazone_bucket_format_validation(self):
        """Test DataZone S3 bucket format validation."""
        # Valid DataZone bucket formats
        valid_buckets = [
            "s3://sagemaker-unified-studio-<aws-account-id>-us-east-1-my-domain/bundles",
            "s3://sagemaker-unified-studio-<aws-account-id-2>-eu-west-1-test-domain/bundles",
            "s3://sagemaker-unified-studio-<aws-account-id-3>-ap-southeast-2-prod-domain/bundles"
        ]
        
        for bucket in valid_buckets:
            bundle_path = get_bundle_path(bucket, "TestPipeline")
            assert bundle_path.startswith(bucket.rstrip('/'))
            assert bundle_path.endswith("TestPipeline.zip")
    
    def test_s3_bundle_configuration_example(self):
        """Test example pipeline configuration with S3 bundle storage."""
        # Example pipeline manifest configuration
        pipeline_config = {
            "pipelineName": "MarketingDataPipeline",
            "bundlesDirectory": "s3://sagemaker-unified-studio-<aws-account-id>-us-east-1-marketing-domain/bundles",
            "domain": {
                "name": "marketing-domain",
                "region": "us-east-1"
            },
            "targets": {
                "dev": {
                    "project": {"name": "marketing-dev"}
                },
                "prod": {
                    "project": {"name": "marketing-prod"}
                }
            }
        }
        
        # Test bundle path generation
        bundles_dir = pipeline_config["bundlesDirectory"]
        pipeline_name = pipeline_config["pipelineName"]
        
        bundle_path = get_bundle_path(bundles_dir, pipeline_name)
        expected = f"{bundles_dir}/MarketingDataPipeline.zip"
        assert bundle_path == expected
        
        # Verify it's recognized as S3 URL
        from src.smus_cicd.helpers.bundle_storage import is_s3_url
        assert is_s3_url(bundles_dir)
        
        print(f"✅ S3 bundle configuration validated: {bundle_path}")


# Example usage in pipeline manifest
EXAMPLE_PIPELINE_WITH_S3_BUNDLES = """
pipelineName: MarketingDataPipeline
bundlesDirectory: s3://sagemaker-unified-studio-<aws-account-id>-us-east-1-marketing-domain/bundles

domain:
  name: marketing-domain
  region: us-east-1

bundle:
  workflow:
    - connectionName: default.s3_shared
      append: true
      include: ['workflows/']
  storage:
    - connectionName: default.s3_shared
      append: false
      include: ['src/']

targets:
  dev:
    default: true
    project:
      name: marketing-dev
  
  prod:
    project:
      name: marketing-prod
    bundle_target_configuration:
      storage:
        connectionName: default.s3_shared
        directory: 'src'
      workflows:
        connectionName: default.s3_shared
        directory: 'workflows'
"""

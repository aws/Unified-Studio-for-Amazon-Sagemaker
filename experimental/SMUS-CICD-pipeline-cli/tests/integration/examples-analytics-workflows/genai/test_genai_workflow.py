"""Integration test for GenAI workflow deployment."""

import pytest
import os
import subprocess
import re
from tests.integration.base import IntegrationTestBase


class TestGenAIWorkflow(IntegrationTestBase):
    """Test GenAI workflow deployment."""

    def setup_method(self, method):
        """Set up test environment."""
        super().setup_method(method)
        self.setup_test_directory()

    def teardown_method(self, method):
        """Clean up test environment."""
        super().teardown_method(method)
        self.cleanup_resources()
        self.cleanup_test_directory()

    def get_pipeline_file(self):
        return os.path.join(
            os.path.dirname(__file__),
            "../../../../examples/analytic-workflow/genai/manifest.yaml"
        )

    @pytest.mark.integration
    def test_genai_workflow_deployment(self):
        """Test GenAI workflow deployment following basic_pipeline pattern."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()
        workflow_name = "genai_dev_workflow"

        # Step 1: Describe --connect
        self.logger.info("\n=== Step 1: Describe with Connections ===")
        result = self.run_cli_command(["describe", "--manifest", pipeline_file, "--connect"])
        assert result["success"], f"Describe --connect failed: {result['output']}"
        self.logger.info("✅ Describe --connect successful")

        # Step 2: Clean S3 target location before deployment
        self.logger.info("\n=== Step 2: Clean S3 Target Location ===")
        describe_result = self.run_cli_command(["describe", "--manifest", pipeline_file, "--connect"])
        test_s3_uri_match = re.search(
            r"test: test-[\w-]+.*?default\.s3_shared:.*?s3Uri: (s3://[^\s]+)",
            describe_result["output"],
            re.DOTALL
        )
        if test_s3_uri_match:
            test_s3_uri = test_s3_uri_match.group(1).rstrip('/')
            s3_target = f"{test_s3_uri}/genai/bundle/"
            self.logger.info(f"🧹 Cleaning S3 location: {s3_target}")
            cleanup_cmd = ["aws", "s3", "rm", s3_target, "--recursive"]
            cleanup_result = subprocess.run(cleanup_cmd, capture_output=True, text=True)
            if cleanup_result.returncode == 0:
                self.logger.info(f"✅ S3 cleanup successful: {cleanup_result.stdout}")
            else:
                self.logger.info(f"⚠️ S3 cleanup warning: {cleanup_result.stderr}")
        else:
            self.logger.info("⚠️ Could not determine S3 URI for cleanup")

        # Step 3: Deploy directly from local filesystem (no upload or bundle needed)
        # Bootstrap action will auto-trigger workflow and wait for completion
        self.logger.info("\n=== Step 3: Deploy (Direct from Local) ===")
        result = self.run_cli_command(["deploy", "test", "--manifest", pipeline_file])
        assert result["success"], f"Deploy failed: {result['output']}"
        self.logger.info("✅ Deploy successful (bootstrap triggered workflow)")

        # Step 4: Get workflow ARN and run_id from deploy output
        self.logger.info("\n=== Step 4: Extract Workflow Info ===")
        expected_name = 'IntegrationTestGenAIWorkflow_test_marketing_genai_dev_workflow'
        workflow_arn = self.get_workflow_arn(expected_name)
        self.logger.info(f"✅ Workflow ARN: {workflow_arn}")

        # Extract run_id from deploy output (bootstrap logs)
        run_id_match = re.search(r"(?:run_id[=:]\s*)([a-zA-Z0-9]+)", result["output"])
        run_id = run_id_match.group(1) if run_id_match else None
        
        self.logger.info(f"🔍 DEBUG: Extracted run_id={run_id}")
        
        # Assert workflow run started after test began
        if run_id and workflow_arn:
            self.assert_workflow_run_after_test_start(run_id, workflow_arn)
        
        self.logger.info("✅ Workflow completed successfully")

        # Step 5: Download and validate notebooks
        self.logger.info("\n=== Step 5: Download and Validate Notebooks ===")
        
        # Extract S3 bucket from test project (not dev)
        describe_result = self.run_cli_command(["describe", "--manifest", pipeline_file, "--connect"])
        test_s3_uri_match = re.search(
            r"test: test-[\w-]+.*?default\.s3_shared:.*?s3Uri: (s3://[^\s]+)",
            describe_result["output"],
            re.DOTALL
        )
        
        self.logger.info(f"🔍 DEBUG: run_id={run_id}")
        self.logger.info(f"🔍 DEBUG: test_s3_uri_match={'Found' if test_s3_uri_match else 'Not found'}")
        if not test_s3_uri_match:
            self.logger.info(f"🔍 DEBUG: Describe output length: {len(describe_result['output'])}")
            # Show a snippet to see the format
            if 'test: test-' in describe_result['output']:
                self.logger.info("🔍 DEBUG: 'test:' project found in output")
            else:
                self.logger.info("🔍 DEBUG: 'test:' project NOT found in output")
        
        if test_s3_uri_match and run_id:
            test_s3_uri = test_s3_uri_match.group(1)
            s3_bucket = re.search(r"s3://([^/]+)", test_s3_uri).group(1)
            
            # Wait for S3 propagation
            import time
            self.logger.info("⏳ Waiting 10s for S3 propagation...")
            time.sleep(10)
            
            notebooks_valid = self.download_and_validate_notebooks(
                
                workflow_arn=workflow_arn,
                run_id=run_id
            )
            assert notebooks_valid, "Output notebooks contain errors or were not found"
            self.logger.info("✅ All output notebooks validated successfully")
        else:
            self.logger.info("❌ Could not determine S3 bucket or run_id")
            assert False, "Could not determine S3 bucket or run_id for notebook validation"
        
        # Step 6: Check final workflow status
        self.logger.info("\n=== Step 6: Verify Final Workflow Status ===")
        if run_id:
            self.verify_workflow_status(workflow_arn, run_id)
        else:
            pytest.fail("Could not retrieve run_id for status verification")

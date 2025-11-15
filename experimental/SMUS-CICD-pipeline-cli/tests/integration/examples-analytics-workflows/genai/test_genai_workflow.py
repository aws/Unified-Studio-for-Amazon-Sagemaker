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
        print("\n=== Step 1: Describe with Connections ===")
        result = self.run_cli_command(["describe", "--manifest", pipeline_file, "--connect"])
        assert result["success"], f"Describe --connect failed: {result['output']}"
        print("✅ Describe --connect successful")

        # Step 2: Upload GenAI code to S3 (dev project)
        print("\n=== Step 2: Upload GenAI Code to S3 (dev project) ===")
        genai_dir = os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            "../../../../examples/analytic-workflow/genai"
        ))
        self.upload_code_to_dev_project(
            pipeline_file=pipeline_file,
            source_dir=genai_dir,
            target_prefix="genai/"
        )

        # Step 3: Bundle from dev
        print("\n=== Step 3: Bundle from dev ===")
        result = self.run_cli_command(["bundle", "--manifest", pipeline_file, "--target", "dev"])
        assert result["success"], f"Bundle failed: {result['output']}"
        print("✅ Bundle successful")

        # Step 3.5: Check for active workflow runs - fail if any exist
        print("\n=== Step 3.5: Check for Active Workflow Runs ===")
        expected_name = 'IntegrationTestGenAIWorkflow_test_marketing_genai_dev_workflow'
        try:
            workflow_arn = self.get_workflow_arn(expected_name)
            active_runs = self.check_active_workflow_runs(workflow_arn)
            if active_runs:
                pytest.fail(f"❌ Found {len(active_runs)} active workflow run(s) from previous test: {active_runs}. Clean up before running tests.")
            print("✅ No active workflow runs found")
        except AssertionError:
            print("✅ Workflow doesn't exist yet (first run)")


        # Step 4: Deploy
        print("\n=== Step 4: Deploy ===")
        result = self.run_cli_command(["deploy", "test", "--manifest", pipeline_file])
        assert result["success"], f"Deploy failed: {result['output']}"
        print("✅ Deploy successful")

        # Step 5: Monitor
        print("\n=== Step 5: Monitor ===")
        result = self.run_cli_command(["monitor", "--targets", "test", "--manifest", pipeline_file])
        assert result["success"], f"Monitor failed: {result['output']}"
        print("✅ Monitor successful")

        # Step 6: Run workflow
        print("\n=== Step 6: Run Workflow ===")
        result = self.run_cli_command(
            ["run", "--workflow", workflow_name, "--targets", "test", "--manifest", pipeline_file]
        )
        assert result["success"], f"Run workflow failed: {result['output']}"
        print("✅ Workflow started")

        # Step 7: Get workflow ARN
        print("\n=== Step 7: Get Workflow ARN ===")
        expected_name = 'IntegrationTestGenAIWorkflow_test_marketing_genai_dev_workflow'
        workflow_arn = self.get_workflow_arn(expected_name)
        print(f"✅ Workflow ARN: {workflow_arn}")


        # Step 8: Fetch workflow logs and wait for completion
        print("\n=== Step 8: Fetch Workflow Logs and Wait ===")
        result = self.run_cli_command(
            ["logs", "--live", "--workflow", workflow_arn]
        )
        workflow_succeeded = result["success"]
        
        # Extract run_id from logs output - match pattern like "Run: dyo4EXeWXjVP4nd"
        run_id_match = re.search(r"Run:\s+([a-zA-Z0-9]+)", result["output"])
        run_id = run_id_match.group(1) if run_id_match else None
        
        if workflow_succeeded:
            print("✅ Workflow completed successfully")
        else:
            print(f"⚠️ Workflow failed: {result['output']}")

        # Step 9: Download and validate notebooks
        print("\n=== Step 9: Download and Validate Notebooks ===")
        
        # Extract S3 bucket from test project (not dev)
        describe_result = self.run_cli_command(["describe", "--manifest", pipeline_file, "--connect"])
        test_s3_uri_match = re.search(
            r"test: test-marketing.*?default\.s3_shared:.*?s3Uri: (s3://[^\s]+)",
            describe_result["output"],
            re.DOTALL
        )
        
        if test_s3_uri_match and run_id:
            test_s3_uri = test_s3_uri_match.group(1)
            s3_bucket = re.search(r"s3://([^/]+)", test_s3_uri).group(1)
            
            # Wait for S3 propagation
            import time
            print("⏳ Waiting 10s for S3 propagation...")
            time.sleep(10)
            
            notebooks_valid = self.download_and_validate_notebooks(
                
                workflow_arn=workflow_arn,
                run_id=run_id
            )
            assert notebooks_valid, "Output notebooks contain errors or were not found"
            print("✅ All output notebooks validated successfully")
        else:
            print("❌ Could not determine S3 bucket or run_id")
            assert False, "Could not determine S3 bucket or run_id for notebook validation"
        
        # Step 10: Check final workflow status
        print("\n=== Step 10: Verify Final Workflow Status ===")
        if run_id:
            self.verify_workflow_status(workflow_arn, run_id)
        else:
            pytest.fail("Could not retrieve run_id for status verification")

"""
Integration test for parallel notebook execution workflow.
Tests deployment and execution of 9 example notebooks in parallel.
"""
import pytest
import os
import re
import subprocess
from tests.integration.base import IntegrationTestBase


class TestNotebooksWorkflow(IntegrationTestBase):
    
    def get_pipeline_file(self):
        return os.path.join(
            os.path.dirname(__file__),
            "../../../../examples/analytic-workflow/data-notebooks/notebooks_bundle.yaml"
        )
    
    def test_notebooks_workflow_deployment(self):
        """Test complete notebook workflow deployment and execution."""
        
        pipeline_file = self.get_pipeline_file()
        
        # Step 1: Describe with connections
        print("\n=== Step 1: Describe with Connections ===")
        result = self.run_cli_command(["describe", "--bundle", pipeline_file, "--connect"])
        assert result["success"], f"Describe failed: {result['output']}"
        print("✅ Describe successful")
        
        # Step 2: Upload notebooks to S3 (dev project - must already exist)
        print("\n=== Step 2: Upload Notebooks to S3 (dev project) ===")
        s3_uri_match = re.search(
            r"dev: dev-marketing.*?default\.s3_shared:.*?s3Uri: (s3://[^\s]+)",
            result["output"],
            re.DOTALL
        )
        
        if s3_uri_match:
            s3_uri = s3_uri_match.group(1)
            notebooks_dir = os.path.join(
                os.path.dirname(__file__),
                "../../../../examples/analytic-workflow/data-notebooks"
            )
            
            if os.path.exists(notebooks_dir):
                self.sync_to_s3(
                    notebooks_dir,
                    s3_uri,
                    exclude_patterns=[
                        "*.pyc",
                        "__pycache__/*",
                        ".ipynb_checkpoints/*",
                        "*_bundle.yaml",
                        "*.md",
                        "pipeline_tests/*"
                    ]
                )
        else:
            print("⚠️ Could not extract S3 URI from describe output")
        
        # Step 3: Bundle from dev
        print("\n=== Step 3: Bundle from dev ===")
        result = self.run_cli_command(["bundle", "--bundle", pipeline_file, "--target", "dev"])
        assert result["success"], f"Bundle failed: {result['output']}"
        print("✅ Bundle successful")
        
        # Step 4: Deploy to test target
        print("\n=== Step 4: Deploy to test ===")
        result = self.run_cli_command(["deploy", "test", "--bundle", pipeline_file])
        assert result["success"], f"Deploy failed: {result['output']}"
        print("✅ Deploy successful")
        
        # Step 5: Run workflow
        print("\n=== Step 5: Run Workflow ===")
        result = self.run_cli_command(
            ["run", "--workflow", "parallel_notebooks_workflow", "--targets", "test", "--bundle", pipeline_file]
        )
        assert result["success"], f"Run workflow failed: {result['output']}"
        
        # Extract workflow ARN
        arn_match = re.search(r'🔗 ARN: (arn:aws:airflow-serverless:[^\s]+)', result["output"])
        assert arn_match, "Could not find workflow ARN in output"
        workflow_arn = arn_match.group(1)
        print(f"📋 Workflow ARN: {workflow_arn}")
        
        # Step 6: Stream logs and wait for completion
        print("\n=== Step 6: Stream Logs ===")
        result = self.run_cli_command(["logs", "--live", "--workflow", workflow_arn])
        assert result["success"], f"Logs streaming failed: {result['output']}"
        print("✅ Workflow completed")
        
        # Step 7: Run pipeline tests to validate all notebooks succeeded
        print("\n=== Step 7: Run Pipeline Tests ===")
        result = self.run_cli_command(["test", "--targets", "test", "--test-output", "console", "--bundle", pipeline_file])
        assert result["success"], f"Pipeline tests failed: {result['output']}"
        print("✅ All tests passed")

        # Step 8: Download and validate notebooks
        print("\n=== Step 8: Download and Validate Notebooks ===")
        if s3_uri_match:
            s3_bucket = s3_uri_match.group(1).replace("s3://", "").split("/")[0]
            notebooks_valid = self.download_and_validate_notebooks(s3_bucket)
            assert notebooks_valid, "Notebook validation failed - errors found in notebook outputs"
            print("✅ Notebooks validated successfully")
        else:
            print("⚠️ Skipping notebook validation - S3 bucket not found")

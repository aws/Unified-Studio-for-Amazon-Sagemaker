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
            "../../../../examples/analytic-workflow/data-notebooks/manifest.yaml"
        )
    
    def test_notebooks_workflow_deployment(self):
        """Test complete notebook workflow deployment and execution."""
        
        pipeline_file = self.get_pipeline_file()
        
        # Step 1: Describe with connections
        print("\n=== Step 1: Describe with Connections ===")
        result = self.run_cli_command(["describe", "--manifest", pipeline_file, "--connect"])
        assert result["success"], f"Describe failed: {result['output']}"
        print("✅ Describe successful")
        
        # Step 2: Upload notebooks to S3 (dev project - must already exist)
        print("\n=== Step 2: Upload Notebooks to S3 (dev project) ===")
        notebooks_dir = os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            "../../../../examples/analytic-workflow/data-notebooks"
        ))
        self.upload_code_to_dev_project(
            pipeline_file=pipeline_file,
            source_dir=notebooks_dir,
            target_prefix="",  # Upload to root of S3 shared
            exclude_patterns=[
                "*.pyc",
                "__pycache__/*",
                ".ipynb_checkpoints/*",
                "*_bundle.yaml",
                "*.md",
                "pipeline_tests/*"
            ]
        )
        
        # Step 3: Bundle from dev
        print("\n=== Step 3: Bundle from dev ===")
        result = self.run_cli_command(["bundle", "--manifest", pipeline_file, "--target", "dev"])
        assert result["success"], f"Bundle failed: {result['output']}"
        print("✅ Bundle successful")
        
        # Step 4: Deploy to test target
        print("\n=== Step 4: Deploy to test ===")
        result = self.run_cli_command(["deploy", "test", "--manifest", pipeline_file])
        assert result["success"], f"Deploy failed: {result['output']}"
        print("✅ Deploy successful")
        
        # Step 5: Run workflow
        print("\n=== Step 5: Run Workflow ===")
        result = self.run_cli_command(
            ["run", "--workflow", "parallel_notebooks_workflow", "--targets", "test", "--manifest", pipeline_file]
        )
        assert result["success"], f"Run workflow failed: {result['output']}"
        
        # Extract workflow ARN
        arn_match = re.search(r'🔗 ARN: (arn:aws:airflow-serverless:[^\s]+)', result["output"])
        assert arn_match, "Could not find workflow ARN in output"
        workflow_arn = arn_match.group(1)
        print(f"📋 Workflow ARN: {workflow_arn}")
        
        # Extract run_id from run command output
        run_id_match = re.search(r'Run ID: ([A-Za-z0-9]+)', result["output"])
        assert run_id_match, "Could not find run ID in run output"
        run_id = run_id_match.group(1)
        print(f"📋 Run ID: {run_id}")
        
        # Step 6: Stream logs and wait for completion
        print("\n=== Step 6: Stream Logs ===")
        result = self.run_cli_command(["logs", "--live", "--workflow", workflow_arn])
        assert result["success"], f"Logs streaming failed: {result['output']}"
        print("✅ Workflow completed")
        
        # Step 7: Run pipeline tests to validate all notebooks succeeded
        print("\n=== Step 7: Run Pipeline Tests ===")
        result = self.run_cli_command(["test", "--targets", "test", "--test-output", "console", "--manifest", pipeline_file])
        assert result["success"], f"Pipeline tests failed: {result['output']}"
        print("✅ All tests passed")

        # Step 8: Download and validate notebooks
        print("\n=== Step 8: Download and Validate Notebooks ===")
        notebooks_valid = self.download_and_validate_notebooks(workflow_arn, run_id)
        assert notebooks_valid, "Notebook validation failed - errors found in notebook outputs"
        print("✅ Notebooks validated successfully")

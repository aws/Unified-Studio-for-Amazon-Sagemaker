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
        self.logger.info("\n=== Step 1: Describe with Connections ===")
        result = self.run_cli_command(["describe", "--manifest", pipeline_file, "--connect"])
        assert result["success"], f"Describe failed: {result['output']}"
        self.logger.info("✅ Describe successful")
        
        # Step 2: Deploy to test (bootstrap auto-runs workflow and waits for completion)
        self.logger.info("\n=== Step 2: Deploy to test (with bootstrap workflow execution) ===")
        result = self.run_cli_command(["deploy", "test", "--manifest", pipeline_file])
        assert result["success"], f"Deploy failed: {result['output']}"
        self.logger.info("✅ Deploy successful")
        
        # Extract workflow info from bootstrap output
        arn_match = re.search(r'🔗 ARN: (arn:aws:airflow-serverless:[^\s]+)', result["output"])
        assert arn_match, "Could not find workflow ARN in output"
        workflow_arn = arn_match.group(1)
        self.logger.info(f"📋 Workflow ARN: {workflow_arn}")
        
        run_id_match = re.search(r'Run ID: ([A-Za-z0-9]+)', result["output"])
        assert run_id_match, "Could not find run ID in output"
        run_id = run_id_match.group(1)
        self.logger.info(f"📋 Run ID: {run_id}")
        
        # Assert workflow run started after test began
        if run_id and workflow_arn:
            self.assert_workflow_run_after_test_start(run_id, workflow_arn)
        
        # Step 3: Run pipeline tests to validate all notebooks succeeded
        self.logger.info("\n=== Step 3: Run Pipeline Tests ===")
        result = self.run_cli_command(["test", "--targets", "test", "--test-output", "console", "--manifest", pipeline_file])
        assert result["success"], f"Pipeline tests failed: {result['output']}"
        self.logger.info("✅ All tests passed")

        # Step 4: Download and validate notebooks
        self.logger.info("\n=== Step 4: Download and Validate Notebooks ===")
        notebooks_valid = self.download_and_validate_notebooks(workflow_arn, run_id)
        assert notebooks_valid, "Notebook validation failed - errors found in notebook outputs"
        self.logger.info("✅ Notebooks validated successfully")

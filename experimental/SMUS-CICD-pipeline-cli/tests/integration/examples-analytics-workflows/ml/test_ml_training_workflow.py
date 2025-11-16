"""Integration test for ML training workflow."""

import pytest
import os
import subprocess
import re
from tests.integration.base import IntegrationTestBase


class TestMLTrainingWorkflow(IntegrationTestBase):
    """Test ML training workflow."""

    def setup_method(self, method):
        """Set up test environment."""
        super().setup_method(method)
        self.setup_test_directory()

    def get_pipeline_file(self):
        return os.path.join(
            os.path.dirname(__file__),
            "../../../../examples/analytic-workflow/ml/training/manifest.yaml"
        )

    @pytest.mark.integration
    def test_ml_training_workflow(self):
        """Test ML training workflow."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()
        workflow_name = "ml_training_workflow"

        # Step 1: Describe --connect
        print("\n=== Step 1: Describe with Connections ===")
        result = self.run_cli_command(["describe", "--manifest", pipeline_file, "--connect"])
        assert result["success"], f"Describe --connect failed: {result['output']}"
        print("✅ Describe --connect successful")

        # Step 2: Upload ML code to S3
        print("\n=== Step 2: Upload ML Code to S3 ===")
        ml_dir = os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            "../../../../examples/analytic-workflow/ml"
        ))
        self.upload_code_to_dev_project(
            pipeline_file=pipeline_file,
            source_dir=ml_dir,
            target_prefix="ml/"
        )

        # Step 3: Bundle
        print("\n=== Step 3: Bundle ===")
        result = self.run_cli_command(["bundle", "--manifest", pipeline_file, "--target", "dev"])
        assert result["success"], f"Bundle failed: {result['output']}"
        print("✅ Bundle successful")

        # Step 4: Deploy
        print("\n=== Step 4: Deploy ===")
        result = self.run_cli_command(["deploy", "test", "--manifest", pipeline_file])
        assert result["success"], f"Deploy failed: {result['output']}"
        print("✅ Deploy successful")

        # Step 5: Run workflow
        print("\n=== Step 5: Run Workflow ===")
        result = self.run_cli_command(
            ["run", "--workflow", workflow_name, "--targets", "test", "--manifest", pipeline_file]
        )
        assert result["success"], f"Run workflow failed: {result['output']}"
        print("✅ Workflow started")

        # Step 6: Get workflow ARN
        print("\n=== Step 6: Get Workflow ARN ===")
        expected_name = 'IntegrationTestMLTraining_test_marketing_ml_training_workflow'
        workflow_arn = self.get_workflow_arn(expected_name)
        print(f"✅ Workflow ARN: {workflow_arn}")


        # Step 7: Wait for completion
        print("\n=== Step 7: Wait for Completion ===")
        result = self.run_cli_command(
            ["logs", "--live", "--workflow", workflow_arn]
        )
        workflow_succeeded = result["success"]
        
        # Extract run_id from logs output - match pattern like "Run: dyo4EXeWXjVP4nd"
        run_id_match = re.search(r"Run:\s+([a-zA-Z0-9]+)", result["output"])
        run_id = run_id_match.group(1) if run_id_match else None
        
        # Assert workflow run started after test began
        if run_id and workflow_arn:
            self.assert_workflow_run_after_test_start(run_id, workflow_arn)
        
        if workflow_succeeded:
            print("✅ Training workflow completed successfully")
        else:
            print(f"⚠️ Workflow failed: {result['output']}")
        
        # Step 8: Download and validate output notebooks (always run, even if workflow failed)
        print("\n=== Step 8: Download and Validate Output Notebooks ===")
        
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
            print("❌ Could not determine run_id")
            assert False, "Could not determine run_id for notebook validation"
        
        # Final assertion - workflow must succeed
        assert workflow_succeeded, "Workflow execution failed"

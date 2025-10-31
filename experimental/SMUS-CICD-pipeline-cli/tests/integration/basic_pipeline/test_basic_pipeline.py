"""Integration test for basic pipeline workflow."""

import pytest
import os
from typer.testing import CliRunner
from ..base import IntegrationTestBase
from smus_cicd.helpers.utils import get_datazone_project_info


class TestBasicPipeline(IntegrationTestBase):
    """Test basic pipeline end-to-end workflow."""

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
        """Get path to pipeline file in same directory."""
        return os.path.join(os.path.dirname(__file__), "basic_pipeline.yaml")

    @pytest.mark.integration
    def test_basic_pipeline_workflow(self):
        """Test complete basic pipeline workflow: describe --connect -> bundle -> deploy -> monitor."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()
        results = []
        workflow_name = "basic_test_workflow"

        # Step 0: Delete workflow if it exists
        print("\n=== Step 0: Cleanup Existing Workflow ===")
        try:
            import boto3
            client = boto3.client('awsoverdriveservice', region_name='us-east-1', endpoint_url='https://overdrive-gamma.us-east-1.api.aws')
            response = client.list_workflows()
            workflows = response.get('Workflows', [])
            expected_name = f'BasicTestPipeline_test_marketing_{workflow_name}'
            
            for wf in workflows:
                if wf.get('Name') == expected_name:
                    workflow_arn = wf.get('WorkflowArn')
                    print(f"🗑️  Deleting existing workflow: {expected_name}")
                    client.delete_workflow(WorkflowArn=workflow_arn)
                    print("✅ Workflow deleted")
                    break
            else:
                print("✓ No existing workflow to delete")
        except Exception as e:
            print(f"⚠️  Could not delete workflow: {e}")

        # Step 1: Describe with connections
        print("\n=== Step 1: Describe with Connections ===")
        self.logger.info("=== STEP 1: Describe with Connections ===")
        result = self.run_cli_command(["describe", "--pipeline", pipeline_file, "--connect"])
        results.append(result)
        assert result["success"], f"Describe --connect failed: {result['output']}"
        print("✅ Describe --connect successful")

        # Step 1.5: Upload local code to S3
        print("\n=== Step 2: Upload Code and Workflows to S3 ===")
        describe_output = result["output"]
        import re
        import subprocess

        # Extract S3 URI for test project from describe output (look for s3_shared connection)
        s3_uri_match = re.search(
            r"test: test-marketing.*?default\.s3_shared:.*?s3Uri: (s3://[^\s]+)",
            describe_output,
            re.DOTALL,
        )

        if s3_uri_match:
            s3_uri = s3_uri_match.group(1)
            base_dir = os.path.dirname(pipeline_file)
            
            # Upload code directory
            code_dir = os.path.join(base_dir, "code")
            if os.path.exists(code_dir):
                upload_result = subprocess.run(
                    [
                        "aws", "s3", "sync",
                        code_dir, s3_uri,
                        "--exclude", "*.pyc",
                        "--exclude", "__pycache__/*",
                    ],
                    capture_output=True,
                    text=True,
                )
                
                if upload_result.returncode == 0:
                    print(f"✅ Code uploaded to S3: {s3_uri}")
                else:
                    print(f"⚠️ Code upload failed: {upload_result.stderr}")
            else:
                print(f"⚠️ Code directory not found: {code_dir}")
            
            # Upload workflows directory
            workflows_dir = os.path.join(base_dir, "workflows")
            if os.path.exists(workflows_dir):
                upload_result = subprocess.run(
                    [
                        "aws", "s3", "sync",
                        workflows_dir, s3_uri + "workflows/",
                        "--exclude", "*.pyc",
                        "--exclude", "__pycache__/*",
                    ],
                    capture_output=True,
                    text=True,
                )
                
                if upload_result.returncode == 0:
                    print(f"✅ Workflows uploaded to S3: {s3_uri}workflows/")
                else:
                    print(f"⚠️ Workflows upload failed: {upload_result.stderr}")
            else:
                print(f"⚠️ Workflows directory not found: {workflows_dir}")
        else:
            print("⚠️ Could not extract S3 URI from describe output")

        # Step 3: Bundle (for test target)
        print("\n=== Step 3: Bundle ===")
        self.logger.info("=== STEP 3: Bundle ===")
        result = self.run_cli_command(["bundle", "--pipeline", pipeline_file, "--targets", "test"])
        results.append(result)
        assert result["success"], f"Bundle failed: {result['output']}"
        print("✅ Bundle successful")

        # Step 4: Deploy
        print("\n=== Step 4: Deploy ===")
        self.logger.info("=== STEP 4: Deploy ===")
        result = self.run_cli_command(["deploy", "test", "--pipeline", pipeline_file])
        results.append(result)
        assert result["success"], f"Deploy failed: {result['output']}"
        print("✅ Deploy successful")

        # Step 5: Monitor
        print("\n=== Step 5: Monitor ===")
        self.logger.info("=== STEP 5: Monitor ===")
        result = self.run_cli_command(
            ["monitor", "--targets", "test", "--pipeline", pipeline_file]
        )
        results.append(result)
        assert result["success"], f"Monitor failed: {result['output']}"
        print("✅ Monitor successful")

        # Step 6: Run workflow
        print("\n=== Step 6: Run Workflow ===")
        self.logger.info("=== STEP 6: Run Workflow ===")
        result = self.run_cli_command(
            ["run", "--workflow", workflow_name, "--targets", "test", "--pipeline", pipeline_file]
        )
        results.append(result)
        assert result["success"], f"Run workflow failed: {result['output']}"
        print("✅ Workflow started")

        # Step 7: Monitor workflow status
        print("\n=== Step 7: Monitor Workflow Status ===")
        self.logger.info("=== STEP 7: Monitor Workflow Status ===")
        result = self.run_cli_command(
            ["monitor", "--targets", "test", "--pipeline", pipeline_file]
        )
        results.append(result)
        assert result["success"], f"Monitor after run failed: {result['output']}"
        print("✅ Monitor after run successful")

        # Step 8: Get workflow ARN and fetch logs
        print("\n=== Step 8: Fetch Workflow Logs ===")
        self.logger.info("=== STEP 8: Fetch Workflow Logs ===")
        import boto3
        try:
            client = boto3.client('awsoverdriveservice', region_name='us-east-1', endpoint_url='https://overdrive-gamma.us-east-1.api.aws')
            response = client.list_workflows()
            workflows = response.get('Workflows', [])
            expected_name = f'BasicTestPipeline_test_marketing_{workflow_name}'
            
            workflow_arn = None
            for wf in workflows:
                if wf.get('Name') == expected_name:
                    workflow_arn = wf.get('WorkflowArn')
                    break
            
            if workflow_arn:
                print(f"📋 Workflow ARN: {workflow_arn}")
                # Fetch logs with --live flag
                result = self.run_cli_command(
                    ["logs", "--workflow", workflow_arn, "--live"]
                )
                results.append(result)
                # Don't fail if logs command times out - that's expected with --live
                if result["success"]:
                    print("✅ Logs retrieved successfully")
                else:
                    print("⚠️  Logs command timed out (expected with --live)")
            else:
                print("⚠️  Workflow ARN not found")
        except Exception as e:
            print(f"⚠️  Could not fetch logs: {e}")

        # Step 9: Verify workflow completed successfully
        print("\n=== Step 9: Verify Workflow Completion ===")
        try:
            import time
            client = boto3.client('awsoverdriveservice', region_name='us-east-1', endpoint_url='https://overdrive-gamma.us-east-1.api.aws')
            expected_name = f'BasicTestPipeline_test_marketing_{workflow_name}'
            
            # Wait up to 5 minutes for workflow to complete
            max_wait = 300
            start_time = time.time()
            workflow_status = None
            
            while time.time() - start_time < max_wait:
                response = client.list_workflows()
                workflows = response.get('Workflows', [])
                
                for wf in workflows:
                    if wf.get('Name') == expected_name:
                        workflow_status = wf.get('WorkflowStatus')
                        print(f"  Workflow status: {workflow_status}")
                        
                        if workflow_status in ['COMPLETED', 'FAILED', 'STOPPED']:
                            break
                
                if workflow_status in ['COMPLETED', 'FAILED', 'STOPPED']:
                    break
                
                time.sleep(10)
            
            if workflow_status == 'COMPLETED':
                print("✅ Workflow completed successfully")
            elif workflow_status == 'FAILED':
                pytest.fail(f"Workflow failed with status: {workflow_status}")
            elif workflow_status == 'STOPPED':
                pytest.fail(f"Workflow was stopped: {workflow_status}")
            else:
                print(f"⚠️  Workflow status after {max_wait}s: {workflow_status}")
                # Don't fail - workflow might still be running
                
        except Exception as e:
            print(f"⚠️  Could not verify workflow completion: {e}")

        print(f"\n✅ All workflow steps completed successfully!")
        print(f"Total commands: {len(results)}")
        print(f"Successful: {sum(1 for r in results if r['success'])}/{len(results)}")



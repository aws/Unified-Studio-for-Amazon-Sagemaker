"""Integration test for ML workflow deployment."""

import pytest
import os
import subprocess
import re
import boto3
from tests.integration.base import IntegrationTestBase


class TestMLWorkflow(IntegrationTestBase):
    """Test ML workflow deployment."""

    def setup_method(self, method):
        """Set up test environment."""
        super().setup_method(method)
        self.setup_test_directory()

    def get_pipeline_file(self):
        return os.path.join(
            os.path.dirname(__file__),
            "../../../../examples/analytic-workflow/ml/ml_pipeline.yaml"
        )

    @pytest.mark.integration
    def test_ml_workflow_deployment(self):
        """Test ML workflow deployment following basic_pipeline pattern."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()
        workflow_name = "ml_dev_workflow_v3"

        # Step 1: Describe --connect
        print("\n=== Step 1: Describe with Connections ===")
        result = self.run_cli_command(["describe", "--pipeline", pipeline_file, "--connect"])
        assert result["success"], f"Describe --connect failed: {result['output']}"
        print("✅ Describe --connect successful")

        # Step 2: Upload ML code to S3 (dev project)
        print("\n=== Step 2: Upload ML Code to S3 (dev project) ===")
        s3_uri_match = re.search(
            r"dev: dev-marketing.*?default\.s3_shared:.*?s3Uri: (s3://[^\s]+)",
            result["output"],
            re.DOTALL
        )
        
        if s3_uri_match:
            s3_uri = s3_uri_match.group(1)
            ml_dir = os.path.join(
                os.path.dirname(__file__),
                "../../../../examples/analytic-workflow/ml"
            )
            
            if os.path.exists(ml_dir):
                upload_result = subprocess.run(
                    [
                        "aws", "s3", "sync",
                        ml_dir, s3_uri + "ml/",
                        "--delete",
                        "--exclude", "*.pyc",
                        "--exclude", "__pycache__/*",
                        "--exclude", ".ipynb_checkpoints/*",
                    ],
                    capture_output=True,
                    text=True
                )
                
                if upload_result.returncode == 0:
                    print(f"✅ ML code uploaded to S3: {s3_uri}ml/")
                else:
                    print(f"⚠️ Upload failed: {upload_result.stderr}")
        else:
            print("⚠️ Could not extract S3 URI from describe output")

        # Step 3: Bundle from dev
        print("\n=== Step 3: Bundle from dev ===")
        result = self.run_cli_command(["bundle", "--pipeline", pipeline_file, "--target", "dev"])
        assert result["success"], f"Bundle failed: {result['output']}"
        print("✅ Bundle successful")

        # Step 4: Deploy
        print("\n=== Step 4: Deploy ===")
        result = self.run_cli_command(["deploy", "test", "--pipeline", pipeline_file])
        assert result["success"], f"Deploy failed: {result['output']}"
        print("✅ Deploy successful")

        # Step 5: Monitor
        print("\n=== Step 5: Monitor ===")
        result = self.run_cli_command(["monitor", "--targets", "test", "--pipeline", pipeline_file])
        assert result["success"], f"Monitor failed: {result['output']}"
        print("✅ Monitor successful")

        # Step 6: Run workflow
        print("\n=== Step 6: Run Workflow ===")
        result = self.run_cli_command(
            ["run", "--workflow", workflow_name, "--targets", "test", "--pipeline", pipeline_file]
        )
        assert result["success"], f"Run workflow failed: {result['output']}"
        print("✅ Workflow started")

        # Step 7: Get workflow ARN
        print("\n=== Step 7: Get Workflow ARN ===")
        import boto3
        region = os.environ.get('DEV_DOMAIN_REGION', 'us-east-2')
        endpoint = os.environ.get('AIRFLOW_SERVERLESS_ENDPOINT', f'https://airflow-serverless.{region}.api.aws/')
        client = boto3.client('mwaaserverless', region_name=region, endpoint_url=endpoint)
        response = client.list_workflows()
        workflow_arn = None
        expected_name = 'IntegrationTestMLWorkflow_test_marketing_ml_dev_workflow_v3'
        for wf in response.get('Workflows', []):
            if wf.get('Name') == expected_name:
                workflow_arn = wf.get('WorkflowArn')
                break
        assert workflow_arn, "Could not find workflow ARN"
        print(f"✅ Workflow ARN: {workflow_arn}")

        # Step 8: Fetch workflow logs and wait for completion
        print("\n=== Step 8: Fetch Workflow Logs and Wait ===")
        result = self.run_cli_command(
            ["logs", "--live", "--workflow", workflow_arn]
        )
        if result["success"]:
            print("✅ Workflow completed successfully")
        else:
            print(f"⚠️ Workflow logs: {result['output']}")

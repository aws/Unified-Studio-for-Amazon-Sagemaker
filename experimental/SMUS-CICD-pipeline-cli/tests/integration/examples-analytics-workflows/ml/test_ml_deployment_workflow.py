"""Integration test for ML deployment workflow."""

import pytest
import os
import subprocess
import re
import boto3
from tests.integration.base import IntegrationTestBase


class TestMLDeploymentWorkflow(IntegrationTestBase):
    """Test ML deployment workflow."""

    def setup_method(self, method):
        """Set up test environment."""
        super().setup_method(method)
        self.setup_test_directory()
        self.cleanup_workflows()

    def cleanup_workflows(self):
        """Delete existing workflows from previous runs."""
        try:
            region = os.environ.get('DEV_DOMAIN_REGION', 'us-east-1')
            endpoint = os.environ.get('AIRFLOW_SERVERLESS_ENDPOINT')
            if not endpoint:
                endpoint = f'https://airflow-serverless.{region}.api.aws/'
            
            client = boto3.client(
                'awsoverdriveservice',
                region_name=region,
                endpoint_url=endpoint
            )
            response = client.list_workflows()
            workflows = response.get('Workflows', [])
            expected_name = 'IntegrationTestMLWorkflow_test_marketing_ml_deployment_workflow'
            
            for wf in workflows:
                if wf.get('Name') == expected_name:
                    workflow_arn = wf.get('WorkflowArn')
                    print(f"🗑️  Deleting existing workflow: {expected_name}")
                    client.delete_workflow(WorkflowArn=workflow_arn)
                    print("✅ Workflow deleted")
                    break
        except Exception as e:
            print(f"⚠️  Could not delete workflow: {e}")

    def get_pipeline_file(self):
        return os.path.join(
            os.path.dirname(__file__),
            "../../../../examples/analytic-workflow/ml/ml_pipeline.yaml"
        )

    def get_latest_training_job(self):
        """Get the most recent completed training job."""
        region = os.environ.get('DEV_DOMAIN_REGION', 'us-east-2')
        sm_client = boto3.client('sagemaker', region_name=region)
        
        response = sm_client.list_training_jobs(
            SortBy='CreationTime',
            SortOrder='Descending',
            MaxResults=10,
            StatusEquals='Completed'
        )
        
        for job in response['TrainingJobSummaries']:
            job_name = job['TrainingJobName']
            if 'orchestrated-training' in job_name or 'ml-training' in job_name:
                print(f"✅ Found training job: {job_name}")
                return job_name
        
        pytest.skip("No completed training job found")

    @pytest.mark.integration
    def test_ml_deployment_workflow(self):
        """Test ML deployment workflow using model from 'latest' S3 location."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()
        workflow_name = "ml_deployment_workflow"

        # Step 1: Describe --connect
        print("\n=== Step 1: Describe with Connections ===")
        result = self.run_cli_command(["describe", "--pipeline", pipeline_file, "--connect"])
        assert result["success"], f"Describe --connect failed: {result['output']}"
        print("✅ Describe --connect successful")

        # Step 2: Upload ML code to S3
        print("\n=== Step 2: Upload ML Code to S3 ===")
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

        # Step 3: Bundle from dev
        print("\n=== Step 3: Bundle from dev ===")
        result = self.run_cli_command(["bundle", "--pipeline", pipeline_file, "--target", "dev"])
        assert result["success"], f"Bundle failed: {result['output']}"
        print("✅ Bundle successful")

        # Step 4: Deploy to test
        print("\n=== Step 4: Deploy to test ===")
        result = self.run_cli_command(["deploy", "test", "--pipeline", pipeline_file])
        assert result["success"], f"Deploy failed: {result['output']}"
        print("✅ Deploy successful")

        # Step 5: Run workflow
        print("\n=== Step 5: Run Workflow ===")
        result = self.run_cli_command(
            ["run", "--workflow", workflow_name, "--targets", "test", "--pipeline", pipeline_file]
        )
        assert result["success"], f"Run workflow failed: {result['output']}"
        print("✅ Workflow started")

        # Step 6: Get workflow ARN
        print("\n=== Step 6: Get Workflow ARN ===")
        region = os.environ.get('DEV_DOMAIN_REGION', 'us-east-1')
        endpoint = os.environ.get('AIRFLOW_SERVERLESS_ENDPOINT', f'https://airflow-serverless.{region}.api.aws/')
        client = boto3.client('awsoverdriveservice', region_name=region, endpoint_url=endpoint)
        response = client.list_workflows()
        workflow_arn = None
        expected_name = 'IntegrationTestMLWorkflow_test_marketing_ml_deployment_workflow'
        for wf in response.get('Workflows', []):
            if wf.get('Name') == expected_name:
                workflow_arn = wf.get('WorkflowArn')
                break
        assert workflow_arn, "Could not find workflow ARN"
        print(f"✅ Workflow ARN: {workflow_arn}")

        # Step 7: Wait for completion
        print("\n=== Step 7: Wait for Completion ===")
        result = self.run_cli_command(
            ["logs", "--live", "--workflow", workflow_arn]
        )
        if result["success"]:
            print("✅ Deployment workflow completed successfully")
        else:
            print(f"⚠️ Workflow logs: {result['output']}")

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

    def get_pipeline_file(self):
        return os.path.join(
            os.path.dirname(__file__),
            "../../../../examples/analytic-workflow/ml/deployment/ml_deployment_bundle.yaml"
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
        result = self.run_cli_command(["describe", "--bundle", pipeline_file, "--connect"])
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
        result = self.run_cli_command(["bundle", "--bundle", pipeline_file, "--target", "dev"])
        assert result["success"], f"Bundle failed: {result['output']}"
        print("✅ Bundle successful")

        # Step 4: Deploy to test
        print("\n=== Step 4: Deploy to test ===")
        result = self.run_cli_command(["deploy", "test", "--bundle", pipeline_file])
        assert result["success"], f"Deploy failed: {result['output']}"
        print("✅ Deploy successful")

        # Step 5: Run workflow
        print("\n=== Step 5: Run Workflow ===")
        result = self.run_cli_command(
            ["run", "--workflow", workflow_name, "--targets", "test", "--bundle", pipeline_file]
        )
        assert result["success"], f"Run workflow failed: {result['output']}"
        print("✅ Workflow started")

        # Step 6: Get workflow ARN
        print("\n=== Step 6: Get Workflow ARN ===")
        region = os.environ.get('DEV_DOMAIN_REGION', 'us-east-2')
        endpoint = os.environ.get('AIRFLOW_SERVERLESS_ENDPOINT', f'https://airflow-serverless.{region}.api.aws/')
        client = boto3.client('mwaaserverless', region_name=region, endpoint_url=endpoint)
        response = client.list_workflows()
        workflow_arn = None
        expected_name = 'IntegrationTestMLDeployment_test_marketing_ml_deployment_workflow'
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
        workflow_succeeded = result["success"]
        if workflow_succeeded:
            print("✅ Deployment workflow completed successfully")
        else:
            print(f"⚠️ Workflow failed: {result['output']}")
        
        # Step 8: Download and validate output notebooks (always run, even if workflow failed)
        print("\n=== Step 8: Download and Validate Output Notebooks ===")
        
        # Extract S3 bucket from test project (not dev)
        test_s3_uri_match = re.search(
            r"test: test-marketing.*?default\.s3_shared:.*?s3Uri: (s3://[^\s]+)",
            result["output"] if not workflow_succeeded else "",
            re.DOTALL
        )
        # Fallback to describe output from Step 1
        if not test_s3_uri_match:
            describe_result = self.run_cli_command(["describe", "--bundle", pipeline_file, "--connect"])
            test_s3_uri_match = re.search(
                r"test: test-marketing.*?default\.s3_shared:.*?s3Uri: (s3://[^\s]+)",
                describe_result["output"],
                re.DOTALL
            )
        
        s3_bucket_match = test_s3_uri_match
        if s3_bucket_match:
            test_s3_uri = s3_bucket_match.group(1)
            s3_bucket = re.search(r"s3://([^/]+)", test_s3_uri).group(1)
            
            # Extract run_id from workflow ARN or logs
            run_id_match = re.search(r"run_id=([^/\s]+)", result["output"])
            run_id = run_id_match.group(1) if run_id_match else None
            
            notebooks_valid = self.download_and_validate_notebooks(
                s3_bucket=s3_bucket,
                run_id=run_id
            )
            
            # Only assert if workflow succeeded
            if workflow_succeeded:
                assert notebooks_valid, "Output notebooks contain errors"
                print("✅ All output notebooks validated successfully")
            else:
                print(f"⚠️ Notebooks downloaded for inspection (workflow failed)")
        else:
            print("⚠️ Could not determine S3 bucket, skipping notebook validation")
        
        # Final assertion - workflow must succeed
        assert workflow_succeeded, "Workflow execution failed"

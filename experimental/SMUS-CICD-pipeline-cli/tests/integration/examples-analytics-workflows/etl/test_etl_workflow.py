"""Integration test for ETL workflow deployment."""

import pytest
import os
import subprocess
import re
import boto3
from tests.integration.base import IntegrationTestBase


class TestETLWorkflow(IntegrationTestBase):
    """Test ETL workflow deployment."""

    def setup_method(self, method):
        """Set up test environment."""
        super().setup_method(method)
        self.setup_test_directory()
        self.cleanup_glue_databases()

    def cleanup_glue_databases(self):
        """Delete test Glue databases and S3 data."""
        glue_client = boto3.client('glue', region_name='us-east-1')
        s3_client = boto3.client('s3', region_name='us-east-1')
        
        databases_to_delete = ['analytic_workflow_test_db', 'covid19_summary_db']
        
        for db_name in databases_to_delete:
            try:
                # Get database location before deleting
                try:
                    db_info = glue_client.get_database(Name=db_name)
                    location_uri = db_info.get('Database', {}).get('LocationUri', '')
                    
                    # Delete S3 data if location exists
                    if location_uri.startswith('s3://'):
                        bucket_and_key = location_uri[5:].split('/', 1)
                        bucket = bucket_and_key[0]
                        prefix = bucket_and_key[1] if len(bucket_and_key) > 1 else ''
                        
                        # Delete all objects in the location
                        paginator = s3_client.get_paginator('list_objects_v2')
                        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                            objects = page.get('Contents', [])
                            if objects:
                                delete_keys = [{'Key': obj['Key']} for obj in objects]
                                s3_client.delete_objects(Bucket=bucket, Delete={'Objects': delete_keys})
                                print(f"✅ Deleted S3 data: s3://{bucket}/{prefix}")
                except glue_client.exceptions.EntityNotFoundException:
                    pass
                
                # Delete the database
                glue_client.delete_database(Name=db_name)
                print(f"✅ Deleted Glue database: {db_name}")
            except glue_client.exceptions.EntityNotFoundException:
                pass
            except Exception as e:
                print(f"⚠️ Could not delete database {db_name}: {e}")

    def get_pipeline_file(self):
        return os.path.join(
            os.path.dirname(__file__),
            "../../../../examples/analytic-workflow/etl/etl_bundle.yaml"
        )

    @pytest.mark.integration
    def test_etl_workflow_deployment(self):
        """Test ETL workflow deployment following basic_pipeline pattern."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()
        workflow_name = "covid_etl_pipeline"
        
        # Cleanup: Remove etl directory from test project S3
        print("\n=== Cleanup: Remove test project S3 etl directory ===")
        try:
            subprocess.run(
                ["aws", "s3", "rm", "s3://amazon-sagemaker-198737698272-us-east-1-4pg255jku47vdz/shared/etl/", "--recursive"],
                capture_output=True,
                text=True
            )
            print("✅ Cleaned test project S3 etl directory")
        except Exception as e:
            print(f"⚠️ Could not clean S3: {e}")

        # Step 1: Describe --connect
        print("\n=== Step 1: Describe with Connections ===")
        result = self.run_cli_command(["describe", "--manifest", pipeline_file, "--connect"])
        assert result["success"], f"Describe --connect failed: {result['output']}"
        print("✅ Describe --connect successful")

        # Step 2: Upload ETL code to S3 (dev project)
        print("\n=== Step 2: Upload ETL Code to S3 (dev project) ===")
        s3_uri_match = re.search(
            r"dev: dev-marketing.*?default\.s3_shared:.*?s3Uri: (s3://[^\s]+)",
            result["output"],
            re.DOTALL
        )
        
        if s3_uri_match:
            s3_uri = s3_uri_match.group(1)
            etl_dir = os.path.join(
                os.path.dirname(__file__),
                "../../../../examples/analytic-workflow/etl"
            )
            
            if os.path.exists(etl_dir):
                self.sync_to_s3(etl_dir, s3_uri + "etl/", exclude_patterns=["*.pyc", "__pycache__/*", "test_*.sh"])
        else:
            print("⚠️ Could not extract S3 URI from describe output")

        # Step 3: Bundle from dev
        print("\n=== Step 3: Bundle from dev ===")
        result = self.run_cli_command(["bundle", "--manifest", pipeline_file, "--target", "dev"])
        assert result["success"], f"Bundle failed: {result['output']}"
        print("✅ Bundle successful")

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

        # Step 6: Run workflow and extract ARN
        print("\n=== Step 6: Run Workflow ===")
        result = self.run_cli_command(
            ["run", "--workflow", workflow_name, "--targets", "test", "--manifest", pipeline_file]
        )
        assert result["success"], f"Run workflow failed: {result['output']}"
        
        # Extract workflow ARN from run output
        workflow_arn_match = re.search(r'🔗 ARN: (arn:aws:airflow-serverless:[^\s]+)', result["output"])
        workflow_arn = workflow_arn_match.group(1) if workflow_arn_match else None
        
        if workflow_arn:
            print(f"✅ Workflow started: {workflow_arn}")
        else:
            print("✅ Workflow started (ARN not found)")

        # Step 7: Monitor workflow status
        print("\n=== Step 7: Monitor Workflow Status ===")
        result = self.run_cli_command(["monitor", "--targets", "test", "--manifest", pipeline_file])
        assert result["success"], f"Monitor after run failed: {result['output']}"
        print("✅ Monitor after run successful")

        # Step 8: Wait for workflow completion using logs
        print("\n=== Step 8: Wait for Workflow Completion ===")
        if workflow_arn:
            print(f"📋 Monitoring workflow: {workflow_arn}")
            result = self.run_cli_command(["logs", "--live", "--workflow", workflow_arn])
            # logs --live waits for completion and returns success/failure
            if result["success"]:
                print("✅ Workflow completed successfully")
            else:
                print(f"⚠️ Workflow failed or timed out: {result['output']}")
                # Don't fail the test yet - let pipeline tests determine success
        else:
            print("⚠️ Could not extract workflow ARN, skipping log wait")
        
        # Step 9: Run pipeline tests
        print("\n=== Step 9: Run Pipeline Tests ===")
        result = self.run_cli_command(["test", "--targets", "test", "--test-output", "console", "--manifest", pipeline_file])
        assert result["success"], f"Pipeline tests failed: {result['output']}"
        print("✅ Pipeline tests passed")
        print("✅ ETL workflow test completed successfully")

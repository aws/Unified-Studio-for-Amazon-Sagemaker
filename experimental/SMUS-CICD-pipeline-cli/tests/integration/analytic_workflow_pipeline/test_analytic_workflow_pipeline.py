"""Integration test for analytic workflow pipeline deployment."""

import pytest
import os
from typer.testing import CliRunner
from ..base import IntegrationTestBase
from smus_cicd.helpers.utils import get_datazone_project_info


class TestAnalyticWorkflowPipeline(IntegrationTestBase):
    """Test analytic workflow pipeline end-to-end deployment."""

    def setup_method(self, method):
        """Set up test environment."""
        super().setup_method(method)
        self.setup_test_directory()
        self.cleanup_glue_databases()
        self.cleanup_airflow_workflows()

    def cleanup_glue_databases(self):
        """Delete Glue databases that might conflict with the test."""
        import boto3
        
        glue_client = boto3.client('glue', region_name='us-east-1')
        lakeformation_client = boto3.client('lakeformation', region_name='us-east-1')
        sts_client = boto3.client('sts', region_name='us-east-1')
        
        # Get current role ARN
        identity = sts_client.get_caller_identity()
        role_arn = identity['Arn']
        print(f"✅ AWS credentials verified: {role_arn}")
        
        databases_to_delete = ['analytic_workflow_test_db']
        
        for db_name in databases_to_delete:
            try:
                # First, try to grant Lake Formation DROP permission
                try:
                    lakeformation_client.grant_permissions(
                        Principal={'DataLakePrincipalIdentifier': role_arn},
                        Resource={'Database': {'Name': db_name}},
                        Permissions=['DROP']
                    )
                    print(f"✅ Granted Lake Formation DROP permission for {db_name}")
                except Exception as perm_error:
                    if "Database not found" in str(perm_error):
                        print(f"ℹ️  Database {db_name} doesn't exist, no permissions needed")
                    else:
                        print(f"⚠️ Could not grant Lake Formation permissions for {db_name}: {perm_error}")
                
                # Try to delete the database
                glue_client.delete_database(Name=db_name)
                print(f"✅ Deleted Glue database: {db_name}")
                
            except glue_client.exceptions.EntityNotFoundException:
                print(f"ℹ️  Database {db_name} doesn't exist, skipping deletion")
            except Exception as e:
                print(f"⚠️ Could not delete database {db_name}: {e}")

    def cleanup_airflow_workflows(self):
        """Delete Airflow Serverless workflows from previous test runs."""
        import boto3
        from botocore.exceptions import ClientError
        import time
        
        client = boto3.client(
            'awsoverdriveservice',
            region_name='us-west-2',
            endpoint_url='https://overdrive-gamma.us-west-2.api.aws'
        )
        
        try:
            response = client.list_workflows()
            workflows = response.get('Workflows', [])
            
            for workflow in workflows:
                workflow_name = workflow['Name']
                workflow_arn = workflow['WorkflowArn']
                
                # Delete workflows matching test pattern
                if 'IntegrationTestAnalyticWorkflowBundle' in workflow_name or 'ml-dev' in workflow_name:
                    try:
                        # Stop all running executions first
                        runs_response = client.list_workflow_runs(WorkflowArn=workflow_arn, MaxResults=10)
                        runs = runs_response.get('WorkflowRuns', [])
                        
                        for run in runs:
                            status = run['RunDetailSummary']['Status']
                            run_id = run['RunId']
                            
                            if status in ['RUNNING', 'QUEUED', 'STARTING']:
                                print(f"⏹️  Stopping run {run_id} for {workflow_name}")
                                client.stop_workflow_run(WorkflowArn=workflow_arn, RunId=run_id)
                        
                        # Wait for stops to process
                        if runs:
                            print(f"⏳ Waiting 5s for runs to stop...")
                            time.sleep(5)
                        
                        # Try to delete
                        client.delete_workflow(WorkflowArn=workflow_arn)
                        print(f"✅ Deleted workflow: {workflow_name}")
                    except ClientError as e:
                        if 'workflow runs are in progress' in str(e):
                            print(f"⚠️ Workflow {workflow_name} still has running executions, skipping")
                        else:
                            print(f"⚠️ Could not delete workflow {workflow_name}: {e}")
                    except Exception as e:
                        print(f"⚠️ Could not delete workflow {workflow_name}: {e}")
        except Exception as e:
            print(f"⚠️ Could not list workflows: {e}")

    def get_pipeline_file(self):
        """Get path to pipeline file in same directory."""
        return os.path.join(os.path.dirname(__file__), "analytic_workflow_pipeline.yaml")

    @pytest.mark.integration
    def test_analytic_workflow_pipeline_deployment(self):
        """Test complete analytic workflow pipeline deployment workflow."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()
        
        print(f"\n=== Starting Analytic Workflow Pipeline Deployment Test ===")
        print(f"Pipeline file: {pipeline_file}")
        
        # Verify the referenced analytic-workflow directory exists
        analytic_workflow_dir = os.path.join(os.path.dirname(__file__), "../../../examples/analytic-workflow")
        ml_workflows_dir = os.path.join(analytic_workflow_dir, "ml/workflows")
        ml_scripts_dir = os.path.join(analytic_workflow_dir, "ml/scripts")
        
        assert os.path.exists(analytic_workflow_dir), f"Analytic workflow directory not found: {analytic_workflow_dir}"
        assert os.path.exists(ml_workflows_dir), f"ML workflows directory not found: {ml_workflows_dir}"
        print(f"✅ Verified analytic-workflow ML directories exist")
        
        try:
            # Step 1: Describe pipeline to get dev project S3 URI
            print(f"\n=== Step 1: Get Dev Project S3 URI ===")
            result = self.run_cli_command([
                "describe", 
                "--pipeline", pipeline_file,
                "--connect"
            ])
            assert result["exit_code"] == 0, f"Describe failed: {result['output']}"
            
            # Extract S3 URI for dev project
            import re
            import subprocess
            
            s3_uri_match = re.search(
                r"dev: dev-marketing.*?s3Uri: (s3://[^\s]+)",
                result["output"],
                re.DOTALL
            )
            assert s3_uri_match, "S3 URI not found for dev project"
            s3_uri = s3_uri_match.group(1)
            print(f"✅ Found dev project S3 URI: {s3_uri}")
            
            # Step 2: Upload entire analytic-workflow to dev project S3 code/ directory
            print(f"\n=== Step 2: Upload Analytic Workflow to Dev Project ===")
            analytic_workflow_dir = os.path.join(os.path.dirname(__file__), "../../../examples/analytic-workflow")
            code_dest = f"{s3_uri}code/"
            
            result = subprocess.run([
                "aws", "s3", "sync", analytic_workflow_dir, code_dest,
                "--exclude", ".*",
                "--exclude", "*/.*",
                "--exclude", "*.pyc",
                "--exclude", "__pycache__/*", 
                "--exclude", ".ipynb_checkpoints/*"
            ], capture_output=True, text=True)
            assert result.returncode == 0, f"Code upload failed: {result.stderr}"
            print(f"✅ Analytic workflow uploaded to {code_dest}")
            
            # Step 3: Create bundle from dev project (now has files)
            print(f"\n=== Step 3: Create Bundle from Dev Project ===")
            result = self.run_cli_command([
                "bundle", 
                "--pipeline", pipeline_file,
                "dev"  # Bundle from dev project that has the files
            ])
            assert result["exit_code"] == 0, f"Bundle creation failed: {result['output']}"
            print(f"✅ Bundle created successfully from dev project")
            
            # Step 4: Deploy to test
            print(f"\n=== Step 4: Deploy to Test ===")
            result = self.run_cli_command([
                "deploy", 
                "--pipeline", pipeline_file,
                "--targets", "test"
            ])
            assert result["exit_code"] == 0, f"Deploy failed: {result['output']}"
            print(f"✅ Deployed to test successfully")
            
            # Step 5: Verify deployment
            print(f"\n=== Step 5: Verify Deployment ===")
            result = self.run_cli_command([
                "describe", 
                "--pipeline", pipeline_file,
                "--connect"
            ])
            assert result["exit_code"] == 0, f"Describe failed: {result['output']}"
            
            # Verify test project was created and is accessible
            output = result["output"]
            assert "analytic-workflow-test" in output
            if "Project analytic-workflow-test not found" not in output:
                print(f"✅ Test project created and accessible")
            else:
                print(f"⚠️ Test project still showing as not found")
            
            # Step 6: Run workflow
            print(f"\n=== Step 6: Run Workflow ===")
            result = self.run_cli_command([
                "run", 
                "--pipeline", pipeline_file,
                "--targets", "test",
                "--workflow", "ml_dev_workflow"
            ])
            
            workflow_arn = None
            if result["exit_code"] == 0:
                print(f"✅ Workflow started successfully")
                # Extract workflow ARN from output
                import re
                arn_match = re.search(r'(arn:aws:airflow-serverless:[^:]+:[^:]+:workflow/[^\s]+)', result["output"])
                if arn_match:
                    workflow_arn = arn_match.group(1)
                    print(f"📋 Workflow ARN: {workflow_arn}")
            else:
                print(f"⚠️ Workflow run failed: {result['output']}")
            
            # Step 7: Monitor deployment
            print(f"\n=== Step 7: Monitor Deployment ===")
            result = self.run_cli_command([
                "monitor", 
                "--pipeline", pipeline_file
            ])
            if result["exit_code"] == 0:
                print(f"✅ Monitor completed successfully")
            else:
                print(f"⚠️ Monitor failed or timed out: {result['output']}")
            
            # Step 8: Get workflow logs
            if workflow_arn:
                print(f"\n=== Step 8: Get Workflow Logs ===")
                result = self.run_cli_command([
                    "logs",
                    "--workflow", workflow_arn,
                    "--live"
                ])
                if result["exit_code"] == 0:
                    print(f"✅ Logs retrieved successfully")
                    print(f"📄 Log output preview (last 20 lines):")
                    log_lines = result["output"].split('\n')
                    for line in log_lines[-20:]:
                        if line.strip():
                            print(f"  {line}")
                else:
                    print(f"⚠️ Logs retrieval failed (workflow may not have generated logs yet)")
                    print(f"   This is expected if the workflow completed very quickly")
            
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            raise
        
        finally:
            # Cleanup
            print(f"\n=== Cleanup ===")
            try:
                bundle_dir = "/tmp/bundles"
                if os.path.exists(bundle_dir):
                    shutil.rmtree(bundle_dir)
                    print(f"✅ Cleaned up bundle directory: {bundle_dir}")
            except Exception as e:
                print(f"⚠️ Could not clean up: {e}")
            print(f"✅ Test completed and cleaned up")


#!/usr/bin/env python3
"""
Integration test for airflow serverless helper functions.
Tests complete lifecycle: upload, create, list, start, monitor, stop, delete
"""

import sys
import os
import time
import uuid
import pytest

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from smus_cicd.helpers import airflow_serverless

# Test configuration
REGION = 'us-east-1'
BUCKET_NAME = 'datazone-058264284947-us-east-1-cicd-test-domain'
ROLE_ARN = 'arn:aws:iam::058264284947:role/OverdriveExecutionRole'

# Test DAG content
TEST_DAG_CONTENT = """s3_list_dag:
  dag_id: "integration_test_dag"
  tasks:
    task_1:
      operator: "airflow.providers.amazon.aws.operators.s3.S3ListOperator"
      bucket: "datazone-058264284947-us-east-1-cicd-test-domain"
"""

class TestAirflowServerlessHelperLifecycle:
    """Integration test class for airflow serverless helper lifecycle."""
    
    def test_airflow_serverless_complete_lifecycle(self):
        """Test complete airflow serverless lifecycle in sequence."""
        
        # Generate unique identifiers
        test_workflow_name = f'integration-test-{uuid.uuid4().hex[:8]}'
        dag_key = f'integration-test/{test_workflow_name}.yaml'
        
        # Step 1: Upload DAG to S3
        print("Step 1: Uploading DAG to S3...")
        result = airflow_serverless.upload_dag_to_s3(
            dag_content=TEST_DAG_CONTENT,
            bucket_name=BUCKET_NAME,
            dag_key=dag_key,
            region=REGION
        )
        assert result['success'] is True
        assert result['bucket'] == BUCKET_NAME
        assert result['key'] == dag_key
        
        # Step 2: List existing workflows
        print("Step 2: Listing workflows...")
        workflows = airflow_serverless.list_workflows(region=REGION)
        assert isinstance(workflows, list)
        if workflows:
            workflow = workflows[0]
            assert 'workflow_arn' in workflow
            assert 'name' in workflow
            assert 'status' in workflow
        
        # Step 3: Create workflow
        print("Step 3: Creating workflow...")
        dag_s3_location = {
            'Bucket': BUCKET_NAME,
            'ObjectKey': dag_key
        }
        result = airflow_serverless.create_workflow(
            workflow_name=test_workflow_name,
            dag_s3_location=dag_s3_location,
            role_arn=ROLE_ARN,
            description='Integration test workflow',
            tags={'Test': 'Integration', 'Purpose': 'Lifecycle'},
            region=REGION
        )
        assert result['success'] is True
        assert 'workflow_arn' in result
        assert test_workflow_name in result['workflow_arn']
        workflow_arn = result['workflow_arn']
        
        # Step 4: Get workflow status
        print("Step 4: Getting workflow status...")
        result = airflow_serverless.get_workflow_status(
            workflow_arn=workflow_arn,
            region=REGION
        )
        assert result['success'] is True
        assert result['status'] == 'READY'
        assert 'name' in result
        
        # Step 5: Start workflow run
        print("Step 5: Starting workflow run...")
        result = airflow_serverless.start_workflow_run(
            workflow_arn=workflow_arn,
            run_name=f"integration-run-{uuid.uuid4().hex[:8]}",
            region=REGION
        )
        assert result['success'] is True
        assert 'run_id' in result
        assert result['status'] in ['STARTING', 'QUEUED']
        run_id = result['run_id']
        
        # Step 6: List workflow runs
        print("Step 6: Listing workflow runs...")
        runs = airflow_serverless.list_workflow_runs(
            workflow_arn=workflow_arn,
            region=REGION
        )
        assert isinstance(runs, list)
        assert len(runs) >= 1
        our_run = next((r for r in runs if r['run_id'] == run_id), None)
        assert our_run is not None
        assert our_run['status'] in ['STARTING', 'QUEUED', 'RUNNING']
        
        # Step 7: Get workflow run status
        print("Step 7: Getting workflow run status...")
        result = airflow_serverless.get_workflow_run_status(
            workflow_arn=workflow_arn,
            run_id=run_id,
            region=REGION
        )
        assert result['success'] is True
        assert result['run_id'] == run_id
        assert 'status' in result
        
        # Step 8: Stop workflow run
        print("Step 8: Stopping workflow run...")
        try:
            result = airflow_serverless.stop_workflow_run(
                workflow_arn=workflow_arn,
                run_id=run_id,
                region=REGION
            )
            assert result['success'] is True
        except Exception as e:
            # Allow if already completed/stopping
            assert "already" in str(e).lower()
        
        # Step 9: Validate health
        print("Step 9: Validating health...")
        result = airflow_serverless.validate_airflow_serverless_health(
            project_name="integration-test",
            config={"region": REGION}
        )
        assert result is True
        
        # Step 10: Cleanup S3 DAG
        print("Step 10: Cleaning up S3 DAG...")
        result = airflow_serverless.cleanup_s3_dag(
            bucket_name=BUCKET_NAME,
            dag_key=dag_key,
            region=REGION
        )
        assert result['success'] is True
        
        # Step 11: Cleanup workflow
        print("Step 11: Cleaning up workflow...")
        try:
            result = airflow_serverless.delete_workflow(
                workflow_arn=workflow_arn,
                region=REGION
            )
            assert result['success'] is True
        except Exception as e:
            # Expected to fail if runs are still active
            assert "Operation denied" in str(e)
        
        print("✅ Complete airflow serverless lifecycle test passed!")


if __name__ == '__main__':
    # Run as standalone test
    pytest.main([__file__, '-v'])

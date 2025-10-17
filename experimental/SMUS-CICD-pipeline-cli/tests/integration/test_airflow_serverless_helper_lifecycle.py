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
    
    @pytest.fixture(scope="class")
    def test_workflow_name(self):
        """Generate unique workflow name for test."""
        return f'integration-test-{uuid.uuid4().hex[:8]}'
    
    @pytest.fixture(scope="class")
    def dag_key(self, test_workflow_name):
        """Generate S3 key for test DAG."""
        return f'integration-test/{test_workflow_name}.yaml'
    
    def test_01_upload_dag_to_s3(self, dag_key):
        """Test DAG upload to S3."""
        result = airflow_serverless.upload_dag_to_s3(
            dag_content=TEST_DAG_CONTENT,
            bucket_name=BUCKET_NAME,
            dag_key=dag_key,
            region=REGION
        )
        
        assert result['success'] is True
        assert result['bucket'] == BUCKET_NAME
        assert result['key'] == dag_key
    
    def test_02_list_workflows(self):
        """Test listing existing workflows."""
        workflows = airflow_serverless.list_workflows(region=REGION)
        
        assert isinstance(workflows, list)
        assert len(workflows) >= 0
        
        # Verify workflow structure
        if workflows:
            workflow = workflows[0]
            assert 'workflow_arn' in workflow
            assert 'name' in workflow
            assert 'status' in workflow
    
    def test_03_create_workflow(self, test_workflow_name, dag_key):
        """Test workflow creation."""
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
        
        # Store for cleanup
        self.workflow_arn = result['workflow_arn']
    
    def test_04_get_workflow_status(self):
        """Test getting workflow status."""
        result = airflow_serverless.get_workflow_status(
            workflow_arn=self.workflow_arn,
            region=REGION
        )
        
        assert result['success'] is True
        assert result['status'] == 'READY'
        assert 'name' in result
    
    def test_05_start_workflow_run(self):
        """Test starting workflow run."""
        result = airflow_serverless.start_workflow_run(
            workflow_arn=self.workflow_arn,
            run_name=f"integration-run-{uuid.uuid4().hex[:8]}",
            region=REGION
        )
        
        assert result['success'] is True
        assert 'run_id' in result
        assert result['status'] in ['STARTING', 'QUEUED']
        
        # Store for monitoring
        self.run_id = result['run_id']
    
    def test_06_list_workflow_runs(self):
        """Test listing workflow runs."""
        runs = airflow_serverless.list_workflow_runs(
            workflow_arn=self.workflow_arn,
            region=REGION
        )
        
        assert isinstance(runs, list)
        assert len(runs) >= 1
        
        # Find our run
        our_run = next((r for r in runs if r['run_id'] == self.run_id), None)
        assert our_run is not None
        assert our_run['status'] in ['STARTING', 'QUEUED', 'RUNNING']
    
    def test_07_get_workflow_run_status(self):
        """Test getting workflow run status."""
        result = airflow_serverless.get_workflow_run_status(
            workflow_arn=self.workflow_arn,
            run_id=self.run_id,
            region=REGION
        )
        
        assert result['success'] is True
        assert result['run_id'] == self.run_id
        assert 'status' in result
    
    def test_08_stop_workflow_run(self):
        """Test stopping workflow run."""
        try:
            result = airflow_serverless.stop_workflow_run(
                workflow_arn=self.workflow_arn,
                run_id=self.run_id,
                region=REGION
            )
            assert result['success'] is True
        except Exception as e:
            # Allow if already completed/stopping
            assert "already" in str(e).lower()
    
    def test_09_validate_health(self):
        """Test health validation."""
        result = airflow_serverless.validate_airflow_serverless_health(
            project_name="integration-test",
            config={"region": REGION}
        )
        
        assert result is True
    
    def test_10_cleanup_s3_dag(self, dag_key):
        """Test S3 DAG cleanup."""
        result = airflow_serverless.cleanup_s3_dag(
            bucket_name=BUCKET_NAME,
            dag_key=dag_key,
            region=REGION
        )
        
        assert result['success'] is True
    
    def test_11_cleanup_workflow(self):
        """Test workflow cleanup (may fail if runs active)."""
        try:
            result = airflow_serverless.delete_workflow(
                workflow_arn=self.workflow_arn,
                region=REGION
            )
            assert result['success'] is True
        except Exception as e:
            # Expected to fail if runs are still active
            assert "Operation denied" in str(e)


if __name__ == '__main__':
    # Run as standalone test
    pytest.main([__file__, '-v'])

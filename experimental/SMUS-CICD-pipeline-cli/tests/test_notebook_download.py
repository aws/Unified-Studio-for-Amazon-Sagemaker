#!/usr/bin/env python3
# TODO: Replace {account_id} placeholders with test_config.get_account_id()
"""Test notebook download logic with real workflow data."""

import boto3
import json
import sys
import os

# Test data
WORKFLOW_ARN = "arn:aws:airflow-serverless:us-east-2:{account_id}:workflow/IntegrationTestMLTraining_test_marketing_ml_training_workflow-kzdAIFgVi0"
RUN_ID = "8eWcohEKJp9jomr"
TASK_INSTANCE_ID = "ex_b97788da-5efd-4347-8755-1ba2ed15db18_ml_training_notebook_1"

def test_aws_cli_response():
    """Test what AWS CLI returns."""
    print("=== Testing AWS CLI Response ===")
    
    region = 'us-east-2'
    endpoint = 'https://airflow-serverless.us-east-2.api.aws/'
    client = boto3.client('mwaaserverless-internal', region_name=region, endpoint_url=endpoint)
    
    # List task instances
    print(f"\n1. Listing task instances for run {RUN_ID}")
    response = client.list_task_instances(WorkflowArn=WORKFLOW_ARN, RunId=RUN_ID)
    task_instances = response.get('TaskInstances', [])
    print(f"   Found {len(task_instances)} task instances")
    for task in task_instances:
        print(f"   - TaskId: {task.get('TaskId')}, TaskInstanceId: {task.get('TaskInstanceId')}")
    
    # Get specific task instance
    print(f"\n2. Getting task instance details")
    task_detail = client.get_task_instance(
        WorkflowArn=WORKFLOW_ARN,
        RunId=RUN_ID,
        TaskInstanceId=TASK_INSTANCE_ID
    )
    
    print(f"   Status: {task_detail.get('Status')}")
    print(f"   OperatorName: {task_detail.get('OperatorName')}")
    
    # Check XCom
    xcom = task_detail.get('Xcom', {})
    print(f"\n3. XCom data:")
    print(f"   Keys: {list(xcom.keys())}")
    for key, value in xcom.items():
        print(f"   {key}: {value[:100] if isinstance(value, str) and len(value) > 100 else value}")
    
    # Check for notebook output
    print(f"\n4. Looking for notebook output:")
    notebook_output = (
        xcom.get('notebook_output') or 
        xcom.get('return_value') or 
        xcom.get('sagemaker_unified_studio') or
        xcom.get('s3_path')
    )
    
    if notebook_output:
        # Remove quotes if present
        if isinstance(notebook_output, str):
            notebook_output = notebook_output.strip('"')
        print(f"   ✅ Found: {notebook_output}")
        
        # Check if it's a tar.gz file
        if notebook_output.endswith('.tar.gz'):
            print(f"   ✅ Is tar.gz file")
            
            # Check if it contains 'output'
            if '/output/' in notebook_output:
                print(f"   ✅ Contains /output/ path")
            else:
                print(f"   ⚠️ Does not contain /output/ path")
        else:
            print(f"   ⚠️ Not a tar.gz file")
    else:
        print(f"   ❌ No notebook output found in XCom")
        return False
    
    return True

def test_download_logic():
    """Test the actual download logic from base.py."""
    print("\n\n=== Testing Download Logic ===")
    
    # Add parent directory to path to import base
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'integration'))
    from base import IntegrationTestBase
    
    # Create test instance
    test = IntegrationTestBase()
    
    print(f"\nCalling download_and_validate_notebooks:")
    print(f"  workflow_arn: {WORKFLOW_ARN}")
    print(f"  run_id: {RUN_ID}")
    
    result = test.download_and_validate_notebooks(
        workflow_arn=WORKFLOW_ARN,
        run_id=RUN_ID
    )
    
    if result:
        print(f"\n✅ Download and validation succeeded")
    else:
        print(f"\n❌ Download and validation failed")
    
    return result

if __name__ == "__main__":
    print("Testing Notebook Download Logic\n")
    print("=" * 60)
    
    # Test AWS CLI response
    cli_success = test_aws_cli_response()
    
    if not cli_success:
        print("\n❌ AWS CLI test failed")
        sys.exit(1)
    
    # Test download logic
    download_success = test_download_logic()
    
    if download_success:
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("❌ Download test failed")
        sys.exit(1)

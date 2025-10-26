#!/usr/bin/env python3
"""Quick test script for iterating on workflow creation."""

import boto3
import sys
import os
import json
import time
import logging

# Enable logging to see API calls
logging.basicConfig(level=logging.INFO, format='%(message)s')

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from smus_cicd.helpers import airflow_serverless

# ============================================================================
# CONFIGURATION - US-EAST-1 (ACTIVE)
# ============================================================================
REGION = "us-east-1"
DATAZONE_REGION = "us-east-1"
ENDPOINT_URL = "https://overdrive-gamma.us-east-1.api.aws"
WORKFLOW_NAME = f"test_debug_ml_workflow_{int(time.time())}"
ROLE_ARN = "arn:aws:iam::058264284947:role/datazone_usr_role_b3oxmwjmqclvl3_4a1eqm11kisn53"
S3_BUCKET = "smus-airflow-serverless-058264284947-us-east-1"
WORKFLOW_FILE = "examples/analytic-workflow/ml/workflows/ml_dev_workflow.yaml"

# DataZone configuration - US-EAST-1
DATAZONE_DOMAIN_ID = "dzd_6je2k8b63qse07"
DATAZONE_PROJECT_ID = "b3oxmwjmqclvl3"

# Network configuration - US-EAST-1 (using SageMaker Unified Studio VPC)
SECURITY_GROUP_IDS = ["sg-07ce34118d196989d"]
SUBNET_IDS = ["subnet-0e857a207d1e5b628", "subnet-05260c65533eb43be", "subnet-099d3bd861b50c36b"]

# Set environment variables for airflow_serverless helper
os.environ["AIRFLOW_SERVERLESS_ENDPOINT"] = ENDPOINT_URL
os.environ["AIRFLOW_SERVERLESS_REGION"] = REGION

# ============================================================================
# CONFIGURATION - US-WEST-2 (COMMENTED OUT)
# ============================================================================
# REGION = "us-west-2"
# DATAZONE_REGION = "us-west-2"
# ENDPOINT_URL = "https://overdrive-gamma.us-west-2.api.aws"
# WORKFLOW_NAME = "test_debug_ml_workflow"
# ROLE_ARN = "arn:aws:iam::058264284947:role/service-role/AmazonSageMakerAdminIAMExecutionRole_2"
# S3_BUCKET = "smus-airflow-serverless-058264284947-us-west-2"
# WORKFLOW_FILE = "examples/analytic-workflow/ml/workflows/ml_dev_workflow.yaml"
# 
# # DataZone configuration - US-WEST-2
# DATAZONE_DOMAIN_ID = "dzd-dcygqiyck8gcsw"
# DATAZONE_PROJECT_ID = "3mjrpe320r3d74"
# 
# # Network configuration - US-WEST-2 (using SageMaker Unified Studio VPC)
# SECURITY_GROUP_IDS = ["sg-0f1687f4c1b442074"]
# SUBNET_IDS = ["subnet-0f19c0a1709c709d2", "subnet-0d9f0dc1030294283", "subnet-06f1848bd87169347"]
# 
# # Set environment variables for airflow_serverless helper
# os.environ["AIRFLOW_SERVERLESS_ENDPOINT"] = ENDPOINT_URL
# os.environ["AIRFLOW_SERVERLESS_REGION"] = REGION
# ============================================================================

def fix_role_policy():
    """Fix IAM role trust policy and attach Admin policy."""
    import json
    
    iam = boto3.client("iam", region_name=DATAZONE_REGION)
    role_name = ROLE_ARN.split("/")[-1]
    
    # Fix trust policy
    try:
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": [
                            "airflow-serverless.amazonaws.com",
                            "airflow-serverless-gamma.amazonaws.com"
                        ]
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        iam.update_assume_role_policy(
            RoleName=role_name,
            PolicyDocument=json.dumps(trust_policy)
        )
    except Exception:
        pass  # May already be set
    
    # Attach Admin policy
    try:
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/AdministratorAccess"
        )
    except Exception:
        pass  # Already attached

def upload_workflow_to_s3():
    """Upload workflow YAML to S3."""
    s3_client = boto3.client('s3', region_name=REGION)
    s3_key = f"workflows/{WORKFLOW_NAME}.yaml"
    
    s3_client.upload_file(WORKFLOW_FILE, S3_BUCKET, s3_key)
    return {"Bucket": S3_BUCKET, "ObjectKey": s3_key}

def create_workflow(dag_s3_location):
    """Create Airflow Serverless workflow."""
    print(f"\n🚀 Creating workflow: {WORKFLOW_NAME}")
    
    try:
        result = airflow_serverless.create_workflow(
            workflow_name=WORKFLOW_NAME,
            dag_s3_location=dag_s3_location,
            role_arn=ROLE_ARN,
            datazone_domain_id=DATAZONE_DOMAIN_ID,
            datazone_domain_region=DATAZONE_REGION,
            datazone_project_id=DATAZONE_PROJECT_ID,
            security_group_ids=SECURITY_GROUP_IDS,
            subnet_ids=SUBNET_IDS,
            region=REGION
        )
        
        print(f"✅ Workflow ARN: {result['workflow_arn']}")
        return result
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        return None

def run_and_monitor_workflow(workflow_arn):
    """Run workflow and monitor until completion."""
    client = boto3.client(
        'awsoverdriveservice',
        region_name=REGION,
        endpoint_url=ENDPOINT_URL
    )
    
    print(f"\n🚀 Starting workflow run...")
    response = client.start_workflow_run(WorkflowArn=workflow_arn)
    run_id = response['RunId']
    print(f"✅ Run ID: {run_id}")
    
    print(f"\n⏳ Monitoring workflow...")
    start_time = time.time()
    timeout = 15 * 60
    
    while time.time() - start_time < timeout:
        runs = client.list_workflow_runs(WorkflowArn=workflow_arn, MaxResults=1)
        if runs['WorkflowRuns']:
            status = runs['WorkflowRuns'][0]['RunDetailSummary']['Status']
            elapsed = int(time.time() - start_time)
            print(f"  [{elapsed}s] Status: {status}")
            
            if status in ['SUCCEEDED', 'FAILED', 'STOPPED']:
                print(f"\n✅ Workflow completed: {status}")
                return run_id, status
        
        time.sleep(10)
    
    print(f"\n⚠️ Timeout after 15 minutes")
    return run_id, 'TIMEOUT'

def show_cloudwatch_logs(workflow_arn, run_id):
    """Display CloudWatch logs and extract errors."""
    logs_client = boto3.client('logs', region_name=REGION)
    
    workflow_name = workflow_arn.split('/')[-1]
    log_group = f"/aws/mwaa-serverless/{workflow_name}/"
    
    print(f"\n📋 CloudWatch Logs: {log_group}")
    print("=" * 80)
    
    try:
        streams = logs_client.describe_log_streams(
            logGroupName=log_group,
            orderBy='LastEventTime',
            descending=True,
            limit=10
        )
        
        errors = []
        for stream in streams['logStreams']:
            stream_name = stream['logStreamName']
            if run_id in stream_name:
                events = logs_client.get_log_events(
                    logGroupName=log_group,
                    logStreamName=stream_name,
                    startFromHead=True
                )
                
                for event in events['events']:
                    message = event['message'].strip()
                    # Collect error messages
                    if any(err in message.lower() for err in ['error', 'exception', 'failed', 'traceback']):
                        errors.append(message)
        
        if errors:
            print("\n❌ ERRORS FOUND:")
            print("-" * 80)
            for error in errors:
                print(error)
                print()
        else:
            print("✅ No errors found in logs")
    
    except Exception as e:
        print(f"⚠️ Could not retrieve logs: {e}")

def main():
    print("Quick Workflow Test")
    print("=" * 80)
    
    fix_role_policy()
    dag_s3_location = upload_workflow_to_s3()
    result = create_workflow(dag_s3_location)
    
    if result:
        run_id, status = run_and_monitor_workflow(result['workflow_arn'])
        show_cloudwatch_logs(result['workflow_arn'], run_id)
    else:
        print(f"\n❌ Test failed")
        sys.exit(1)

if __name__ == "__main__":
    main()

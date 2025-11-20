#!/usr/bin/env python3
"""Download notebook outputs from workflow using Airflow XCom data."""

import argparse
import boto3
import subprocess
import tarfile
import tempfile
from pathlib import Path


def download_workflow_outputs(workflow_name: str, region: str, output_dir: str = "tests/test-outputs/notebooks"):
    """Download notebook outputs from latest workflow run using XCom."""
    
    endpoint = f'https://airflow-serverless.{region}.api.aws/'
    client = boto3.client('mwaaserverless-internal', region_name=region, endpoint_url=endpoint)
    
    # Find workflow ARN
    response = client.list_workflows()
    workflow_arn = None
    for wf in response.get('Workflows', []):
        if workflow_name in wf.get('Name', ''):
            workflow_arn = wf.get('WorkflowArn')
            print(f"Found workflow: {wf.get('Name')}")
            print(f"  ARN: {workflow_arn}")
            break
    
    if not workflow_arn:
        print(f"❌ Workflow '{workflow_name}' not found")
        return []
    
    # Get latest run
    runs = client.list_workflow_runs(WorkflowArn=workflow_arn, MaxResults=1)
    if not runs.get('WorkflowRuns'):
        print("❌ No runs found")
        return []
    
    run_id = runs['WorkflowRuns'][0]['RunId']
    print(f"Latest Run ID: {run_id}\n")
    
    # Get task instances
    tasks = client.list_task_instances(WorkflowArn=workflow_arn, RunId=run_id)
    task_list = tasks.get('TaskInstances', [])
    
    if not task_list:
        print("❌ No task instances found")
        return []
    
    print(f"Found {len(task_list)} task(s)\n")
    
    downloaded_files = []
    output_path = Path(output_dir) / workflow_name.split('/')[-1] / run_id
    output_path.mkdir(parents=True, exist_ok=True)
    
    for task in task_list:
        task_id = task.get('TaskInstanceId')
        task_name = task.get('TaskId', 'unknown')
        
        # Get task details with XCom
        task_detail = client.get_task_instance(
            WorkflowArn=workflow_arn,
            RunId=run_id,
            TaskInstanceId=task_id
        )
        
        xcom = task_detail.get('Xcom', {})
        
        # Try different XCom keys
        s3_path = None
        for key in ['s3_path', 'sagemaker_unified_studio', 'notebook_output', 'return_value']:
            if key in xcom:
                s3_path = xcom[key]
                if isinstance(s3_path, str):
                    s3_path = s3_path.strip('"')
                    # Fix path: model.tar.gz -> output.tar.gz
                    if s3_path.endswith('/output/model.tar.gz'):
                        s3_path = s3_path.replace('/output/model.tar.gz', '/output/output.tar.gz')
                    break
        
        if not s3_path:
            print(f"⚠️  Task '{task_name}': No S3 output path in XCom")
            continue
        
        print(f"📓 Task: {task_name}")
        print(f"   S3: {s3_path}")
        
        # Download from S3
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp_path = tmp.name
        
        result = subprocess.run(
            ["aws", "s3", "cp", s3_path, tmp_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"   ❌ Download failed: {result.stderr}")
            Path(tmp_path).unlink(missing_ok=True)
            continue
        
        # Extract notebooks
        task_output_dir = output_path / task_name
        task_output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            with tarfile.open(tmp_path, "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name.startswith("_") and member.name.endswith(".ipynb"):
                        tar.extract(member, task_output_dir)
                        notebook_path = task_output_dir / member.name
                        downloaded_files.append(str(notebook_path))
                        print(f"   ✅ {notebook_path}")
        except Exception as e:
            print(f"   ❌ Extract failed: {e}")
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    
    print(f"\n✅ Downloaded {len(downloaded_files)} notebook(s)")
    for f in downloaded_files:
        print(f"   {f}")
    
    return downloaded_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download workflow outputs using Airflow XCom")
    parser.add_argument("workflow_name", help="Workflow name (e.g., IntegrationTestMLTraining_test_marketing_ml_training_workflow)")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--output-dir", default="tests/test-outputs/notebooks", help="Output directory")
    
    args = parser.parse_args()
    download_workflow_outputs(args.workflow_name, args.region, args.output_dir)

"""Test GenAI workflow execution and notebook outputs."""

import boto3
import pytest


def test_workflow_notebook_output_exists(s3_connection, project_id):
    """Verify that the workflow produced notebook output in S3."""
    s3_client = boto3.client("s3", region_name=s3_connection["region"])
    bucket = s3_connection["bucket"]
    prefix = s3_connection["prefix"]
    
    # Expected output path from workflow
    output_prefix = f"{prefix}genai/bundle/workflows/"
    
    # List objects to find notebook output
    response = s3_client.list_objects_v2(
        Bucket=bucket,
        Prefix=output_prefix
    )
    
    assert "Contents" in response, f"No files found in {output_prefix}"
    
    # Check for notebook file
    files = [obj["Key"] for obj in response["Contents"]]
    notebook_files = [f for f in files if f.endswith(".ipynb")]
    
    assert len(notebook_files) > 0, f"No notebook outputs found in {output_prefix}"
    print(f"✓ Found {len(notebook_files)} notebook output(s)")


def test_workflow_completed_successfully(workflow_connection, project_id):
    """Verify the workflow run completed successfully."""
    from smus_cicd.helpers.airflow_serverless import list_workflows, get_workflow_runs
    
    region = workflow_connection["region"]
    
    # List workflows to find our workflow
    workflows = list_workflows(region=region)
    assert workflows.get("success"), "Failed to list workflows"
    
    workflow_list = workflows.get("workflows", [])
    genai_workflows = [
        w for w in workflow_list 
        if "genai_dev_workflow" in w.get("Name", "")
    ]
    
    assert len(genai_workflows) > 0, "GenAI workflow not found"
    
    workflow_arn = genai_workflows[0]["Arn"]
    
    # Get recent runs
    runs = get_workflow_runs(workflow_arn, region=region)
    assert runs.get("success"), "Failed to get workflow runs"
    
    run_list = runs.get("runs", [])
    assert len(run_list) > 0, "No workflow runs found"
    
    # Check most recent run
    latest_run = run_list[0]
    status = latest_run.get("Status")
    
    assert status == "SUCCEEDED", f"Latest workflow run status: {status}"
    print(f"✓ Workflow completed successfully (run_id: {latest_run.get('RunId')})")

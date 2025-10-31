# Notebook Download Feature
**Date**: 2025-10-30
**Status**: ✅ Implemented

## What Was Added

Automatic download and extraction of executed notebook outputs after workflow completion.

## How It Works

### 1. After Workflow Execution
When a workflow with SageMakerNotebookOperator completes, the test automatically:
1. Parses CloudWatch logs to find notebook job names (e.g., `ml-orchestrator-notebook-UUID`)
2. Downloads the output tar.gz from DataZone S3 bucket
3. Extracts the notebook to `tests/test-outputs/`
4. Prints the path for easy access

### 2. Implementation Details

**New Method**: `download_notebook_outputs(workflow_arn, datazone_domain_id, datazone_project_id, region)`

**Process**:
```python
# 1. Get workflow run ID
runs = client.list_workflow_runs(WorkflowArn=workflow_arn)

# 2. Parse CloudWatch logs for notebook job names
log_group = f"/aws/mwaa-serverless/{workflow_name}/"
# Finds patterns like: ml-orchestrator-notebook-UUID

# 3. Download from DataZone S3
bucket = f"datazone-{account_id}-{region}-cicd-test-domain"
s3_key = f"{domain_id}/{project_id}/{env}/workflows/output/{job_name}/output/output.tar.gz"

# 4. Extract to tests/test-outputs/
tar.extractall(extract_dir)
```

**Location**: `tests/integration/analytic_workflow_pipeline/test_analytic_workflow_pipeline.py`

### 3. Integration

Added as **Step 9** in the test flow:
```
Step 6: Run Workflow
Step 7: Monitor Deployment  
Step 8: Get Workflow Logs
Step 9: Download Notebook Outputs  ← NEW
Cleanup
```

## Output Example

```
=== Downloading Notebook Outputs ===
✅ Downloaded: /Users/amirbo/code/smus/experimental/SMUS-CICD-pipeline-cli/tests/test-outputs/ml-orchestrator-notebook-abc123/output.ipynb
```

## Benefits

1. **Easy Debugging**: Immediately see executed notebook with outputs
2. **Verification**: Confirm all cells executed successfully
3. **Reproducibility**: Keep history of test executions
4. **No Manual Steps**: Automatic download, no need to manually fetch from S3

## File Structure

```
tests/test-outputs/
├── ml-orchestrator-notebook-UUID1/
│   └── output.ipynb                    ← Executed notebook
├── ml-orchestrator-notebook-UUID1.tar.gz
├── ml-orchestrator-notebook-UUID2/
│   └── output.ipynb
└── ...
```

## Usage

The feature runs automatically when:
- Workflow contains SageMakerNotebookOperator tasks
- Workflow execution completes (success or failure)
- CloudWatch logs contain notebook job names

No configuration needed - works out of the box!

## Error Handling

Gracefully handles:
- No workflow runs found
- No notebook jobs in logs
- S3 download failures
- Extraction errors

Prints warnings but doesn't fail the test.

## Future Enhancements

Potential improvements:
- [ ] Support multiple notebook operators in one workflow
- [ ] Download notebooks from failed workflows
- [ ] Clean up old notebook outputs (retention policy)
- [ ] Support other notebook formats (HTML, PDF)
- [ ] Add notebook diff comparison between runs

---
inclusion: manual
---

# Integration Test Execution Guide

## Test Structure Overview
Integration tests validate end-to-end CICD workflows in real AWS environments. Each test follows a standard pattern:
1. Cleanup existing resources
2. Describe pipeline configuration
3. Upload code to S3
4. Bundle deployment artifacts
5. Deploy to target environment
6. Run workflow
7. Monitor execution
8. Validate results

## Running Specific Integration Tests

### ML Training Workflow Test
**Purpose**: Tests ML training orchestrator with SageMaker and MLflow integration
**Location**: `tests/integration/examples-analytics-workflows/ml/test_ml_workflow.py`
**Duration**: ~11 minutes
**Environment**: Account 198737698272, us-east-1, test-marketing project

```bash
cd experimental/SMUS-CICD-pipeline-cli
pytest tests/integration/examples-analytics-workflows/ml/test_ml_workflow.py::TestMLWorkflow::test_ml_workflow_deployment -v -s
```

**What it validates**:
- MLflow ARN parameter injection via Papermill
- Dynamic connection fetching (S3, IAM, MLflow)
- SageMaker training job execution
- Model logging to MLflow tracking server
- Workflow completes with exit_code=0

**Key files**:
- Notebook: `examples/analytic-workflow/ml/workflows/ml_orchestrator_notebook.ipynb`
- Workflow: `examples/analytic-workflow/ml/workflows/ml_dev_workflow_v3.yaml`
- Pipeline: `examples/analytic-workflow/ml/ml_pipeline.yaml`

**Check notebooks (ALWAYS CHECK HERE FIRST)**:
```bash
# Check local test outputs (underscore-prefixed = actual outputs)
ls tests/test-outputs/notebooks/_*.ipynb
grep '"output_type": "error"' tests/test-outputs/notebooks/_*.ipynb

# If not local, download from S3
aws s3 ls s3://amazon-sagemaker-ACCOUNT-REGION-ID/shared/workflows/output/ --recursive | grep output.tar.gz
```

### ETL Workflow Test
**Purpose**: Tests Glue ETL jobs with parameter passing and database creation
**Location**: `tests/integration/examples-analytics-workflows/etl/test_etl_workflow.py`
**Duration**: ~10 minutes
**Environment**: Account 198737698272, us-east-1, test-marketing project

```bash
cd experimental/SMUS-CICD-pipeline-cli
pytest tests/integration/examples-analytics-workflows/etl/test_etl_workflow.py -v -s
```

**What it validates**:
- Glue job parameter passing via `run_job_kwargs.Arguments`
- S3 data cleanup before execution
- Database creation in Glue catalog
- Workflow completion polling (30s intervals, 10min timeout)
- All 4 parameters received by Glue job

**Key fix**: Use `run_job_kwargs.Arguments` instead of `script_args` in workflow YAML

**Key files**:
- Workflow: `examples/analytic-workflow/etl/s3_analytics_workflow.yaml`
- Glue scripts: `examples/analytic-workflow/etl/*.py`
- Pipeline: `examples/analytic-workflow/etl/etl_pipeline.yaml`

### Basic Pipeline Test
**Purpose**: Tests bootstrap actions (workflow.create, workflow.run) and expected workflow failures
**Location**: `tests/integration/basic_pipeline/test_basic_app.py`
**Duration**: ~15 minutes

```bash
cd experimental/SMUS-CICD-pipeline-cli
pytest tests/integration/basic_pipeline/test_basic_app.py -v -s
```

**What it validates**:
- Bootstrap actions execute in correct order (workflow.create before workflow.run)
- Deploy fails when workflow execution fails (expected_failure_workflow)
- Workflow status correctly reported in monitor output
- Parameter substitution with environment variables (${AWS_ACCOUNT_ID})
- MLflow connection configuration without trackingServerName field

**Key behaviors**:
- expected_failure_workflow is designed to fail - deploy should fail and test verifies this
- Test checks workflow statuses from monitor output, not by manually starting workflows
- Uses environment variables for account-specific values (no hardcoded ARNs)

## Test Output Locations
- **Logs**: `tests/test-outputs/{TestClass}__{test_method}.log`
- **Notebooks**: `tests/test-outputs/notebooks/_*.ipynb` (underscore = actual outputs)
- **Reports**: `tests/reports/test-results.html`
- **Coverage**: `tests/reports/coverage/`

## Common Test Patterns

**Parameter Injection Pattern** (ML/Basic tests):
1. Workflow YAML defines `input_params` with variable substitution
2. Papermill injects parameters into tagged cell
3. Notebook receives parameters as variables
4. Verify in executed notebook's "injected-parameters" cell

**Workflow Monitoring Pattern** (All tests):
1. Start workflow with `run` command
2. Poll status with `monitor` command
3. Fetch logs with `logs --live` command
4. Wait for "Task finished" with exit_code=0

**S3 Artifact Pattern** (ML/ETL tests):
1. Bundle creates compressed archives
2. Deploy uploads to `s3://{bucket}/shared/{path}/`
3. Workflow references S3 paths
4. Download outputs from `s3://{bucket}/shared/workflows/output/`

## Debugging Failed Tests

**Check workflow status**:
```bash
# List workflows
aws mwaaserverless list-workflows --region us-east-2 --endpoint-url https://airflow-serverless.us-east-2.api.aws/

# Check runs
aws mwaaserverless list-workflow-runs --workflow-arn ARN --region us-east-2 --endpoint-url https://airflow-serverless.us-east-2.api.aws/
```

**Check notebooks (ALWAYS CHECK HERE FIRST)**:
```bash
# Check local (underscore-prefixed = actual outputs)
ls tests/test-outputs/notebooks/_*.ipynb
grep '"output_type": "error"' tests/test-outputs/notebooks/_*.ipynb

# If not local, use download script
python tests/scripts/download_workflow_outputs.py --workflow-arn <ARN>
# Downloads to /tmp/workflow_outputs/
```

**Check Glue job parameters**:
```bash
aws glue get-job-run --job-name JOB_NAME --run-id RUN_ID --query 'JobRun.Arguments'
```

**Workflow Output Validation (After Test Completion)**

After a workflow test completes, validate notebook outputs for errors:

```bash
# Download and analyze workflow outputs in one command
./tests/scripts/validate_workflow_run.sh <workflow_name> [region]

# Example:
./tests/scripts/validate_workflow_run.sh IntegrationTestMLTraining_test_marketing_ml_training_workflow us-east-1

# Or run steps separately:

# Step 1: Download notebook outputs from workflow
python3 tests/scripts/download_workflow_outputs_from_xcom.py <workflow_name> --region us-east-1

# Step 2: Analyze notebooks for errors
python3 tests/scripts/analyze_notebook_errors.py tests/test-outputs/notebooks --verbose

# Step 3: Open notebooks with errors for inspection
python3 tests/scripts/analyze_notebook_errors.py tests/test-outputs/notebooks --open-errors
```

**What the validation does:**
1. Downloads executed notebook outputs from Airflow XCom (S3)
2. Analyzes notebooks for errors (error output types, display errors, stream errors)
3. Reports cell numbers and error details
4. Optionally opens notebooks with errors in your editor

**When to use:**
- After any workflow test completes (pass or fail)
- When debugging workflow execution issues
- To verify notebook cells executed correctly
- To inspect actual error messages from failed cells

Important Note: These are pytest-based integration tests, NOT Hydra tests. Do not attempt to run them using the Hydra test platform.

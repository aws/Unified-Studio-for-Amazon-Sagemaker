# Code Assist Script

## Q Task Tracking

Task progress and context are tracked in the `q-tasks/` folder:
- Location: `experimental/SMUS-CICD-pipeline-cli/q-tasks/`
- Files: `q-task-*.txt` (e.g., `q-task-build-ml-workflow.txt`)
- Purpose: Track progress, environment setup, debugging steps, and next actions
- Note: This folder is git-ignored for local development tracking only

## Automated Workflow for Code Changes

When making any code changes to the SMUS CI/CD CLI, follow this automated workflow to ensure consistency and quality:

### 0. AWS Credentials Setup (when needed)
```bash
# Check AWS credentials using test runner
python tests/run_tests.py --type integration
# If credentials are missing, you'll see a warning

# Or manually:
isenguardcli
aws sts get-caller-identity
```

### 1. Pre-Change Validation
```bash
# Verify current state is clean
python tests/run_tests.py --type unit
python tests/run_tests.py --type integration
git status
```

### 2. Make Code Changes
- Implement the requested feature/fix
- Update relevant docstrings and comments
- **Follow PEP 8 style guide**: https://peps.python.org/pep-0008/
  - Imports should be at the top of the file (after docstrings, before code)
  - Use proper whitespace around operators
  - Avoid unused imports and variables
  - Use regular strings instead of f-strings when no placeholders are needed
- **For DataZone catalog asset features**: Ensure proper exception handling - DataZone helper functions should raise exceptions instead of returning None/False to ensure proper CLI exit codes
- **Always run linting checks after code changes:**
  ```bash
  # Check code formatting and imports
  flake8 src/smus_cicd/ --config=setup.cfg
  black --check src/smus_cicd/
  isort --check-only src/smus_cicd/
  
  # Auto-fix formatting issues
  black src/smus_cicd/
  isort src/smus_cicd/
  ```

### 3. Update Test Cases
```bash
# Run tests to identify failures
python tests/run_tests.py --type unit

# Fix any failing tests by:
# - Updating test expectations to match new behavior
# - Adding new test cases for new functionality
# - Ensuring mock objects match actual implementation
# - Verifying CLI parameter usage is correct
```

### 4. Update README and Documentation
```bash
# Update README.md if:
# - CLI syntax changed
# - New commands added
# - Examples need updating
# - Diagrams need modification

# Verify examples work by running tests
python tests/run_tests.py --type all
```

### 5. Integration Test Validation
```bash
# Run integration tests with detailed logging (RECOMMENDED)
python run_integration_tests_with_logs.py

# This creates:
# - tests/test-outputs/{test_name}.log for each test's full output
# - tests/test-outputs/test_results_summary.json with detailed results
# - tests/test-outputs/test_results_summary.txt with human-readable summary

# Alternative: Run integration tests without detailed logging
python tests/run_tests.py --type integration

# For faster iteration, skip slow tests:
python tests/run_tests.py --type integration --skip-slow
```

### 6. Final Validation and Commit
```bash
# Full validation with coverage
python tests/run_tests.py --type all

# Commit changes
git add .
git commit -m "Descriptive commit message

- List specific changes made
- Note test updates
- Note documentation updates"

# Verify clean state
git status
```

### 7. Push Changes and Monitor PR
```bash
# Push changes to GitHub
git push origin your_feature_branch

# Wait 5 minutes for CI/CD to process
sleep 300

# Check PR status and analyze test results
gh pr checks <PR-NUMBER>

# Get detailed logs for any failing tests
gh run view <RUN-ID> --job <JOB-NAME> --log

# Analyze failures and provide summary:
# - What tests are failing and why
# - Root cause analysis of failures
# - Recommended fixes needed
# - Whether failures are related to code changes or infrastructure

# IMPORTANT: Do not push additional changes without approval
# - Present analysis of test failures first
# - Wait for confirmation before implementing fixes
# - Ensure all stakeholders understand the impact
```

## Test Runner Options

```bash
# Available test types:
python tests/run_tests.py --type unit           # Unit tests only
python tests/run_tests.py --type integration    # Integration tests only
python tests/run_tests.py --type all            # All tests (default)

# Additional options:
--no-coverage        # Skip coverage analysis
--no-html-report    # Skip HTML test results and coverage reports
--skip-slow         # Skip slow tests (marked with @pytest.mark.slow)
--coverage-only     # Only generate coverage report from existing data

# Alternative using pytest directly:
pytest tests/unit/                          # Unit tests
pytest tests/integration/ -m "not slow"     # Integration tests (skip slow)
```

## Integration Test Execution Guide (GenAI Reference)

### Test Structure Overview
Integration tests validate end-to-end CICD workflows in real AWS environments. Each test follows a standard pattern:
1. Cleanup existing resources
2. Describe pipeline configuration
3. Upload code to S3
4. Bundle deployment artifacts
5. Deploy to target environment
6. Run workflow
7. Monitor execution
8. Validate results

### Running Specific Integration Tests

#### ML Training Workflow Test
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

**Download executed notebook**:
```bash
# Find latest output
aws s3 ls s3://amazon-sagemaker-198737698272-us-east-1-4pg255jku47vdz/shared/workflows/output/ml/bundle/workflows/ --recursive | grep output.tar.gz | sort | tail -1

# Download and extract
aws s3 cp s3://amazon-sagemaker-198737698272-us-east-1-4pg255jku47vdz/PATH /tmp/ml_output.tar.gz
cd /tmp && tar -xzf ml_output.tar.gz
# View: /tmp/_ml_orchestrator_notebook.ipynb
```

#### ETL Workflow Test
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

#### Basic Pipeline Test
**Purpose**: Tests parameter passing from workflow to notebook via Papermill
**Location**: `tests/integration/basic_pipeline/test_basic_pipeline.py`
**Duration**: ~15 minutes

```bash
cd experimental/SMUS-CICD-pipeline-cli
pytest tests/integration/basic_pipeline/test_basic_pipeline.py -v -s
```

**What it validates**:
- Variable substitution: `{proj.connection.mlflow-server.trackingServerArn}`
- Papermill parameter injection to notebooks
- Parameters cell tagging and injection
- Workflow execution and completion

### Unit Tests
```bash
cd experimental/SMUS-CICD-pipeline-cli
python -m pytest tests/unit -v
```

### All Integration Tests
```bash
cd experimental/SMUS-CICD-pipeline-cli
python -m pytest tests/integration -v
```

### Test Output Locations
- **Logs**: `tests/test-outputs/{TestClass}__{test_method}.log`
- **Reports**: `tests/reports/test-results.html`
- **Coverage**: `tests/reports/coverage/`

### Common Test Patterns

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

### Debugging Failed Tests

**Check workflow status**:
```bash
# List workflows
aws awsoverdriveservice list-workflows --region us-east-1 --endpoint-url https://overdrive-gamma.us-east-1.api.aws

# Check runs
aws awsoverdriveservice list-workflow-runs --workflow-arn ARN --region us-east-1 --endpoint-url https://overdrive-gamma.us-east-1.api.aws
```

**Download workflow outputs** (notebooks, artifacts):
```bash
# Use the automated download script
python tests/scripts/download_workflow_outputs.py --workflow-arn <WORKFLOW_ARN>

# This script:
# - Finds the latest workflow run automatically
# - Downloads all notebook outputs to /tmp/workflow_outputs/
# - Extracts tar.gz files automatically
# - Shows underscore-prefixed notebooks (true outputs with execution results)
# - Provides paths to all downloaded files

# Example output location: /tmp/workflow_outputs/_notebook_name.ipynb
```

**Check notebook execution**:
```bash
# Search for errors in executed notebook
cat /tmp/_notebook.ipynb | jq -r '.cells[] | select(.outputs != null) | select(.outputs[] | .output_type == "error") | "Cell \(.execution_count): \(.outputs[].ename)"'
```

**Check Glue job parameters**:
```bash
aws glue get-job-run --job-name JOB_NAME --run-id RUN_ID --query 'JobRun.Arguments'
```

Important Note: These are pytest-based integration tests, NOT Hydra tests. Do not attempt to run them using the Hydra test platform.

## Checklist for Any Code Change

- [ ] AWS credentials configured (when needed)
- [ ] **Code formatting and imports are clean:**
  - [ ] `flake8 src/smus_cicd/ --config=setup.cfg` passes
  - [ ] `black --check src/smus_cicd/` passes  
  - [ ] `isort --check-only src/smus_cicd/` passes
- [ ] Unit tests pass
- [ ] Integration tests pass (basic suite)
- [ ] README examples are accurate and tested
- [ ] CLI help text is updated if needed
- [ ] New functionality has corresponding tests
- [ ] Mock objects match real implementation
- [ ] CLI parameter usage is consistent
- [ ] Documentation reflects actual behavior
- [ ] Check that the code and markdown files don't contain aws account ids, web addresses, or host names. Mask all of these before committing.
- [ ] Check that lint is passing
- [ ] Don't swallow exceptions, if an error is thrown, it must be logged or handled
- [ ] All changes are committed
- [ ] **PR Monitoring and Analysis:**
  - [ ] Changes pushed to GitHub
  - [ ] PR status monitored for 5+ minutes
  - [ ] All CI/CD workflows analyzed
  - [ ] Test failures documented with root cause analysis
  - [ ] Summary of failures provided before additional changes
  - [ ] Approval received before pushing fixes

## Common Test Patterns to Maintain

### Unit Test Patterns
- Mock objects need proper attributes, not dictionaries
- Test expectations should match actual output format
- Use proper patch decorators for dependencies

### Integration Test Patterns
- Use `["describe", "--pipeline", file]` not `["describe", file]`
- Expected exit codes should match test framework expectations
- Rename DAG files to avoid pytest collection (`.dag` extension)

### README Patterns
- All CLI examples use correct parameter syntax
- Include realistic command outputs
- Keep examples concise but informative
- Verify examples actually work before documenting

## Project Structure (Python-Native)

```
smus_cicd/
├── pyproject.toml          # Modern Python project config
├── tests/
│   └── run_tests.py       # Test runner script
├── smus_cicd/             # Main package
├── tests/                 # Test suite
└── README.md              # Documentation
```

## AWS Credential Management

When you need to refresh AWS credentials:
1. Run `isenguardcli` to get fresh credentials
2. Verify with `aws sts get-caller-identity`
3. Run a test command to confirm: `python tests/run_tests.py --type integration`

This script ensures that every code change maintains the quality and consistency of the codebase using Python-native tools.

## GitHub PR Validation Using GitHub CLI

### View PR Status and Checks
```bash
# View PR details including status checks
gh pr view <PR-NUMBER> --json statusCheckRollup

# View specific check run logs
gh run view <RUN-ID> --job <JOB-NAME> --log

# List all check runs for a PR
gh pr checks <PR-NUMBER>

# View PR diff
gh pr diff <PR-NUMBER>

# View PR comments and reviews
gh pr view <PR-NUMBER> --json comments,reviews
```

### Common GitHub CLI Commands for PR Review
```bash
# List all open PRs
gh pr list

# Check out PR locally
gh pr checkout <PR-NUMBER>

# View PR status
gh pr status

# Add a comment to PR
gh pr comment <PR-NUMBER> --body "Your comment here"

# Request changes or approve PR
gh pr review <PR-NUMBER> --approve
gh pr review <PR-NUMBER> --request-changes --body "Changes needed"
```

### Monitoring CI/CD Pipeline Status
```bash
# View recent workflow runs
gh run list --workflow=".github/workflows/pr-integration-tests.yml"

# Watch workflow run in real-time
gh run watch

# Download workflow artifacts
gh run download <RUN-ID>
```

Note: Replace `<PR-NUMBER>` with the actual PR number and `<RUN-ID>` with the actual run ID from the GitHub Actions workflow.

## Airflow Serverless (Overdrive) Environment Configuration

When working with airflow-serverless workflows, always determine the current environment configuration dynamically:

### Environment Variables Check
```bash
# Check current airflow-serverless endpoint
echo $AIRFLOW_SERVERLESS_ENDPOINT

# Check current AWS region
echo $AWS_DEFAULT_REGION

# Check current AWS account
aws sts get-caller-identity --query Account --output text

# Get all relevant environment variables
env | grep -E "(AWS_REGION|AWS_DEFAULT_REGION|AWS_ACCOUNT|AIRFLOW_SERVERLESS|OVERDRIVE)" | sort
```

### Dynamic Configuration Pattern
When updating documentation or code, use this approach to get current values:
- **Endpoint**: Read from `$AIRFLOW_SERVERLESS_ENDPOINT` environment variable
- **Region**: Read from `$AWS_DEFAULT_REGION` or `$AWS_REGION` environment variable  
- **Account**: Get from `aws sts get-caller-identity --query Account --output text`
- **IAM Role Pattern**: `arn:aws:iam::{account}:role/datazone_usr_role_{project_id}_{environment_id}`

### Important Notes
- Never hardcode account IDs, regions, or endpoints in permanent documentation
- Always reference environment variables or provide commands to determine current values
- The airflow-serverless service may use different endpoints/regions across environments
- Use `aws sts get-caller-identity` to verify you're working with the correct AWS account

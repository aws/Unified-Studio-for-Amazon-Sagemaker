# Code Assist Script

## AI Assistant Rules

**CRITICAL: Never commit code or push changes without explicit request from user.**

**CRITICAL: For non-trivial changes (beyond syntax errors or simple fixes), request approval before making significant flow or architectural changes.**

## Q Task Tracking

Task progress and context are tracked in the `q-tasks/` folder:
- Location: `experimental/SMUS-CICD-pipeline-cli/q-tasks/`
- Files: `q-task-*.txt` (e.g., `q-task-build-ml-workflow.txt`)
- Purpose: Track progress, environment setup, debugging steps, and next actions
- Note: This folder is git-ignored for local development tracking only

## Test Account Setup

### Account Types

**IAM-Based Domains** (Simpler setup - no IDC required)
- Steps: 1 → 4 → 5
- Location: `tests/scripts/setup/iam-based-domains/`

**IDC-Based Domains** (Full setup with IAM Identity Center)
- Steps: 1 → 2 → 3 → 4 → 5
- Location: `tests/scripts/setup/idc-based-domains/`

### Setup Steps

#### Step 1: Account Setup
```bash
cd tests/scripts/setup/{domain-type}/1-account-setup
./deploy.sh
```
Creates:
- VPC and networking
- IAM roles for GitHub Actions
- Stage-specific IAM roles (dev/test/prod)

#### Step 2: Domain Creation (IDC only)
```bash
cd tests/scripts/setup/idc-based-domains/2-domain-creation
./deploy.sh
```
Creates SageMaker Unified Studio domain with IDC integration.

#### Step 3: Domain Configuration (IDC only)
```bash
cd tests/scripts/setup/idc-based-domains/3-domain-configuration
./deploy.sh
```
Configures domain blueprints and profiles.

#### Step 4: Project Setup
```bash
cd tests/scripts/setup/{domain-type}/4-project-setup
./deploy.sh
```
Creates SMUS projects (dev-marketing, test-marketing).

#### Step 5: Testing Infrastructure and Data
```bash
# Deploy infrastructure (MLflow, IAM roles, S3)
cd tests/scripts/setup/{domain-type}/5-testing-infrastructure/testing-infrastructure
./deploy.sh us-east-1

# Deploy test data (ML datasets, COVID data)
cd ../testing-data
./deploy.sh us-east-1
```

**Infrastructure creates:**
- MLflow tracking server
- SageMaker execution role
- S3 artifacts bucket

**Test data creates:**
- ML training/inference datasets (always)
- COVID-19 catalog data (optional, requires DataZone)

**Outputs saved to `/tmp/`:**
- `mlflow_arn_{region}.txt`
- `sagemaker_role_arn_{region}.txt`
- `mlflow_bucket_{region}.txt`
- `ml_bucket_{region}.txt`

### Quick Start (IAM-Based)

```bash
cd tests/scripts/setup/iam-based-domains

# Step 1: Account base setup
cd 1-account-setup && ./deploy.sh && cd ..

# Step 4: Create projects
cd 4-project-setup && ./deploy.sh && cd ..

# Step 5: Deploy infrastructure and data
cd 5-testing-infrastructure/testing-infrastructure && ./deploy.sh us-east-1 && cd ..
cd testing-data && ./deploy.sh us-east-1
```

### Environment Variables

After setup, export these for integration tests:
```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export TEST_DOMAIN_REGION=us-east-1
export DEV_DOMAIN_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
```

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
# Run with detailed logging (creates logs in tests/test-outputs/)
python run_integration_tests_with_logs.py

# Or without logging
python tests/run_tests.py --type integration

# Skip slow tests
python tests/run_tests.py --type integration --skip-slow
```

**IMPORTANT: Verifying Test Results**
- NEVER re-run test to check if it passed
- ALWAYS check logs first: `tests/test-outputs/{test_name}.log`
- ALWAYS check notebooks: `tests/test-outputs/notebooks/` (underscore-prefixed = actual outputs)

```bash
# Check logs and notebooks
cat tests/test-outputs/TestMLWorkflow__test_ml_workflow_deployment.log
ls tests/test-outputs/notebooks/_*.ipynb
grep -i "error\|failed\|exception" tests/test-outputs/*.log
```

**CRITICAL: Integration Tests Are Slow (10-15 min) - Test Fixes Quickly First**

1. Identify issue from logs/notebooks
2. Create small test script (30 sec - 1 min)
3. Iterate on fix with small script
4. Only then run full integration test

```bash
# Quick test examples:
# Notebook: python -c "import papermill as pm; pm.execute_notebook('nb.ipynb', '/tmp/out.ipynb', parameters={'p': 'v'})"
# Manifest: python -c "from smus_cicd.application.application_manifest import ApplicationManifest; m = ApplicationManifest.from_file('manifest.yaml'); print(m.initialization)"
# CLI: smus-cli describe --manifest manifest.yaml

# Run full integration test only after fix confirmed working
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

# Download combined coverage report
gh run download <RUN-ID> -n test-summary-combined
python tests/scripts/combine_coverage.py --coverage-dir tests/test-outputs/coverage-artifacts

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

### PR Test Structure

**Automatic test discovery** - no workflow updates needed when adding tests.

**Adding New Tests**:
```bash
tests/integration/my_new_app/
  └── test_my_new_app.py  # Auto-discovered!
```

**Coverage combining**:
```bash
gh run download <RUN_ID> -n test-summary-combined
python tests/scripts/combine_coverage.py
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

**Check notebooks (ALWAYS CHECK HERE FIRST)**:
```bash
# Check local test outputs (underscore-prefixed = actual outputs)
ls tests/test-outputs/notebooks/_*.ipynb
grep '"output_type": "error"' tests/test-outputs/notebooks/_*.ipynb

# If not local, download from S3
aws s3 ls s3://amazon-sagemaker-ACCOUNT-REGION-ID/shared/workflows/output/ --recursive | grep output.tar.gz
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
**Location**: `tests/integration/basic_pipeline/test_basic_app.py`
**Duration**: ~15 minutes

```bash
cd experimental/SMUS-CICD-pipeline-cli
pytest tests/integration/basic_pipeline/test_basic_app.py -v -s
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
- **Notebooks**: `tests/test-outputs/notebooks/_*.ipynb` (underscore = actual outputs)
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
  ```bash
  # Run automated check for hardcoded values
  ./tests/scripts/check-hardcoded-values.sh
  
  # This checks for:
  # - AWS Account IDs (12-digit numbers)
  # - Hardcoded AWS regions in code
  # - Hardcoded AWS endpoints
  # - IP addresses
  # - IAM role ARNs with account IDs
  # - S3 bucket names with account IDs
  # - Internal hostnames
  # - Email addresses
  
  # If issues found, fix them:
  # - Account IDs: Use boto3.client('sts').get_caller_identity()['Account']
  # - Regions: Use os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
  # - Endpoints: Use environment variables or dynamic lookup
  # - Emails: Use placeholders like user@example.com
  ```
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

### AWS Service Name (Pre-GA)
**IMPORTANT**: Until the service is fully GA, use the internal service name:
- **Service Name**: `mwaaserverless-internal` (NOT `airflow-serverless`)
- **Endpoint**: `https://airflow-serverless.{region}.api.aws/`
- This is already configured in `src/smus_cicd/helpers/airflow_serverless.py`

### AWS CLI Commands
```bash
# List available commands
aws mwaaserverless-internal help

# Get workflow run status
aws mwaaserverless-internal get-workflow-run \
  --workflow-arn "arn:aws:airflow-serverless:REGION:ACCOUNT:workflow/NAME" \
  --run-id "RUN_ID" \
  --region REGION \
  --endpoint-url "https://airflow-serverless.REGION.api.aws/"

# List workflows
aws mwaaserverless-internal list-workflows \
  --region REGION \
  --endpoint-url "https://airflow-serverless.REGION.api.aws/"

# List workflow runs
aws mwaaserverless-internal list-workflow-runs \
  --workflow-arn "ARN" \
  --region REGION \
  --endpoint-url "https://airflow-serverless.REGION.api.aws/"
```

### API Response Structure
The `get-workflow-run` API returns status in `RunDetail.RunState`, not `Status`:
```json
{
  "Status": null,
  "RunDetail": {
    "RunState": "SUCCESS",  // Actual status field
    "StartedOn": "...",
    "CompletedOn": "...",
    "Duration": 751
  }
}
```

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
- **Service Name**: `mwaaserverless-internal` (hardcoded until GA)
- **Endpoint**: Read from `$AIRFLOW_SERVERLESS_ENDPOINT` or default to `https://airflow-serverless.{region}.api.aws/`
- **Region**: Read from `$AWS_DEFAULT_REGION` or `$AWS_REGION` environment variable  
- **Account**: Get from `aws sts get-caller-identity --query Account --output text`
- **IAM Role Pattern**: `arn:aws:iam::{account}:role/datazone_usr_role_{project_id}_{environment_id}`

### Important Notes
- Never hardcode account IDs, regions, or endpoints in permanent documentation
- Always reference environment variables or provide commands to determine current values
- The airflow-serverless service may use different endpoints/regions across environments
- Use `aws sts get-caller-identity` to verify you're working with the correct AWS account
- **Pre-GA**: Service name is `mwaaserverless-internal` - this will change to `airflow-serverless` at GA

### Verify No Hardcoded Values
Before committing code, run the automated check:
```bash
./tests/scripts/check-hardcoded-values.sh
```

This script checks for:
- AWS Account IDs (12-digit numbers)
- Hardcoded AWS regions in code (not in config files)
- Hardcoded AWS endpoints
- IP addresses
- IAM role ARNs with account IDs
- S3 bucket names with account IDs
- Internal hostnames
- Email addresses (potential PII)

**How to fix issues:**
```python
# ❌ Bad - Hardcoded account ID
account_id = "123456789012"

# ✅ Good - Dynamic lookup
account_id = boto3.client('sts').get_caller_identity()['Account']

# ❌ Bad - Hardcoded region
region = "us-east-1"

# ✅ Good - Environment variable with default
region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')

# ❌ Bad - Hardcoded endpoint
endpoint = "https://airflow-serverless.us-east-1.api.aws/"

# ✅ Good - Environment variable
endpoint = os.environ.get('AIRFLOW_SERVERLESS_ENDPOINT', 
                         f'https://airflow-serverless.{region}.api.aws/')
```

## GitHub Deployment Workflows

### Approval Protocol

**Q Must Ask Before:**
- ✋ Committing code changes
- ✋ Pushing to remote repository
- ✋ Triggering workflows
- ✋ Deleting files or branches
- ✋ Merging branches

**Q Can Do Without Asking:**
- ✅ Reading files
- ✅ Analyzing logs
- ✅ Running local tests
- ✅ Checking git status
- ✅ Monitoring workflow status
- ✅ Suggesting fixes

**Approval Keywords:**
- "yes" / "ok" / "do it" / "fix" / "apply" → Proceed
- "no" / "wait" / "stop" / "don't" → Do not proceed
- "show me" / "what would" / "options" → Explain without doing

### Triggering Workflows
```bash
# Trigger all workflows
bash tests/scripts/trigger-workflows.sh all

# Trigger specific workflow
bash tests/scripts/trigger-workflows.sh genai
bash tests/scripts/trigger-workflows.sh ml-training
```

### Monitoring Workflows
```bash
# List recent workflow runs
gh run list --branch <branch-name> --limit 10

# View specific run
gh run view <run-id>

# View specific job
gh run view <run-id> --job <job-id>

# Get logs from failed job
gh api repos/aws/Unified-Studio-for-Amazon-Sagemaker/actions/jobs/<job-id>/logs

# Search for errors in logs
gh api repos/aws/Unified-Studio-for-Amazon-Sagemaker/actions/jobs/<job-id>/logs | grep -A 20 "Error"
```

### 4-Phase Workflow Process

**1. Analysis Phase**
- Monitor GitHub workflow runs
- Download logs from failed jobs
- Analyze errors and identify root cause
- Suggest specific fixes with code examples

**2. Approval Phase**
- Wait for user approval before committing/pushing/triggering
- User reviews suggested fixes
- User explicitly approves with keywords

**3. Implementation Phase**
- Apply the fix
- Run unit tests locally
- Commit with descriptive message
- Push to branch
- Trigger workflows if needed

**4. Monitoring Phase**
- Check workflow status
- Report success/failure
- If failure, return to Analysis Phase

### Bundle Artifact Pattern

Use temp directory with unique run ID to prevent stale artifacts:

```yaml
# Bundle step
BUNDLE_DIR="${{ runner.temp }}/smus-bundles-${{ github.run_id }}"
smus-cli bundle --output-dir "$BUNDLE_DIR"

# Upload
path: ${{ env.BUNDLE_DIR }}/*.zip

# Download
path: ${{ runner.temp }}/smus-bundles-${{ github.run_id }}

# Deploy
BUNDLE_FILE=$(ls ${{ runner.temp }}/smus-bundles-${{ github.run_id }}/*.zip | head -1)
smus-cli deploy --bundle-archive-path "$BUNDLE_FILE"
```

**Impact:** Clean isolation per run, no stale artifacts, guaranteed only uploads what was just created.

### Common Workflow Failures

**Environment Protection**
- Error: "Branch not allowed to deploy to dev-aws-account"
- Cause: Branch not in environment's allowed deployment branches
- Fix: Add branch to environment protection rules or use different branch

**Bundle Not Found**
- Error: "No files were found with the provided path"
- Cause: Bundle path mismatch between creation and upload
- Fix: Use temp directory approach (see Bundle Artifact Pattern above)

**DataZone API Errors**
- Error: "Unknown parameter in input: customerProvidedRoleConfigs"
- Cause: Missing DataZone model registration
- Fix: Register model with `aws configure add-model`

**Project Creation Failures**
- Error: "Failed to create project"
- Cause: Missing project info in metadata or invalid API parameters
- Fix: Ensure metadata initialization and DataZone model registration

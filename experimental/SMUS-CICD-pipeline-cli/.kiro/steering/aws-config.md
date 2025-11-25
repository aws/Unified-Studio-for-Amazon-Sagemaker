---
inclusion: manual
---

# AWS Configuration and Setup

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

After setup, configure environment variables for integration tests:

```bash
# Copy template and customize for your account
cp env-example.env env-local.env

# Edit env-local.env with your account-specific values:
# - AWS_ACCOUNT_ID
# - Domain IDs and regions
# - Project IDs
# - MLflow server names
# - S3 bucket names

# Source before running tests
source env-local.env

# Verify configuration
python tests/run_tests.py --type integration
```

**Configuration approach:**
- All test configuration comes from environment variables only
- No config files loaded by test infrastructure (conftest.py)
- Use `env-*.env` files for account-specific values (git-ignored)
- Template provided in `env-example.env`

## AWS Credential Management

When you need to refresh AWS credentials:
1. Run `isenguardcli` to get fresh credentials
2. Verify with `aws sts get-caller-identity`
3. Run a test command to confirm: `python tests/run_tests.py --type integration`

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

## GitHub Deployment Workflows

### GitHub PR Validation Using GitHub CLI

**View PR Status and Checks**
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

**Common GitHub CLI Commands for PR Review**
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

**Monitoring CI/CD Pipeline Status**
```bash
# View recent workflow runs
gh run list --workflow=".github/workflows/pr-integration-tests.yml"

# Watch workflow run in real-time
gh run watch

# Download workflow artifacts
gh run download <RUN-ID>
```

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

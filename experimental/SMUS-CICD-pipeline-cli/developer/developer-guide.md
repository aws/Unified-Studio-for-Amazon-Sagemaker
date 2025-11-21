# SMUS CI/CD Developer Guide

## 1. Quick Start

### Prerequisites
- Python 3.7 or higher
- pip package manager
- AWS CLI configured with appropriate credentials
- yq (YAML processor) - `brew install yq` (macOS) or `apt-get install yq` (Ubuntu)

### Installation

```bash
# Clone the repository
cd experimental/SMUS-CICD-pipeline-cli

# Install in development mode
pip install -e ".[dev]"
```

### Basic CLI Usage

```bash
# Run the CLI
smus-cli --help

# Or using Python module
python -m smus_cicd.cli --help
```

## 2. AI Assistant Context (AmazonQ.md)

### 2.1 Purpose
The `developer/AmazonQ.md` file is a comprehensive development guide specifically designed for AI assistants (Amazon Q, Kiro, etc.). It contains:
- Automated workflows for code changes
- Test execution patterns and commands
- Integration test guides and debugging procedures
- AWS credential management
- GitHub PR validation procedures
- Airflow Serverless configuration
- Complete development checklists

### 2.2 Using with Kiro Agent

**Loading Context:**
Reference `experimental/SMUS-CICD-pipeline-cli/developer/AmazonQ.md` at the start of your conversation to load full development context.

**What It Contains:**
- **7-Step Automated Workflow**: Pre-validation → Changes → Tests → Docs → Integration → Commit → PR monitoring
- **Test Execution Guide**: ML workflow, ETL workflow, Basic Pipeline tests with durations and validation steps
- **GitHub PR Validation**: Using GitHub CLI for monitoring, 4-phase workflow process
- **Airflow Serverless Config**: Pre-GA service name, dynamic configuration patterns, API response structure
- **Common Test Patterns**: Unit test patterns, integration test patterns, README patterns

**Critical Rules:**
- Never commit code or push changes without explicit approval
- Always check logs and notebooks first before re-running tests
- Use quick test scripts (30s-1min) before full integration tests (10-15min)
- No hardcoded account IDs, regions, or endpoints

### 2.3 Key Sections

**Automated Workflow for Code Changes:**
1. Pre-change validation (unit + integration tests)
2. Make code changes (PEP 8, linting)
3. Update test cases
4. Update README and documentation
5. Integration test validation
6. Final validation and commit
7. Push changes and monitor PR

**Integration Test Execution Guide:**
- ML Training Workflow: ~11 minutes, validates MLflow integration
- ETL Workflow: ~10 minutes, validates Glue jobs
- Basic Pipeline: ~15 minutes, validates parameter passing

**GitHub PR Validation:**
- View PR status: `gh pr view <PR-NUMBER>`
- Monitor CI/CD: `gh run list`, `gh run watch`
- Download artifacts: `gh run download <RUN-ID>`
- 4-phase process: Analysis → Approval → Implementation → Monitoring

## 3. Architecture Overview

### 3.1 Core Components

**Commands** (`src/smus_cicd/commands/`)
- CLI entry points for deploy, bundle, describe, monitor, logs, run
- Orchestrate workflows using helpers and operations

**Helpers** (`src/smus_cicd/helpers/`)
- `datazone.py` - DataZone project/domain operations
- `quicksight.py` - QuickSight dashboard deployment and permissions
- `airflow_serverless.py` - Serverless Airflow workflow operations
- `mwaa.py` - Managed Airflow (MWAA) operations
- `s3.py` - S3 file operations and syncing
- `cloudformation.py` - CloudFormation stack management

**Bootstrap Actions** (`src/smus_cicd/bootstrap/`)
- Execute automated tasks during deployment
- Handlers: workflow operations, QuickSight refresh, EventBridge events
- See `docs/bootstrap-actions.md` for available actions

**Workflows** (`src/smus_cicd/workflows/`)
- Shared operations for workflow management
- Used by both CLI commands and bootstrap actions

### 3.2 Key Design Patterns

1. **Manifest-Driven**: All configuration in `manifest.yaml`
2. **Multi-Stage**: Support for dev/test/prod environments
3. **Idempotent**: Commands can be run multiple times safely
4. **Event-Driven**: EventBridge integration for CI/CD pipelines

## 4. Development Environment Setup

### 4.1 Domain Types and Testing

**IAM-Based Domains** (Simpler, Faster Setup)
- **No IAM Identity Center (IDC) required**
- Direct IAM role authentication
- **Setup steps**: 1 → 4 → 5 (skip steps 2-3)
- **Location**: `tests/scripts/setup/iam-based-domains/`
- **Use case**: Quick testing, development environments, CI/CD pipelines
- **Limitations**: No SSO integration, manual user management
- **Performance**: Faster setup (~15 minutes), faster test execution

**IDC-Based Domains** (Full Production Setup)
- **Requires IAM Identity Center enabled**
- SSO integration with user federation
- **Setup steps**: 1 → 2 → 3 → 4 → 5 (all steps)
- **Location**: `tests/scripts/setup/idc-based-domains/`
- **Use case**: Production-like testing, multi-user scenarios, SSO validation
- **Benefits**: Realistic user authentication, SSO workflows, proper user isolation
- **Performance**: Slower setup (~30 minutes), additional overhead

**Choosing Domain Type:**

| Scenario | Recommended Type | Reason |
|----------|-----------------|---------|
| Development/CI | IAM-based | Faster, simpler |
| Integration testing | IAM-based | Unless testing SSO features |
| Production validation | IDC-based | Matches production |
| Multi-user testing | IDC-based | Proper user isolation |
| Quick prototyping | IAM-based | Minimal setup time |
| SSO feature testing | IDC-based | Required for SSO |

### 4.2 Infrastructure Deployment

**Setup Steps:**

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
./deploy.sh us-east-2

# Deploy test data (ML datasets, COVID data)
cd ../testing-data
./deploy.sh us-east-2
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

### 4.3 Quick Start (IAM-Based)

```bash
cd tests/scripts/setup/iam-based-domains

# Step 1: Account base setup
cd 1-account-setup && ./deploy.sh && cd ..

# Step 4: Create projects
cd 4-project-setup && ./deploy.sh && cd ..

# Step 5: Deploy infrastructure and data
cd 5-testing-infrastructure/testing-infrastructure && ./deploy.sh us-east-2 && cd ..
cd testing-data && ./deploy.sh us-east-2
```

### 4.4 Environment Variables

After setup, export these for integration tests:
```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export TEST_DOMAIN_REGION=us-east-2
export DEV_DOMAIN_REGION=us-east-2
export AWS_DEFAULT_REGION=us-east-2
```

## 5. Testing Framework

### 5.1 Structure

```
tests/
├── unit/                    # Unit tests (fast, no AWS calls)
├── integration/             # Integration tests (real AWS resources)
│   ├── base.py             # Base test class with CLI helpers
│   ├── examples-analytics-workflows/  # Analytics workflow tests
│   └── PARALLEL_TESTING.md # Parallel execution guide
├── run_tests.py            # Test runner with parallel support
└── scripts/                # Setup and utility scripts
    ├── combine_coverage.py # Combine coverage from parallel runs
    └── README-coverage.md  # Coverage combining guide
```

### 5.2 Base Test Class

All integration tests inherit from `IntegrationTestBase` (`tests/integration/base.py`):

**Key Features:**
- CLI command execution with output capture
- Automatic log file generation per test
- AWS credential verification
- S3 sync helpers
- Workflow monitoring utilities

**Usage:**
```python
class TestMyFeature(IntegrationTestBase):
    def test_deployment(self):
        result = self.run_cli_command(["deploy", "test", "--manifest", "manifest.yaml"])
        assert result["success"]
```

### 5.3 Running Tests

**Using run_tests.py (Recommended):**
```bash
# All tests
python tests/run_tests.py --type all

# Unit tests only
python tests/run_tests.py --type unit

# Integration tests only
python tests/run_tests.py --type integration

# Parallel execution (auto-detect CPUs)
python tests/run_tests.py --type integration --parallel

# Parallel with specific workers
python tests/run_tests.py --type integration --parallel --workers 4

# Skip coverage for faster runs
python tests/run_tests.py --type integration --parallel --no-coverage

# Skip slow tests
python tests/run_tests.py --type integration --skip-slow
```

**Using pytest directly:**
```bash
# All integration tests
pytest tests/integration/ -v

# Specific test
pytest tests/integration/examples-analytics-workflows/dashboard-glue-quick/ -v -s

# Parallel execution
pytest tests/integration/ -n auto -v

# Skip slow tests
pytest tests/integration/ -m "not slow" -v
```

### 5.4 Domain-Specific Testing

**IAM Domains:**
- Faster test execution (no SSO overhead)
- Simpler cleanup (direct IAM role deletion)
- Recommended for CI/CD pipelines
- Use for most integration tests

**IDC Domains:**
- Test SSO flows and user authentication
- Validate user profile creation
- Test multi-user scenarios
- Required for SSO feature validation

**Test Isolation:**
- Each test uses unique project names (e.g., `test-dashboard-quick`, `test-ml-training`)
- Shared dev project: `dev-marketing` (read-only)
- Reserved: `test-marketing`, `prod-marketing` (long-standing projects)
- Never hardcode project names - use regex patterns

### 5.5 GitHub CI/CD Integration

**Automatic Test Discovery:**
The PR test workflow (`pr-tests.yml`) automatically discovers all integration tests:
- Scans `tests/integration/` for directories with `test_*.py` files
- Excludes `examples-analytics-workflows/` (separate workflows)
- Runs all discovered tests in parallel via matrix strategy

**Adding New Tests:**
Simply create a new test directory - no workflow changes needed:
```bash
tests/integration/
  └── my_new_feature/
      ├── manifest.yaml
      └── test_my_feature.py  # ✅ Auto-discovered in CI!
```

**Coverage Reports:**
Each test generates separate coverage files that are combined:
```bash
# Download from GitHub Actions
gh run download <RUN_ID> -n test-summary-combined

# Combine coverage locally
python tests/scripts/combine_coverage.py
open coverage-combined/htmlcov-combined/index.html
```

## 6. Development Workflow

### 6.1 Making Changes

**Code Style Requirements:**
- Follow PEP 8 style guide: https://peps.python.org/pep-0008/
- Imports at top of file (after docstrings, before code)
- Use proper whitespace around operators
- Avoid unused imports and variables
- Use regular strings instead of f-strings when no placeholders needed

**Pre-commit Hooks:**
- `black` - Code formatting
- `flake8` - Linting
- `isort` - Import sorting

**Always run linting checks after code changes:**
```bash
# Check code formatting and imports
flake8 src/smus_cicd/ --config=setup.cfg
black --check src/smus_cicd/
isort --check-only src/smus_cicd/

# Auto-fix formatting issues
black src/smus_cicd/
isort src/smus_cicd/
```

### 6.2 Testing Changes

**Workflow:**
1. Unit tests first (fast feedback)
2. Integration tests (IAM domain for speed)
3. Parallel execution for faster results

**CRITICAL: Integration Tests Are Slow (10-15 min)**
- Test fixes quickly first with small scripts (30s-1min)
- Only run full integration test after fix confirmed working

```bash
# Quick test examples:
# Notebook: python -c "import papermill as pm; pm.execute_notebook('nb.ipynb', '/tmp/out.ipynb', parameters={'p': 'v'})"
# Manifest: python -c "from smus_cicd.application.application_manifest import ApplicationManifest; m = ApplicationManifest.from_file('manifest.yaml'); print(m.initialization)"
# CLI: smus-cli describe --manifest manifest.yaml

# Run full integration test only after fix confirmed working
```

**Verifying Test Results:**
- NEVER re-run test to check if it passed
- ALWAYS check logs first: `tests/test-outputs/{test_name}.log`
- ALWAYS check notebooks: `tests/test-outputs/notebooks/` (underscore-prefixed = actual outputs)

```bash
# Check logs and notebooks
cat tests/test-outputs/TestMLWorkflow__test_ml_workflow_deployment.log
ls tests/test-outputs/notebooks/_*.ipynb
grep -i "error\|failed\|exception" tests/test-outputs/*.log
```

### 6.3 Documentation Updates

**User-facing docs in `docs/`:**
- `manifest.md` - Manifest schema reference
- `cli-commands.md` - CLI command reference
- `bootstrap-actions.md` - Bootstrap actions guide
- `quicksight-deployment.md` - QuickSight deployment guide

**Update AmazonQ.md:**
- Add new test patterns
- Document new workflows
- Update debugging procedures

## 7. Code Organization

### 7.1 Adding New Commands

1. Create command file in `src/smus_cicd/commands/`
2. Use Typer for CLI interface
3. Import helpers for AWS operations
4. Add tests in `tests/integration/`

**Example Structure:**
```python
@app.command()
def my_command(
    target: str = typer.Argument(..., help="Target stage"),
    manifest: Path = typer.Option(..., help="Manifest file"),
):
    """Command description."""
    # Load manifest
    manifest_obj = load_manifest(manifest)
    
    # Get target config
    target_config = manifest_obj.stages[target]
    
    # Execute operations
    result = helper.do_something(target_config)
    
    # Handle errors
    if not result["success"]:
        raise typer.Exit(1)
```

### 7.2 Adding New Bootstrap Actions

1. Create handler in `src/smus_cicd/bootstrap/handlers/`
2. Register in `src/smus_cicd/bootstrap/executor.py`
3. Document in `docs/bootstrap-actions.md`
4. Add tests

### 7.3 Adding New Helpers

1. Create helper in `src/smus_cicd/helpers/`
2. Keep functions focused and reusable
3. Add error handling and logging
4. Write unit tests in `tests/unit/helpers/`

**Example Structure:**
```python
def do_operation(param: str, region: str = None) -> Dict[str, Any]:
    """
    Perform operation.
    
    Args:
        param: Description
        region: AWS region (optional)
        
    Returns:
        Dict with success status and results
    """
    try:
        # AWS operation
        result = client.operation(param)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        return {"success": False, "error": str(e)}
```

## 8. Common Patterns

### 8.1 CLI Command Structure
```python
@app.command()
def my_command(
    target: str = typer.Argument(..., help="Target stage"),
    manifest: Path = typer.Option(..., help="Manifest file"),
):
    """Command description."""
    # Load manifest
    manifest_obj = load_manifest(manifest)
    
    # Get target config
    target_config = manifest_obj.stages[target]
    
    # Execute operations
    result = helper.do_something(target_config)
    
    # Handle errors
    if not result["success"]:
        raise typer.Exit(1)
```

### 8.2 Helper Function Structure
```python
def do_operation(param: str, region: str = None) -> Dict[str, Any]:
    """
    Perform operation.
    
    Args:
        param: Description
        region: AWS region (optional)
        
    Returns:
        Dict with success status and results
    """
    try:
        # AWS operation
        result = client.operation(param)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        return {"success": False, "error": str(e)}
```

### 8.3 Integration Test Structure
```python
class TestFeature(IntegrationTestBase):
    def test_feature_workflow(self):
        """Test complete workflow."""
        # Step 1: Setup
        self.logger.info("=== Step 1: Setup ===")
        
        # Step 2: Execute
        result = self.run_cli_command(["command", "args"])
        assert result["success"]
        
        # Step 3: Verify
        # Verify expected state
        
        # Cleanup in tearDown
```

## 9. GitHub Workflows

### 9.1 Core Workflows

**CI Workflow** (`ci.yml`)
- **Trigger**: Pull requests and pushes to main/master
- **Purpose**: Code quality validation
- **Jobs**:
  - Lint: flake8, black, isort checks
  - Security: safety, bandit vulnerability scans
  - Validate docs: manifest and backlink validation
- **Use case**: Pre-merge validation

**PR Integration Tests** (`pr-tests.yml`)
- **Trigger**: Pull requests, workflow_dispatch
- **Purpose**: Automated integration testing with AWS
- **Jobs**:
  - Unit tests with coverage
  - Auto-discover integration tests (excludes analytics)
  - Run tests in parallel matrix
  - Combine coverage reports
- **Features**: 
  - Automatic test discovery (no workflow updates needed)
  - Parallel execution per test directory
  - Combined coverage artifacts
- **Use case**: Validate changes against real AWS resources

**Test AWS Credentials** (`test-aws-credentials.yml`)
- **Trigger**: Manual (workflow_dispatch)
- **Purpose**: Verify AWS OIDC authentication
- **Jobs**: Test dev, test, and prod account credentials
- **Use case**: Troubleshoot authentication issues

### 9.2 Reusable Deployment Workflows

**SMUS Direct Deploy** (`smus-direct-deploy.yml`)
- **Type**: Reusable workflow (workflow_call)
- **Purpose**: Deploy directly from branch (no bundle)
- **Flow**: Deploy test → Run tests
- **Parameters**: manifest_path, test_target, skip_tests
- **Use case**: Quick testing, development iterations

**SMUS Bundle and Deploy** (`smus-bundle-deploy.yml`)
- **Type**: Reusable workflow (workflow_call)
- **Purpose**: Full CI/CD with bundling
- **Flow**: Bundle (dev) → Validate → Deploy test → Test → Deploy prod
- **Parameters**: manifest_path, test_target, prod_target, deploy_to_prod
- **Features**: 
  - Artifact isolation per run (temp directory pattern)
  - Multi-environment deployment
  - Notebook output download
- **Use case**: Production deployments

**SMUS Multi-Environment Deploy** (`smus-multi-env-reusable.yml`)
- **Type**: Reusable workflow (workflow_call)
- **Purpose**: Flexible multi-stage deployment
- **Flow**: Bundle → Validate all → Deploy test → Test → Deploy prod
- **Parameters**: skip_bundle, skip_tests, deploy_to_prod
- **Features**: Optional bundling, validate all targets
- **Use case**: Complex deployment scenarios

### 9.3 Analytics Application Workflows

**Deploy GenAI** (`analytic-genai.yml`)
- **Trigger**: Push to specific branches, path changes, workflow_dispatch
- **Uses**: smus-direct-deploy.yml
- **Manifest**: `examples/analytic-workflow/genai/manifest.yaml`
- **Deploys to prod**: Only on main branch

**Deploy ML Training** (`analytic-ml-training.yml`)
- **Trigger**: Push to specific branches, path changes, workflow_dispatch
- **Uses**: smus-direct-deploy.yml
- **Manifest**: `examples/analytic-workflow/ml/training/manifest.yaml`
- **Deploys to**: Test only

**Deploy Data Notebooks** (`analytic-data-notebooks.yml`)
- **Trigger**: Push to specific branches, path changes, workflow_dispatch
- **Uses**: smus-direct-deploy.yml
- **Manifest**: `examples/analytic-workflow/data-notebooks/manifest.yaml`

**Deploy Dashboard Glue QuickSight** (`analytic-dashboard-glue-quicksight.yml`)
- **Trigger**: Push to specific branches, path changes, workflow_dispatch
- **Uses**: smus-direct-deploy.yml
- **Manifest**: `examples/analytic-workflow/dashboard-glue-quick/manifest.yaml`

**Deploy ML Deployment** (`analytic-ml-deployment.yml`)
- **Trigger**: Push to specific branches, path changes, workflow_dispatch
- **Uses**: smus-direct-deploy.yml
- **Manifest**: `examples/analytic-workflow/ml/deployment/manifest.yaml`

### 9.4 Lifecycle Demo Workflows

**Serverless Pipeline Lifecycle** (`serverless-pipeline-lifecycle.yml`)
- **Trigger**: Manual (workflow_dispatch)
- **Purpose**: End-to-end serverless Airflow demo
- **Steps**:
  1. Setup: Resolve domain/project IDs
  2. Validate: Check pipeline configuration
  3. Upload: Sync DAG files to S3
  4. Bundle: Create deployment bundle
  5. Deploy test: Deploy to test environment
  6. Deploy prod: Deploy to production
  7. Monitor: Check pipeline status
- **Inputs**: domain_name, project_name
- **Use case**: Demo complete serverless workflow

**MWAA Pipeline Lifecycle** (`mwaa-pipeline-lifecycle.yml`)
- **Trigger**: Manual (workflow_dispatch)
- **Purpose**: End-to-end MWAA (Managed Airflow) demo
- **Similar flow**: Setup → Validate → Bundle → Deploy → Monitor
- **Use case**: Demo MWAA-based workflow

### 9.5 Publishing Workflows

**Publish to PyPI** (`publish-pypi.yml`)
- **Trigger**: Release creation
- **Purpose**: Publish package to PyPI
- **Use case**: Package distribution

**Release** (`release.yml`)
- **Trigger**: Tag push (v*)
- **Purpose**: Create GitHub release
- **Use case**: Version management

### 9.6 Workflow Selection Guide

**For Development:**
- Use: `smus-direct-deploy.yml`
- Why: Fast, no bundling overhead

**For Testing:**
- Use: `pr-tests.yml` (automatic)
- Why: Validates all changes with parallel execution

**For Production:**
- Use: `smus-bundle-deploy.yml`
- Why: Full validation, artifact management, multi-stage

**For Demos:**
- Use: `serverless-pipeline-lifecycle.yml` or `mwaa-pipeline-lifecycle.yml`
- Why: Complete end-to-end showcase

**For Troubleshooting:**
- Use: `test-aws-credentials.yml`
- Why: Verify authentication setup

### 9.7 Setting Up GitHub Integration

#### Deploy GitHub OIDC Integration

```bash
cd tests/scripts
./deploy-github-integration.sh [config-file]
```

This creates:
- OIDC identity provider for GitHub Actions
- IAM role that GitHub Actions can assume
- Role restricted to your repository and main branch

#### Configure GitHub Repository Secrets

After deployment, add the following secret to your GitHub repository:

1. Go to your repository settings
2. Navigate to "Secrets and variables" → "Actions"  
3. Add a new repository secret:
   - Name: `AWS_ROLE_ARN`
   - Value: The role ARN output from the CloudFormation deployment

#### GitHub Environment Setup

For workflows using the `aws-env` environment:

1. Go to repository Settings → Environments
2. Create environment named `aws-env`
3. Add environment secrets:
   - `AWS_ROLE_ARN`: The IAM role ARN
4. Configure protection rules as needed

## 10. Debugging

### 10.1 Enable Debug Logging
```bash
export SMUS_DEBUG=1
python -m smus_cicd.cli deploy test --manifest manifest.yaml
```

### 10.2 Check Integration Test Logs
```bash
# Latest test log
ls -lt tests/test-outputs/*.log | head -1

# View specific test log
cat tests/test-outputs/TestMyFeature__test_method.log

# Search for errors
grep -i "error\|failed\|exception" tests/test-outputs/*.log
```

### 10.3 Check Notebooks (ALWAYS CHECK HERE FIRST)
```bash
# Check local (underscore-prefixed = actual outputs)
ls tests/test-outputs/notebooks/_*.ipynb
grep '"output_type": "error"' tests/test-outputs/notebooks/_*.ipynb

# If not local, download from S3
aws s3 ls s3://amazon-sagemaker-ACCOUNT-REGION-ID/shared/workflows/output/ --recursive | grep output.tar.gz
```

### 10.4 Common Issues

**Import Errors:**
- Ensure package installed: `pip install -e .`
- Check Python path includes src directory

**AWS Credential Errors:**
- Verify AWS_PROFILE or credentials configured
- Check IAM permissions for DataZone, S3, CloudFormation
- Run: `isenguardcli` and `aws sts get-caller-identity`

**Test Failures:**
- Check test-outputs logs for detailed error messages
- Verify AWS resources exist (projects, domains)
- Ensure cleanup ran from previous test runs

**Domain-Specific Issues:**
- IAM domains: Check IAM role permissions
- IDC domains: Verify IDC is enabled, check user profiles

## 11. Building and Deployment

### 11.1 Building

```bash
# Build the package
python setup.py build

# Create distribution packages
python setup.py sdist bdist_wheel
```

### 11.2 Local Installation
```bash
pip install .
```

### 11.3 PyPI Distribution
```bash
# Build the package
python setup.py sdist bdist_wheel

# Upload to PyPI
twine upload dist/*
```

## 12. Cleanup

### 12.1 Remove GitHub Integration
```bash
aws cloudformation delete-stack --stack-name smus-cli-github-integration
```

### 12.2 Remove Infrastructure (IAM-Based)
```bash
cd tests/scripts/setup/iam-based-domains

# Delete in reverse order
aws cloudformation delete-stack --stack-name datazone-project-dev
aws cloudformation delete-stack --stack-name sagemaker-unified-studio-vpc
```

### 12.3 Remove Infrastructure (IDC-Based)
```bash
cd tests/scripts/setup/idc-based-domains

# Delete in reverse order
aws cloudformation delete-stack --stack-name datazone-project-dev
aws cloudformation delete-stack --stack-name sagemaker-blueprints-profiles-stack  
aws cloudformation delete-stack --stack-name cicd-test-domain-stack
aws cloudformation delete-stack --stack-name sagemaker-unified-studio-vpc
# Repeat for additional regions
```

## 13. Resources

- **User Documentation**: `docs/` directory
- **Examples**: `examples/` directory
- **Test Setup**: `tests/scripts/setup/` directory
- **Main README**: `README.md`
- **AmazonQ.md**: AI assistant context (`developer/AmazonQ.md`)
- **GitHub Workflows**: `.github/workflows/` directory

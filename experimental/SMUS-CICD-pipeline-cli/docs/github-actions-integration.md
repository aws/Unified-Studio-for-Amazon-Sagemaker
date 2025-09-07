# GitHub Actions CI/CD Integration

The SMUS CLI includes comprehensive GitHub Actions integration with three pre-built workflows for automated testing, validation, and demonstration.

## Available Workflows

### 1. CI Workflow (`.github/workflows/ci.yml`)

**Purpose**: Comprehensive code quality and testing validation

**Triggers**: 
- Pull requests to main/master branches
- Pushes to main/master branches
- Path filter: `experimental/SMUS-CICD-pipeline-cli/**`

**Jobs**:
- **Linting**: flake8 syntax checks, black formatting, isort import sorting
- **Unit Tests**: 147 unit tests with coverage reporting and Codecov integration
- **Security**: safety vulnerability scanning and bandit security analysis

**Features**:
- Runs in parallel with dependency management
- Uploads test results and coverage reports as artifacts
- Integrates with Codecov for coverage tracking

### 2. PR Integration Tests (`.github/workflows/pr-tests.yml`)

**Purpose**: Integration testing against real AWS resources

**Triggers**: 
- Pull requests to main/master branches
- Path filter: `experimental/SMUS-CICD-pipeline-cli/**`

**Authentication**: 
- Uses AWS OIDC with GitHub environment `aws-env`
- Assumes IAM role from `smus-cli-github-integration` CloudFormation stack

**Jobs**:
- **Integration Tests**: Full integration test suite with AWS credentials
- **Artifact Upload**: Test results and reports for debugging

**Setup Requirements**:
1. Deploy the GitHub OIDC integration stack (see [tests/integration/github/README.md](../tests/integration/github/README.md))
2. Configure `AWS_ROLE_ARN` secret in GitHub environment `aws-env`

### 3. Full Pipeline Lifecycle Demo (`.github/workflows/full-pipeline-lifecycle.yml`)

**Purpose**: End-to-end demonstration of SMUS CLI capabilities

**Triggers**: 
- Manual workflow dispatch only
- Customizable inputs for domain, project, and pipeline names

**Jobs** (Sequential execution):
1. **Setup**: Resolve domain and project IDs from names
2. **Create Manifest**: Generate pipeline YAML configuration  
3. **Validate Configuration**: Check pipeline setup with workflows/connections
4. **Create Bundle**: Package deployment artifacts for dev target
5. **Deploy Test**: Deploy pipeline to test environment
6. **Run Tests**: Execute test suite on test target
7. **Monitor Pipeline**: Check pipeline status and health
8. **Execute Workflows**: Run Airflow commands (trigger DAG, list tasks, check state)
9. **Cleanup**: Remove test resources (runs even if previous jobs fail)

**Features**:
- Artifact sharing for pipeline manifest between jobs
- Proper error handling and cleanup
- Customizable inputs with sensible defaults
- Follows the exact sequence from `examples/full-pipeline-lifecycle.sh`

## Setup Instructions

### 1. AWS OIDC Integration

Deploy the GitHub OIDC integration to enable AWS authentication:

```bash
cd tests/integration/github
./deploy-github-integration.sh
```

This creates:
- OIDC identity provider for GitHub Actions
- IAM role with appropriate permissions
- CloudFormation stack `smus-cli-github-integration`

### 2. GitHub Environment Configuration

1. Go to repository Settings → Environments
2. Create environment named `aws-env`
3. Add secret `AWS_ROLE_ARN` with the role ARN from CloudFormation output

### 3. Running Workflows

**CI Workflow**: Runs automatically on PRs and pushes

**PR Integration Tests**: Runs automatically on PRs affecting SMUS CLI code

**Full Pipeline Lifecycle Demo**: 
1. Go to Actions tab in GitHub
2. Select "Full Pipeline Lifecycle Demo"
3. Click "Run workflow"
4. Enter custom domain/project/pipeline names or use defaults
5. Click "Run workflow" to start

## Example Custom GitHub Actions Workflow

For your own projects, create `.github/workflows/smus-cicd.yml`:

```yaml
name: SMUS CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

env:
  AWS_REGION: us-east-1
  PIPELINE_FILE: pipeline.yaml

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install SMUS CLI
      run: |
        pip install smus-cicd-cli
    
    - name: Configure AWS Credentials
      uses: aws-actions/configure-aws-credentials@v4
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: ${{ env.AWS_REGION }}
    
    - name: Validate Pipeline Configuration
      run: |
        smus-cli describe --pipeline ${{ env.PIPELINE_FILE }} --connect

  bundle-from-dev:
    needs: validate
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop'
    steps:
    - uses: actions/checkout@v4
    
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install SMUS CLI
      run: pip install smus-cicd-cli
    
    - name: Configure AWS Credentials
      uses: aws-actions/configure-aws-credentials@v4
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: ${{ env.AWS_REGION }}
    
    - name: Describe Development Environment
      run: |
        smus-cli describe --pipeline ${{ env.PIPELINE_FILE }} --targets marketing-dev-stage --connect
    
    - name: Create Bundle from Development
      run: |
        smus-cli bundle --pipeline ${{ env.PIPELINE_FILE }} --targets marketing-dev-stage
    
    - name: Upload Bundle Artifacts
      uses: actions/upload-artifact@v4
      with:
        name: smus-bundle
        path: ./bundles/

  deploy-staging:
    needs: bundle-from-dev
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop'
    steps:
    - uses: actions/checkout@v4
    
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install SMUS CLI
      run: pip install smus-cicd-cli
    
    - name: Configure AWS Credentials
      uses: aws-actions/configure-aws-credentials@v4
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: ${{ env.AWS_REGION }}
    
    - name: Download Bundle Artifacts
      uses: actions/download-artifact@v4
      with:
        name: smus-bundle
        path: ./bundles/
    
    - name: Deploy to Staging
      run: |
        smus-cli deploy --pipeline ${{ env.PIPELINE_FILE }} --targets marketing-test-stage
    
    - name: Run Staging Tests
      run: |
        smus-cli test --pipeline ${{ env.PIPELINE_FILE }} --targets marketing-test-stage
    
    - name: Monitor Workflow Status
      run: |
        smus-cli monitor --pipeline ${{ env.PIPELINE_FILE }} --targets marketing-test-stage

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment: production
    steps:
    - uses: actions/checkout@v4
    
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install SMUS CLI
      run: pip install smus-cicd-cli
    
    - name: Configure AWS Credentials
      uses: aws-actions/configure-aws-credentials@v4
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: ${{ env.AWS_REGION }}
    
    - name: Create Bundle from Development
      run: |
        smus-cli bundle --pipeline ${{ env.PIPELINE_FILE }} --targets marketing-dev-stage
    
    - name: Deploy to Production
      run: |
        smus-cli deploy --pipeline ${{ env.PIPELINE_FILE }} --targets marketing-prod-stage
    
    - name: Run Production Tests
      run: |
        smus-cli test --pipeline ${{ env.PIPELINE_FILE }} --targets marketing-prod-stage
    
    - name: Monitor Production Deployment
      run: |
        smus-cli monitor --pipeline ${{ env.PIPELINE_FILE }} --targets marketing-prod-stage
```

## Workflow Explanation

This GitHub Actions workflow implements a complete CI/CD pipeline for SMUS deployments:

### **Triggers**
- **Push to `develop`**: Deploys to development and staging environments
- **Push to `main`**: Deploys to production (after staging validation)
- **Pull Requests**: Validates pipeline configuration only

### **Pipeline Stages**

1. **Validate** (All branches)
   - Validates pipeline configuration
   - Connects to AWS to verify resources and permissions
   - Runs on every push and PR

2. **Bundle from Development** (develop branch only)
   - Describes the existing development environment
   - Creates bundle from `marketing-dev-stage` (where development work is done)
   - Uploads bundle as GitHub Actions artifact for reuse
   - No deployment - dev environment already exists with latest work

3. **Deploy Staging** (develop branch only)
   - Downloads bundle created from development
   - Deploys to `marketing-test-stage` target
   - Runs comprehensive tests
   - Monitors workflow execution
   - Pre-production validation

4. **Deploy Production** (main branch only)
   - Creates fresh bundle from development environment
   - Uses GitHub Environment protection rules
   - Deploys to `marketing-prod-stage` target
   - Runs production tests
   - Monitors deployment status

### **Required GitHub Secrets**

Configure these secrets in your GitHub repository settings:

- `AWS_ACCESS_KEY_ID`: AWS access key for SMUS CLI
- `AWS_SECRET_ACCESS_KEY`: AWS secret key for SMUS CLI

### **Environment Protection**

The production job uses GitHub's `environment: production` feature, which allows you to:
- Require manual approval before production deployments
- Restrict deployments to specific branches
- Add deployment protection rules

### **Benefits**

- **Automated Testing**: Every deployment is automatically tested
- **Environment Progression**: Code flows through dev (source) → staging → production
- **Bundle Reuse**: Staging uses the same bundle created from dev environment
- **Development Isolation**: Dev environment is the source, not a deployment target
- **Rollback Safety**: Failed tests prevent promotion to next environment
- **Audit Trail**: Complete deployment history in GitHub Actions
- **Team Collaboration**: Pull request validation ensures code quality

This integration transforms your SMUS pipeline into a fully automated CI/CD system that scales with your team's development workflow.

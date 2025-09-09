# SMUS-CICD-pipeline-cli Development Guide

This is a Python 3 project for SageMaker Unified Studio CI/CD pipeline management.

## Development Setup

### Prerequisites
- Python 3.7 or higher
- pip package manager
- AWS CLI configured with appropriate credentials
- yq (YAML processor) - `brew install yq` (macOS) or `apt-get install yq` (Ubuntu)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd experimental/SMUS-CICD-pipeline-cli

# Install in development mode
pip install -e ".[dev]"
```

## Building and Testing

### Building

The project uses standard Python setuptools for building and packaging.

```bash
# Build the package
python setup.py build

# Create distribution packages
python setup.py sdist bdist_wheel
```

### Unit Testing

Run tests using pytest:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/smus_cicd --cov-report=html

# Run specific test patterns
pytest -k "test_pattern"

# Run with debugging
pytest --pdb
```

## Infrastructure Deployment Scripts

Before running integration tests or setting up GitHub workflows, you need to deploy the required AWS infrastructure. The deployment scripts are located in `tests/scripts/` and must be run in the correct order.

### Script Progression

The deployment follows this sequence:

1. **GitHub OIDC Integration** (`deploy-github-integration.sh`)
   - Creates IAM role and OIDC provider for GitHub Actions
   - Deployed to the domain region specified in config

2. **VPC Infrastructure** (`deploy-vpc.sh`)
   - Deploys VPCs in all enabled regions (primary + additional regions)
   - Creates subnets, security groups, and networking components
   - Supports multi-region deployment

3. **DataZone Domain** (`deploy-domain.sh`)
   - Creates DataZone domain with required IAM roles
   - Deployed to the primary region
   - Requires AWS Identity Center (IDC) to be enabled

4. **Environment Blueprints** (`deploy-blueprints-profiles.sh`)
   - Configures DataZone environment blueprints across all regions
   - Creates project profiles and S3 bucket for artifacts
   - Enables multi-region blueprint support

5. **Dev Project** (`deploy-projects.sh`)
   - Creates the dev-marketing project
   - Finds IDC user and creates DataZone user profile if needed
   - Adds user as PROJECT_OWNER via AWS CLI

6. **Project Memberships** (`deploy-memberships.sh`)
   - Additional membership configurations (if needed)

### Configuration

All scripts use a YAML configuration file. Default is `config.yaml`, but you can override:

```bash
# Use custom config
./deploy-all.sh config-6778.yaml
```

Example configuration structure:
```yaml
# AWS Configuration
region: us-east-2
region2: us-west-2
region3: us-east-1

# DataZone Domain Name
domain_name: cicd-test-domain

# Stack Names
stacks:
  domain: cicd-test-domain-stack
  blueprints_profiles: sagemaker-blueprints-profiles-stack

# Project Configuration
projects:
  dev:
    name: dev-marketing
    description: Development environment for marketing team

# User Configuration
users:
  admin_username: eng1

# VPC Configuration
VPC:
  Name: 'SageMakerUnifiedStudioVPC'
```

### Complete Deployment

```bash
cd tests/scripts
./deploy-all.sh [config-file]
```

## Integration Testing

### Local Integration Tests

Before running integration tests, ensure the infrastructure is deployed:

#### 1. Deploy Infrastructure
```bash
cd tests/scripts
./deploy-all.sh config-6778.yaml
```

#### 2. Configure Integration Tests
Create or update `tests/integration/config.local.yaml`:

```yaml
aws:
  profile: default
  region: us-east-2  # Match your domain region

test_environment:
  domain_name: cicd-test-domain
  project_prefix: integration-test
  cleanup_after_tests: true

test_scenarios:
  basic_pipeline:
    enabled: true
    description: "Basic pipeline with single target"
    pipeline_file: "basic_pipeline.yaml"
  
  multi_target_pipeline:
    enabled: true
    description: "Pipeline with multiple targets (dev, test, prod)"
    pipeline_file: "multi_target_pipeline.yaml"

timeouts:
  project_creation: 300
  environment_creation: 600
  bundle_creation: 120
  deployment: 180
```

#### 3. Update Pipeline Configurations
Ensure pipeline files use the correct region:

```bash
# Update basic_pipeline.yaml
sed -i 's/region: us-east-1/region: us-east-2/g' tests/integration/basic_pipeline/basic_pipeline.yaml

# Update multi_target_pipeline.yaml  
sed -i 's/region: us-east-1/region: us-east-2/g' tests/integration/multi_target_pipeline/multi_target_pipeline.yaml
```

#### 4. Run Integration Tests
```bash
# Run with verbose output
python run_tests_verbose.py

# Or run specific tests
pytest tests/integration/ -v
```

### GitHub Workflow Integration

The repository includes several GitHub Actions workflows for automated testing and deployment.

#### Available Workflows

1. **CI Workflow** (`.github/workflows/ci.yml`)
   - **Trigger**: Pull requests and pushes to main/master
   - **Jobs**: Linting (flake8, black, isort), unit tests with coverage, security scans
   - **Purpose**: Comprehensive code quality and testing validation

2. **PR Integration Tests** (`.github/workflows/pr-tests.yml`)
   - **Trigger**: Pull requests to main/master (paths: `experimental/SMUS-CICD-pipeline-cli/**`)
   - **Jobs**: Integration tests with AWS credentials
   - **Purpose**: Test SMUS CLI functionality against real AWS resources
   - **Environment**: Uses `aws-env` GitHub environment for AWS credentials

3. **Full Pipeline Lifecycle Demo** (`.github/workflows/full-pipeline-lifecycle.yml`)
   - **Trigger**: Manual workflow dispatch
   - **Jobs**: 8-step pipeline demonstration following `examples/full-pipeline-lifecycle.sh`
   - **Purpose**: End-to-end demonstration of SMUS CLI capabilities
   - **Features**: 
     - Customizable domain, project, and pipeline names
     - Sequential jobs: setup, create manifest, validate, bundle, deploy, test, monitor, execute workflows, cleanup
     - Artifact sharing between jobs
     - Proper error handling and cleanup

#### Setting Up GitHub Integration

##### 1. Deploy GitHub OIDC Integration

```bash
cd tests/scripts
./deploy-github-integration.sh [config-file]
```

This creates:
- OIDC identity provider for GitHub Actions
- IAM role that GitHub Actions can assume
- Role restricted to your repository and main branch

##### 2. Configure GitHub Repository Secrets

After deployment, add the following secret to your GitHub repository:

1. Go to your repository settings
2. Navigate to "Secrets and variables" → "Actions"  
3. Add a new repository secret:
   - Name: `AWS_ROLE_ARN`
   - Value: The role ARN output from the CloudFormation deployment

##### 3. Customize Parameters (Optional)

You can customize the deployment by setting environment variables:

```bash
export GITHUB_ORG="your-org"
export GITHUB_REPO="your-repo"
export AWS_REGION="us-west-2"
./deploy-github-integration.sh
```

##### 4. GitHub Environment Setup

For workflows using the `aws-env` environment:

1. Go to repository Settings → Environments
2. Create environment named `aws-env`
3. Add environment secrets:
   - `AWS_ROLE_ARN`: The IAM role ARN from step 2
4. Configure protection rules as needed

#### Workflow Execution

The GitHub workflows will:
1. Assume the IAM role using OIDC (no long-lived credentials needed)
2. Install the CLI and dependencies
3. Run integration tests against your deployed infrastructure
4. Execute full pipeline lifecycle demonstrations
5. Provide detailed logs and artifacts

## Running the CLI

### Command Line Interface

```bash
# Run the CLI directly
smus-cli --help

# Or using Python module
python -m smus_cicd.cli --help
```

### Development Mode

```bash
# Install in development mode for live code changes
pip install -e .

# Run from source
python src/smus_cicd/cli.py --help
```

## Security Considerations

- The IAM role is configured to only allow access from the `main` branch
- The role has PowerUser access but you may want to restrict permissions further based on your needs
- The OIDC provider uses GitHub's official thumbprint
- Integration tests create and clean up temporary resources

## Cleanup

### Remove GitHub Integration
```bash
aws cloudformation delete-stack --stack-name smus-cli-github-integration
```

### Remove All Infrastructure
```bash
cd tests/scripts
# Delete stacks in reverse order
aws cloudformation delete-stack --stack-name datazone-project-dev
aws cloudformation delete-stack --stack-name sagemaker-blueprints-profiles-stack  
aws cloudformation delete-stack --stack-name cicd-test-domain-stack
aws cloudformation delete-stack --stack-name sagemaker-unified-studio-vpc
# Repeat for additional regions
```

## Deploying

For distribution:

1. Build the package: `python setup.py sdist bdist_wheel`
2. Upload to PyPI: `twine upload dist/*`

For local installation:
```bash
pip install .
```

## Troubleshooting

### Common Issues

1. **IDC not enabled**: Ensure AWS Identity Center is enabled in your account
2. **Region not supported**: Some regions don't support DataZone - use supported regions like us-east-1, us-east-2, us-west-2
3. **VPC not found**: Ensure VPC deployment completed successfully before running domain deployment
4. **User not found**: Verify the admin_username exists in IDC and matches the configuration

### Debug Mode

Run scripts with debug output:
```bash
set -x  # Enable debug mode
./deploy-all.sh config-6778.yaml
```

### Log Files

Integration test results are saved to:
- `tests/reports/test-results.html` - HTML test report
- Console output with detailed progress information

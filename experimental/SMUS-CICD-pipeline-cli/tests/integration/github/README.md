# GitHub Actions Integration Testing Setup

This directory contains the necessary files to set up GitHub Actions integration testing for the SMUS CLI.

## Files

- `github-oidc-role.yaml` - CloudFormation template that creates the IAM role and OIDC provider
- `deploy-github-integration.sh` - Script to deploy the CloudFormation stack
- `README.md` - This file

## GitHub Workflows

The repository includes several GitHub Actions workflows:

### 1. CI Workflow (`.github/workflows/ci.yml`)
- **Trigger**: Pull requests and pushes to main/master
- **Jobs**: Linting (flake8, black, isort), unit tests with coverage, security scans
- **Purpose**: Comprehensive code quality and testing validation

### 2. PR Integration Tests (`.github/workflows/pr-tests.yml`)
- **Trigger**: Pull requests to main/master (paths: `experimental/SMUS-CICD-pipeline-cli/**`)
- **Jobs**: Integration tests with AWS credentials
- **Purpose**: Test SMUS CLI functionality against real AWS resources
- **Environment**: Uses `aws-env` GitHub environment for AWS credentials

### 3. Full Pipeline Lifecycle Demo (`.github/workflows/full-pipeline-lifecycle.yml`)
- **Trigger**: Manual workflow dispatch
- **Jobs**: 8-step pipeline demonstration following `examples/full-pipeline-lifecycle.sh`
- **Purpose**: End-to-end demonstration of SMUS CLI capabilities
- **Features**: 
  - Customizable domain, project, and pipeline names
  - Sequential jobs: setup, create manifest, validate, bundle, deploy, test, monitor, execute workflows, cleanup
  - Artifact sharing between jobs
  - Proper error handling and cleanup

## Setup Instructions

### 1. Deploy the CloudFormation Stack

Run the deployment script to create the necessary AWS resources:

```bash
cd tests/integration/github
./deploy-github-integration.sh
```

The script will:
- Create an OIDC identity provider for GitHub Actions
- Create an IAM role that GitHub Actions can assume
- Only allow access from the `main` branch of your repository

### 2. Configure GitHub Repository Secrets

After deployment, add the following secret to your GitHub repository:

1. Go to your repository settings
2. Navigate to "Secrets and variables" → "Actions"
3. Add a new repository secret:
   - Name: `AWS_ROLE_ARN`
   - Value: The role ARN output from the CloudFormation deployment

### 3. Customize Parameters (Optional)

You can customize the deployment by setting environment variables:

```bash
export GITHUB_ORG="your-org"
export GITHUB_REPO="your-repo"
export AWS_REGION="us-west-2"
./deploy-github-integration.sh
```

## Security Considerations

- The IAM role is configured to only allow access from the `main` branch
- The role has PowerUser access but you may want to restrict permissions further based on your needs
- The OIDC provider uses GitHub's official thumbprint

## Cleanup

To remove the resources:

```bash
aws cloudformation delete-stack --stack-name smus-cli-github-integration
```

## Workflow

The GitHub workflow (`.github/workflows/integration-tests.yml`) will:
1. Run on pushes to main and pull requests
2. Assume the IAM role using OIDC
3. Install the CLI and dependencies
4. Run the CREATE command as a basic integration test
5. Run unit and integration test suites

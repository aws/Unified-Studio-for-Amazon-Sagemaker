# Development Guide

This guide covers development workflows, testing, and contribution guidelines for the SMUS CI/CD CLI.

## Development Workflow

### Local Development
1. **Update code** in dev environment S3 location
2. **Create bundle**: `smus-cli bundle` (downloads latest from dev)
3. **Deploy to test**: `smus-cli deploy --targets test` (deploys and triggers workflows)
4. **Verify execution**: Check workflow runs in SageMaker Unified Studio console
5. **Deploy to prod**: `smus-cli deploy --targets prod` (when ready)

### GitHub Actions Integration
The repository includes automated workflows for development:

## Development Workflows

### Automated Testing Workflows

**CI Workflow (`.github/workflows/ci.yml`)**:
- **Triggers**: Pull requests and pushes to main/master
- **Features**: Code linting (flake8, black, isort), unit tests with coverage, security scans (safety, bandit)
- **Purpose**: Comprehensive code quality validation
- **Coverage**: 158 unit tests with Codecov integration

**PR Integration Tests (`.github/workflows/pr-tests.yml`)**:
- **Triggers**: Pull requests affecting SMUS CLI code
- **Features**: Integration tests with real AWS resources using OIDC authentication
- **Purpose**: Validate CLI functionality against live AWS services
- **Duration**: Extended 12-hour sessions for long-running MWAA operations

**Full Pipeline Lifecycle Demo (`.github/workflows/full-pipeline-lifecycle.yml`)**:
- **Triggers**: Manual workflow dispatch
- **Features**: Complete 7-step pipeline demonstration with customizable inputs
- **Purpose**: End-to-end showcase of SMUS CLI capabilities
- **Note**: Cleanup step is commented out to prevent resource conflicts

### Development Setup Requirements

1. **Deploy AWS OIDC Integration**:
   ```bash
   cd tests/scripts
   aws cloudformation deploy \
     --template-file github-oidc-role.yaml \
     --stack-name smus-cli-github-integration \
     --capabilities CAPABILITY_NAMED_IAM
   ```

2. **Configure GitHub Secrets**:
   - Create environment `aws-env` in repository settings
   - Add secret `AWS_ROLE_ARN_DEV` with the OIDC role ARN
   - Role has 12-hour maximum session duration for long operations

3. **Local Development Setup**:
   ```bash
   cd experimental/SMUS-CICD-pipeline-cli
   pip install -e ".[dev]"
   ```

### Environment Variable Configuration

The CLI supports environment variable parameterization in bundle manifests for flexible multi-environment development:

**Local Development**:
```bash
# Set local environment variables
export DEV_DOMAIN_REGION=us-east-1
export PROJECT_PREFIX=myteam
export DOMAIN_NAME=local-test-domain

# Run tests with local configuration
python -m pytest tests/integration/
```

**GitHub Actions**:
```bash
# Automatically set in CI environment
export DEV_DOMAIN_REGION=us-east-2
export AWS_ROLE_ARN_DEV=arn:aws:iam::ACCOUNT:role/GitHubActionsRole-SMUS-CLI-Tests
```

**Integration Test Manifests**:
All integration test bundle manifests use environment variables:
```yaml
domain:
  name: cicd-test-domain
  region: ${DEV_DOMAIN_REGION:us-east-2}  # Defaults to us-east-2 for CI
```

This allows the same test manifests to work in both local development (us-east-1) and CI environments (us-east-2) without modification.

See [GitHub Actions Integration](github-actions-integration.md) for complete setup instructions.

## Testing

The project includes comprehensive unit and integration tests with coverage analysis.

### Test Prerequisites

Before running tests, you must set up the required AWS infrastructure and users:

#### 1. Deploy AWS Resources
Run the deployment scripts in the following order:

```bash
cd tests/scripts/

# Deploy all resources in correct order
./deploy-all.sh
```

The `deploy-all.sh` script executes the following in sequence:
1. `deploy-domain.sh` - Creates the SageMaker Unified Studio domain
2. `deploy-blueprints-profiles.sh` - Sets up environment blueprints and profiles
3. `deploy-projects.sh` - Creates the dev project
4. `deploy-memberships.sh` - Configures project memberships

#### 2. Create Required IDC User
Create an Identity Center (IDC) user named **Eng1** that the tests depend on:
- This user must exist in your AWS Identity Center instance
- The user should have appropriate permissions to access the created domain and projects

### Running Tests

```bash
# Run all tests
python scripts/validate.py --all

# Run only unit tests
python scripts/validate.py --unit

# Run only integration tests  
python scripts/validate.py --integration

# Run with coverage
pytest tests/unit/ --cov=src/smus_cicd --cov-report=html
```

### Test Structure

- **Unit Tests** (`tests/unit/`): 147 tests covering CLI commands, helpers, and pipeline logic
- **Integration Tests** (`tests/integration/`): End-to-end tests against real AWS resources
- **Coverage**: Maintained at >35% with focus on critical paths

## Code Quality

### Pre-commit Checks
The project uses automated code quality checks:

```bash
# Format code
black src/smus_cicd/
isort src/smus_cicd/

# Lint code
flake8 src/smus_cicd/ --config=setup.cfg

# Security scan
bandit -r src/
safety check
```

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd experimental/SMUS-CICD-pipeline-cli

# Install in development mode
pip install -e ".[dev]"

# Run validation
python scripts/validate.py --all
```

## Contributing

### Code Changes
1. **Create feature branch** from main
2. **Make changes** following code style guidelines
3. **Run tests** and ensure all pass
4. **Update documentation** if needed
5. **Submit pull request** with clear description

### Pull Request Process
- **Automatic CI**: Linting, unit tests, security scans
- **Integration Tests**: Validates against AWS resources
- **Code Review**: Required before merge
- **Documentation**: Update relevant docs

### Release Process
1. **Version bump** in `pyproject.toml`
2. **Update changelog** with new features/fixes
3. **Tag release** following semantic versioning
4. **Publish to PyPI** (automated via GitHub Actions)

## Architecture

### Project Structure
```
smus_cicd/
├── cli.py              # Main CLI entry point
├── commands/           # CLI command implementations
├── helpers/            # Utility functions and AWS integrations
├── pipeline/           # Pipeline manifest and validation
└── __init__.py
```

### Key Components
- **CLI Commands**: Create, describe, bundle, deploy, test, monitor, run, delete
- **Bundle Manifest**: YAML configuration for multi-environment deployments
- **AWS Integrations**: DataZone, MWAA, S3, CloudFormation
- **Bundle Management**: S3-based artifact storage and deployment

## Troubleshooting

### Common Issues
- **AWS Credentials**: Ensure proper IAM permissions for DataZone and MWAA
- **Domain/Project IDs**: Use `aws datazone list-domains` and `list-projects`
- **S3 Permissions**: Verify access to bundle storage locations
- **MWAA Connectivity**: Check VPC and security group configurations

### Debug Mode
```bash
# Enable verbose logging
export SMUS_CLI_DEBUG=1
smus-cli <command> --verbose
```

### Integration Test Setup
```bash
# Deploy GitHub OIDC integration
cd tests/integration/github
./deploy-github-integration.sh

# Run integration tests locally
python scripts/validate.py --integration
```

# SMUS CLI Tests

This directory contains unit tests and integration tests for the SMUS CI/CD CLI.

## Prerequisites for Integration Tests

Before running integration tests, you must deploy the required AWS infrastructure:

### 1. Deploy SageMaker Domain
```bash
cd tests/scripts
./deploy-domain.sh
```

### 2. Deploy Environment Blueprints and Profiles
```bash
cd tests/scripts
./deploy-blueprints-profiles.sh
```

### 3. Deploy Dev Project
```bash
cd tests/scripts
./deploy-projects.sh
```

**Important:** These scripts must be run in order as they have dependencies on each other. The integration tests require these AWS resources to be deployed and available.

## Test Structure

```
tests/
├── unit/                 # Unit tests (no AWS credentials required)
│   ├── test_describe.py     # Tests for describe command
│   ├── test_bundle.py    # Tests for bundle command
│   └── test_monitor.py   # Tests for monitor command
├── integration/          # Integration tests (require AWS credentials)
│   ├── config.yaml       # Default integration test configuration
│   ├── config.local.yaml # Local configuration (create from config.yaml)
│   ├── base.py           # Base class for integration tests
│   ├── basic_pipeline/   # Basic pipeline test suite
│   │   ├── basic_pipeline.yaml        # Basic pipeline configuration
│   │   ├── test_basic_pipeline.py     # Basic pipeline tests
│   │   └── README.md                  # Test documentation
│   └── multi_target_pipeline/         # Multi-target pipeline test suite
│       ├── multi_target_pipeline.yaml # Multi-target pipeline configuration
│       ├── test_multi_target_pipeline.py # Multi-target tests
│       └── README.md                  # Test documentation
└── requirements.txt      # Test dependencies
```

## Running Tests (Python-Native)

### Prerequisites

Install test dependencies:
```bash
pip install -r tests/requirements.txt
```

### Quick Validation Commands

Use the Python validation script for all testing needs:

```bash
# Unit tests only (no AWS credentials required)
python scripts/validate.py --unit

# Integration tests (automatically refreshes AWS credentials)
python scripts/validate.py --integration

# README examples validation
python scripts/validate.py --readme

# AWS credentials refresh
python scripts/validate.py --aws-login

# Full validation pipeline
python scripts/validate.py --all

# Clean temporary files
python scripts/validate.py --clean
```

### Unit Tests (No AWS Credentials Required)

Unit tests use mocks and don't require AWS credentials:

```bash
# Using validation script (recommended)
python scripts/validate.py --unit

# Or directly with pytest
pytest tests/unit/ -v

# Or legacy method
python run_tests.py --type unit
```

### Integration Tests (Require AWS Credentials)

Integration tests require valid AWS credentials and may interact with real AWS resources.

#### Setup Integration Tests

1. **Copy configuration file:**
```bash
cp tests/integration/config.yaml tests/integration/config.local.yaml
```

2. **Edit configuration:**
```yaml
# tests/integration/config.local.yaml
aws:
  profile: your-aws-profile  # or use access keys
  region: us-east-1

test_environment:
  domain_name: your-test-domain
  project_prefix: integration-test
```

3. **Run integration tests:**
```bash
# Using validation script (recommended - auto-refreshes AWS credentials)
python scripts/validate.py --integration

# Or check AWS setup first
python run_integration_tests.py --check-setup

# Or legacy methods
python run_integration_tests.py --type basic
python run_integration_tests.py --type all
```

### All Tests

```bash
# Full validation (recommended)
python scripts/validate.py --all

# Or legacy method
python run_tests.py --type all
```

## Python-Native Testing Approach

The project now uses modern Python tooling:

### Configuration Files
- `pyproject.toml` - Modern Python project configuration
- `scripts/validate.py` - Python validation script (replaces Makefile)

### Validation Script Features
- ✅ Automatic AWS credential refresh with `isenguardcli`
- ✅ Unit test execution
- ✅ Integration test execution  
- ✅ README example validation
- ✅ Cleanup utilities
- ✅ Cross-platform compatibility

### Alternative pytest Commands
```bash
# Direct pytest usage
pytest tests/unit/                          # Unit tests
pytest tests/integration/ -m "not slow"     # Integration tests
pytest tests/ -m "not slow" -v             # All tests excluding slow ones
```

## Integration Test Features

### Test Scenarios

Each integration test uses its own pipeline configuration:

- **`basic_pipeline.yaml`** - Single target pipeline
- **`multi_target_pipeline.yaml`** - Multiple targets (dev, test, prod)

### Test Categories

- **Basic Tests** - Describe, bundle, monitor commands
- **Multi-Target Tests** - Operations across multiple targets
- **Validation Tests** - Error handling and edge cases
- **Slow Tests** - Full end-to-end workflows (marked with `@pytest.mark.slow`)

### Test Workflow

Each integration test follows this pattern:

1. **Setup** - Configure AWS credentials and test environment
2. **Describe** - Validate pipeline configuration
3. **Bundle** - Create deployment packages (may fail if resources don't exist)
4. **Monitor** - Check pipeline status
5. **Cleanup** - Remove temporary resources
6. **Report** - Generate success/failure report

### Expected Behavior

Integration tests are designed to be **informative** rather than strictly pass/fail:

- ✅ **Commands execute successfully** - CLI works correctly
- ⚠️ **Expected failures** - Missing AWS resources (marked as success)
- ❌ **Unexpected failures** - CLI bugs or configuration issues

## Test Categories

### Unit Tests
- **No AWS credentials required**
- Use mocks for AWS services
- Test CLI command logic and parsing
- Fast execution
- Safe to run in CI/CD

### Integration Tests
- **Require AWS credentials**
- May interact with real AWS resources
- Test end-to-end workflows
- Slower execution
- Should be run in dedicated test environments

## Environment Variables

### For Integration Tests

- `AWS_PROFILE` or `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` - AWS credentials
- `AWS_DEFAULT_REGION` - AWS region (defaults to us-east-1)

### Test Markers

- `@pytest.mark.slow` - Slow running tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.aws` - Tests requiring AWS credentials

## Example Usage

```bash
# Recommended Python-native approach
python scripts/validate.py --unit           # Fast unit tests
python scripts/validate.py --integration    # Integration tests with auto AWS login
python scripts/validate.py --readme         # Validate README examples
python scripts/validate.py --all            # Full validation pipeline

# Alternative pytest commands
pytest tests/unit/ -v                       # Unit tests only
pytest tests/integration/ -m "not slow" -v  # Integration tests excluding slow ones
pytest tests/integration/test_basic_pipeline.py -v  # Specific test file

# Legacy commands (still supported)
python run_tests.py --type unit
python run_integration_tests.py --type basic
```

## Integration Test Configuration

The `config.yaml` file controls integration test behavior:

```yaml
aws:
  profile: default
  region: us-east-1

test_environment:
  domain_name: integration-test-domain
  project_prefix: integration-test
  cleanup_after_tests: true

test_scenarios:
  basic_pipeline:
    enabled: true
    pipeline_file: "basic_pipeline.yaml"
  multi_target_pipeline:
    enabled: true
    pipeline_file: "multi_target_pipeline.yaml"

timeouts:
  project_creation: 300
  bundle_creation: 120
```

## AWS Credential Management

The validation script automatically handles AWS credentials:

```bash
# Manual credential refresh
python scripts/validate.py --aws-login

# Integration tests automatically refresh credentials
python scripts/validate.py --integration
```

This uses `isenguardcli` internally and verifies credentials with `aws sts get-caller-identity`.

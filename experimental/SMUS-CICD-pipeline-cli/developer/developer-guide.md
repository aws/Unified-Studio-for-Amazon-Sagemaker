# SMUS CI/CD Developer Guide

## Architecture Overview

### Core Components

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

### Key Design Patterns

1. **Manifest-Driven**: All configuration in `manifest.yaml`
2. **Multi-Stage**: Support for dev/test/prod environments
3. **Idempotent**: Commands can be run multiple times safely
4. **Event-Driven**: EventBridge integration for CI/CD pipelines

## Testing Framework

### Structure

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

### GitHub CI/CD Integration

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

### Base Test Class

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

### Running Tests

**Using run_tests.py (Recommended):**
```bash
# All tests
python tests/run_tests.py --type all

# Integration tests only
python tests/run_tests.py --type integration

# Parallel execution (auto-detect CPUs)
python tests/run_tests.py --type integration --parallel

# Parallel with specific workers
python tests/run_tests.py --type integration --parallel --workers 4

# Skip coverage for faster runs
python tests/run_tests.py --type integration --parallel --no-coverage
```

**Using pytest directly:**
```bash
# All integration tests
pytest tests/integration/ -v

# Specific test
pytest tests/integration/examples-analytics-workflows/dashboard-glue-quick/ -v -s

# Parallel execution
pytest tests/integration/ -n auto -v
```

### Parallel Test Execution

**Project Isolation:**
- Each test uses unique project names (e.g., `test-dashboard-quick`, `test-ml-training`)
- Shared dev project: `dev-marketing` (read-only)
- Reserved: `test-marketing`, `prod-marketing` (long-standing projects)

**Log Isolation:**
- Unique log files: `tests/test-outputs/{TestClass}__{test_method}.log`
- Worker ID appended for parallel runs: `{test}__{worker_id}.log`

**Best Practices:**
- Never hardcode project names
- Use regex patterns: `test-[\w-]+` instead of specific names
- Clean up resources in teardown
- Avoid shared state between tests

## Development Workflow

### 1. Setup Development Environment

```bash
# Install dependencies
pip install -e .
pip install -r requirements-dev.txt

# Configure AWS credentials
export AWS_PROFILE=your-profile
# or use tests/scripts/config.yaml
```

### 2. Make Code Changes

Follow PEP 8 style guidelines. Pre-commit hooks will run:
- `black` - Code formatting
- `flake8` - Linting

### 3. Run Tests

```bash
# Unit tests (fast)
python tests/run_tests.py --type unit

# Integration tests (requires AWS)
python tests/run_tests.py --type integration

# Parallel for faster feedback
python tests/run_tests.py --type integration --parallel
```

### 4. Update Documentation

User-facing docs in `docs/`:
- `manifest.md` - Manifest schema reference
- `cli-commands.md` - CLI command reference
- `bootstrap-actions.md` - Bootstrap actions guide
- `quicksight-deployment.md` - QuickSight deployment guide

## Code Organization

### Adding New Commands

1. Create command file in `src/smus_cicd/commands/`
2. Use Typer for CLI interface
3. Import helpers for AWS operations
4. Add tests in `tests/integration/`

### Adding New Bootstrap Actions

1. Create handler in `src/smus_cicd/bootstrap/handlers/`
2. Register in `src/smus_cicd/bootstrap/executor.py`
3. Document in `docs/bootstrap-actions.md`
4. Add tests

### Adding New Helpers

1. Create helper in `src/smus_cicd/helpers/`
2. Keep functions focused and reusable
3. Add error handling and logging
4. Write unit tests in `tests/unit/helpers/`

## Common Patterns

### CLI Command Structure
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

### Helper Function Structure
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

### Integration Test Structure
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

## Debugging

### Enable Debug Logging
```bash
export SMUS_DEBUG=1
python -m smus_cicd.cli deploy test --manifest manifest.yaml
```

### Check Integration Test Logs
```bash
# Latest test log
ls -lt tests/test-outputs/*.log | head -1

# View specific test log
cat tests/test-outputs/TestMyFeature__test_method.log
```

### Common Issues

**Import Errors:**
- Ensure package installed: `pip install -e .`
- Check Python path includes src directory

**AWS Credential Errors:**
- Verify AWS_PROFILE or credentials configured
- Check IAM permissions for DataZone, S3, CloudFormation

**Test Failures:**
- Check test-outputs logs for detailed error messages
- Verify AWS resources exist (projects, domains)
- Ensure cleanup ran from previous test runs

## Resources

- **User Documentation**: `docs/` directory
- **Examples**: `examples/` directory
- **Test Setup**: `tests/scripts/setup/` directory
- **Main README**: `README.md`

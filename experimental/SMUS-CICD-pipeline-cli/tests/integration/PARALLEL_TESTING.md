# Parallel Test Execution Guide

## Overview

All integration tests are designed to run in parallel using pytest-xdist. Each test uses isolated resources to prevent conflicts.

## Project Naming Strategy

### Shared Resources
- **dev-marketing**: Shared dev project (read-only operations, used by all tests)

### Reserved Projects
- **test-marketing**: Reserved for long-standing test project
- **prod-marketing**: Reserved for long-standing prod project

### Test-Specific Projects
Each analytics workflow test creates its own unique test project:

| Test | Project Name | Manifest |
|------|-------------|----------|
| Dashboard + QuickSight | `test-dashboard-quick` | `examples/analytic-workflow/dashboard-glue-quick/manifest.yaml` |
| ML Training | `test-ml-training` | `examples/analytic-workflow/ml/training/manifest.yaml` |
| ML Deployment | `test-ml-deployment` | `examples/analytic-workflow/ml/deployment/manifest.yaml` |
| GenAI | `test-genai` | `examples/analytic-workflow/genai/manifest.yaml` |
| Notebooks | `test-notebooks` | `examples/analytic-workflow/data-notebooks/manifest.yaml` |

## Log File Isolation

Each test generates its own log file in `tests/test-outputs/`:
- Format: `{TestClass}__{test_method_name}.log`
- Parallel workers: `{TestClass}__{test_method_name}_{worker_id}.log`
- Example: `TestDashboardGlueQuickWorkflow__test_dashboard_glue_quick_workflow_deployment_gw0.log`

## Running Tests in Parallel

### Using run_tests.py (Recommended)

The `tests/run_tests.py` script provides a convenient wrapper with parallel execution support:

```bash
# Run all integration tests in parallel (auto-detect CPU cores)
python tests/run_tests.py --type integration --parallel

# Run all integration tests with 4 workers
python tests/run_tests.py --type integration --parallel --workers 4

# Run all tests (unit + integration) in parallel
python tests/run_tests.py --type all --parallel

# Run with parallel execution and skip coverage (faster)
python tests/run_tests.py --type integration --parallel --no-coverage
```

### Using pytest directly

### Run all integration tests in parallel (4 workers)
```bash
pytest tests/integration/ -n 4 -v
```

### Run analytics workflow tests in parallel
```bash
pytest tests/integration/examples-analytics-workflows/ -n 5 -v
```

### Run specific test suite in parallel
```bash
pytest tests/integration/examples-analytics-workflows/ml/ -n 2 -v
```

### Run with auto-detection of CPU cores
```bash
pytest tests/integration/ -n auto -v
```

## Test Isolation Guarantees

1. **Project Isolation**: Each test creates/deletes its own project
2. **Log Isolation**: Unique log files per test and worker
3. **Resource Naming**: Unique workflow/resource names per project
4. **S3 Isolation**: Each project has its own S3 bucket/prefix
5. **Cleanup**: Tests clean up their own resources in teardown

## Best Practices

1. **Never hardcode project names**: Use manifest-defined project names
2. **Use regex patterns**: Match `test-[\w-]+` instead of specific names
3. **Clean up resources**: Always delete created projects in teardown
4. **Unique identifiers**: Use test-specific prefixes for resources
5. **Avoid shared state**: Don't rely on resources from other tests

## Troubleshooting

### Tests fail with resource conflicts
- Check if project names are unique
- Verify cleanup is running in teardown
- Check for hardcoded project references

### Log files are overwritten
- Ensure test names are unique
- Check if worker ID is being appended
- Verify `PYTEST_XDIST_WORKER` environment variable

### Parallel execution is slow
- Reduce number of workers if hitting AWS rate limits
- Check if tests are waiting for long-running operations
- Consider splitting slow tests into separate runs

## CI/CD Integration

GitHub Actions can run tests in parallel:

```yaml
- name: Run Integration Tests
  run: |
    pytest tests/integration/ -n 4 -v --dist loadgroup
```

Use `--dist loadgroup` to group tests by class, ensuring related tests run on the same worker.

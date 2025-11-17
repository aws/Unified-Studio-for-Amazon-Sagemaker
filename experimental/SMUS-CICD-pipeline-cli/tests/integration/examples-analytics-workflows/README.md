# Analytics Workflows Integration Tests

Integration tests for analytics workflow examples.

See [developer-guide.md](../../../developer-guide.md) for testing framework details.

## Tests

- `dashboard-glue-quick/` - Dashboard with Glue and QuickSight
- `ml/` - ML training and deployment workflows
- `genai/` - GenAI workflows
- `notebooks/` - Notebook execution workflows

## Running

```bash
# All analytics tests in parallel
pytest tests/integration/examples-analytics-workflows/ -n auto -v

# Specific test
pytest tests/integration/examples-analytics-workflows/dashboard-glue-quick/ -v -s
```

## Project Names

Each test uses a unique project to enable parallel execution:
- `test-dashboard-quick`
- `test-ml-training`
- `test-ml-deployment`
- `test-genai`
- `test-notebooks`

Shared dev project: `dev-marketing` (read-only)

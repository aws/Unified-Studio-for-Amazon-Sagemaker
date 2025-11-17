# SMUS CI/CD Tests

See [developer-guide.md](../developer-guide.md) for comprehensive testing documentation.

## Quick Start

```bash
# Run all tests
python tests/run_tests.py --type all

# Run integration tests in parallel
python tests/run_tests.py --type integration --parallel

# Run specific test
pytest tests/integration/examples-analytics-workflows/dashboard-glue-quick/ -v -s
```

## Structure

- `unit/` - Unit tests (fast, no AWS)
- `integration/` - Integration tests (real AWS resources)
- `run_tests.py` - Test runner with parallel support
- `scripts/` - Setup and utility scripts

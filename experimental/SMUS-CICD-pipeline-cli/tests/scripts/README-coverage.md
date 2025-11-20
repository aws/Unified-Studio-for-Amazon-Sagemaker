# Coverage Report Combining

## Overview

PR tests run in parallel, each generating separate coverage files. This script combines them into a unified coverage report.

## Quick Start

```bash
# 1. Download artifacts from GitHub Actions
gh run download <RUN-ID> -n test-summary-combined

# 2. Combine coverage reports
python tests/scripts/combine_coverage.py

# 3. View combined report
open coverage-combined/htmlcov-combined/index.html
```

## Coverage Files Generated

Each test job produces:
- `coverage-unit.xml` - Unit tests
- `coverage-basic-app.xml` - Basic app integration tests
- `coverage-multi-target.xml` - Multi-target tests
- `coverage-airless.xml` - Airless deployment tests
- `coverage-app-deploy.xml` - App deployment tests
- `coverage-connections.xml` - Connection tests
- `coverage-catalog.xml` - Catalog asset tests
- `coverage-other.xml` - Other integration tests
- `coverage-delete.xml` - Deletion tests

## Usage

### Download Latest PR Test Results

```bash
# List recent workflow runs
gh run list --workflow=pr-tests.yml --limit 5

# Download specific run
gh run download <RUN-ID> -n test-summary-combined

# This creates: coverage-artifacts/
```

### Combine Coverage

```bash
# Default (uses coverage-artifacts/ directory)
python tests/scripts/combine_coverage.py

# Custom directories
python tests/scripts/combine_coverage.py \
  --coverage-dir path/to/artifacts \
  --output-dir path/to/output
```

### View Results

```bash
# HTML report
open coverage-combined/htmlcov-combined/index.html

# XML report (for tools)
cat coverage-combined/coverage-combined.xml

# Terminal summary
cd coverage-combined && coverage report
```

## Test Summary

The test-summary job also generates a markdown summary:

```bash
cat coverage-artifacts/test-summary.md
```

Example output:
```
# Test Results Summary

✅ **unit**: 150 tests passed
✅ **basic-app**: 12 tests passed
❌ **multi-target**: 2 failures, 0 errors out of 15 tests
✅ **connections**: 8 tests passed
```

## CI/CD Integration

The workflow automatically:
1. Runs tests in parallel
2. Generates individual coverage files
3. Uploads all artifacts to `test-summary-combined`
4. Creates test summary markdown

Developers can then:
1. Download the combined artifact
2. Run the combine script locally
3. View full coverage report

## Troubleshooting

**No coverage files found:**
- Ensure you downloaded the correct artifact: `test-summary-combined`
- Check that tests actually ran (not skipped)

**Coverage combine fails:**
- Requires `.coverage` data files (not just XML)
- Current workflow only uploads XML - consider adding `.coverage` files to artifacts

**Missing test results:**
- Check if test job failed before coverage generation
- Review job logs in GitHub Actions

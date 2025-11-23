# Test Workflow and Process

## Automated Workflow for Code Changes

### 0. AWS Credentials Setup (when needed)
```bash
# Check AWS credentials using test runner
python tests/run_tests.py --type integration
# If credentials are missing, you'll see a warning

# Or manually:
isenguardcli
aws sts get-caller-identity
```

### 1. Pre-Change Validation
```bash
# Verify current state is clean
python tests/run_tests.py --type unit
python tests/run_tests.py --type integration
git status
```

### 2. Make Code Changes
- Implement the requested feature/fix
- Update relevant docstrings and comments
- Follow code standards (see code-standards.md)
- Run linting checks

### 3. Update Test Cases
```bash
# Run tests to identify failures
python tests/run_tests.py --type unit

# Fix any failing tests by:
# - Updating test expectations to match new behavior
# - Adding new test cases for new functionality
# - Ensuring mock objects match actual implementation
# - Verifying CLI parameter usage is correct
```

### 4. Update README and Documentation
```bash
# Update README.md if:
# - CLI syntax changed
# - New commands added
# - Examples need updating
# - Diagrams need modification

# Verify examples work by running tests
python tests/run_tests.py --type all
```

### 5. Integration Test Validation
```bash
# Run with detailed logging (creates logs in tests/test-outputs/)
python run_integration_tests_with_logs.py

# Or without logging
python tests/run_tests.py --type integration

# Skip slow tests
python tests/run_tests.py --type integration --skip-slow
```

**IMPORTANT: Verifying Test Results**
- NEVER re-run test to check if it passed
- ALWAYS check logs first: `tests/test-outputs/{test_name}.log`
- ALWAYS check notebooks: `tests/test-outputs/notebooks/` (underscore-prefixed = actual outputs)

```bash
# Check logs and notebooks
cat tests/test-outputs/TestMLWorkflow__test_ml_workflow_deployment.log
ls tests/test-outputs/notebooks/_*.ipynb
grep -i "error\|failed\|exception" tests/test-outputs/*.log
```

**CRITICAL: Integration Tests Are Slow (10-15 min) - Test Fixes Quickly First**

1. Identify issue from logs/notebooks
2. Create small test script (30 sec - 1 min)
3. Iterate on fix with small script
4. Only then run full integration test

```bash
# Quick test examples:
# Notebook: python -c "import papermill as pm; pm.execute_notebook('nb.ipynb', '/tmp/out.ipynb', parameters={'p': 'v'})"
# Manifest: python -c "from smus_cicd.application.application_manifest import ApplicationManifest; m = ApplicationManifest.from_file('manifest.yaml'); print(m.initialization)"
# CLI: smus-cli describe --manifest manifest.yaml

# Run full integration test only after fix confirmed working
```

### 6. Final Validation and Commit
```bash
# Full validation with coverage
python tests/run_tests.py --type all

# Commit changes
git add .
git commit -m "Descriptive commit message

- List specific changes made
- Note test updates
- Note documentation updates"

# Verify clean state
git status
```

### 7. Push Changes and Monitor PR
```bash
# Push changes to GitHub
git push origin your_feature_branch

# Wait 5 minutes for CI/CD to process
sleep 300

# Check PR status and analyze test results
gh pr checks <PR-NUMBER>

# Get detailed logs for any failing tests
gh run view <RUN-ID> --job <JOB-NAME> --log

# Download combined coverage report
gh run download <RUN-ID> -n test-summary-combined
python tests/scripts/combine_coverage.py --coverage-dir tests/test-outputs/coverage-artifacts

# Analyze failures and provide summary:
# - What tests are failing and why
# - Root cause analysis of failures
# - Recommended fixes needed
# - Whether failures are related to code changes or infrastructure

# IMPORTANT: Do not push additional changes without approval
# - Present analysis of test failures first
# - Wait for confirmation before implementing fixes
# - Ensure all stakeholders understand the impact
```

## Test Runner Options

```bash
# Available test types:
python tests/run_tests.py --type unit           # Unit tests only
python tests/run_tests.py --type integration    # Integration tests only
python tests/run_tests.py --type all            # All tests (default)

# Additional options:
--no-coverage        # Skip coverage analysis
--no-html-report    # Skip HTML test results and coverage reports
--skip-slow         # Skip slow tests (marked with @pytest.mark.slow)
--coverage-only     # Only generate coverage report from existing data

# Alternative using pytest directly:
pytest tests/unit/                          # Unit tests
pytest tests/integration/ -m "not slow"     # Integration tests (skip slow)
```

## Checklist for Any Code Change

- [ ] AWS credentials configured (when needed)
- [ ] **Code formatting and imports are clean:**
  - [ ] `flake8 src/smus_cicd/ --config=setup.cfg` passes
  - [ ] `black --check src/smus_cicd/` passes  
  - [ ] `isort --check-only src/smus_cicd/` passes
- [ ] Unit tests pass
- [ ] Integration tests pass (basic suite)
- [ ] README examples are accurate and tested
- [ ] CLI help text is updated if needed
- [ ] New functionality has corresponding tests
- [ ] Mock objects match real implementation
- [ ] CLI parameter usage is consistent
- [ ] Documentation reflects actual behavior
- [ ] **DataZone API calls handle pagination** (check for nextToken)
- [ ] **DataZone API calls handle field compatibility** (new vs legacy fields)
- [ ] **Environment variables used instead of hardcoded values** (account IDs, ARNs, regions)
- [ ] Check that the code and markdown files don't contain aws account ids, web addresses, or host names
- [ ] Check that lint is passing
- [ ] Don't swallow exceptions, if an error is thrown, it must be logged or handled
- [ ] All changes are committed
- [ ] **PR Monitoring and Analysis:**
  - [ ] Changes pushed to GitHub
  - [ ] PR status monitored for 5+ minutes
  - [ ] All CI/CD workflows analyzed
  - [ ] Test failures documented with root cause analysis
  - [ ] Summary of failures provided before additional changes
  - [ ] Approval received before pushing fixes

## Common Test Patterns to Maintain

### Unit Test Patterns
- Mock objects need proper attributes, not dictionaries
- Test expectations should match actual output format
- Use proper patch decorators for dependencies

### Integration Test Patterns
- Use `["describe", "--pipeline", file]` not `["describe", file]`
- Expected exit codes should match test framework expectations
- Rename DAG files to avoid pytest collection (`.dag` extension)
- Source environment variables before running tests (`source env-local.env`)
- Verify workflow failures when expected (e.g., expected_failure_workflow)
- Check workflow statuses from monitor output, not manual workflow starts

### README Patterns
- All CLI examples use correct parameter syntax
- Include realistic command outputs
- Keep examples concise but informative
- Verify examples actually work before documenting
- Use environment variables instead of hardcoded account IDs/ARNs

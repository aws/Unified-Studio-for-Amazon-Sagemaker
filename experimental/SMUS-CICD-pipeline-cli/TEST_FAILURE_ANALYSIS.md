# Test Failure Analysis - SMUS CI/CD CLI

**Date:** 2025-11-07  
**Total Tests:** 299  
**Passed:** 229 (76.6%)  
**Failed:** 13  
**Errors:** 37  
**XFailed:** 8 (expected)  
**XPassed:** 12 (unexpected passes)

---

## Critical Issues

### 1. Coverage Data Conflict (BLOCKER)
**Error:** `DataError: Can't combine statement coverage data with branch data`

**Root Cause:** 
- pytest.ini has `--cov=src/smus_cicd` with branch coverage enabled by default
- Some test runs create coverage data with branch tracking, others without
- Coverage combine operation fails when mixing these formats

**Impact:** Test suite crashes at teardown, preventing proper completion

**Fix Required:**
- Ensure consistent coverage configuration across all test runs
- Clean `.coverage*` files before running tests
- Add `--cov-branch` explicitly or remove branch coverage

---

## Unit Test Failures (2)

### 2. test_bundle_no_default_target
**File:** `tests/unit/test_bundle.py:145`

**Expected:** `"No target specified and no DEV stage target found"`  
**Actual:** `"Error: Target 'dev' not found in manifest"`

**Root Cause:** Error message changed in implementation but test wasn't updated

**Fix:** Update test assertion to match new error message

---

### 3. test_resolve_missing_variable
**File:** `tests/unit/test_context_resolver.py:134`

**Expected:** Test should handle missing variable gracefully  
**Actual:** `ValueError: Failed to resolve variables: {env.DOES_NOT_EXIST}`

**Root Cause:** Context resolver now raises exceptions for missing variables instead of returning None/warning

**Fix:** Update test to expect ValueError exception

---

## Integration Test Failures

### 4. Connection API Tests (4 ERRORS)
**Files:**
- `test_all_connection_types.py`
- `test_connection_validation.py`
- `test_connection_validation_fixed.py`
- `test_working_connections.py`

**Error:** `fixture 'client' not found`

**Root Cause:** Missing pytest fixture definition for `client` parameter

**Fix:** Add conftest.py with client fixture or mark tests as skipped

---

### 5. Bundle Deploy Pipeline Tests (2 FAILURES)

#### 5a. test_describe_connect_validation
**File:** `tests/integration/bundle_deploy_pipeline/pipeline_tests/test_bundle_validation.py:98`

**Expected:** MWAA connection details in describe output  
**Actual:** Connection name shown but not full details

**Root Cause:** Describe command output format changed - connections now shown differently

**Fix:** Update test assertion to match new output format

---

#### 5b. test_bundle_deploy_workflow
**File:** `tests/integration/bundle_deploy_pipeline/test_bundle_deploy_pipeline.py:339`

**Errors:**
1. `create` command: `No such option: --pipeline` (should be manifest file path)
2. `deploy` command: `Project profile 'All capabilities' not found`
3. `monitor` command: `No such option: --tasks` (should be different flag)

**Root Cause:** 
- Test using outdated CLI syntax
- Missing DataZone domain configuration
- Project profile name doesn't exist in test environment

**Fix:** 
- Update CLI commands to current syntax
- Configure proper domain in test manifest
- Use existing project profile name

---

### 6. Multi-Target Pipeline Tests (18 FAILURES)

#### 6a. Project Validation Tests (3 FAILURES)
**Files:** `test_project_validation.py` (both MWAA and Overdrive versions)

**Tests:**
- `test_environment_variables_available`
- `test_project_context`
- `test_domain_and_project_ids`

**Error:** `domain_name should be in test_environment`

**Root Cause:** Config file `config-4947-dev.yaml` has `domain_tags` but missing `domain_name` field

**Fix:** Add `domain_name` to config files or update tests to use domain_tags

---

#### 6b. Describe Connect Tests (11 FAILURES)
**Pattern:** All `test_describe_connect_*` tests failing

**Common Error:** Domain not found / Project doesn't exist

**Root Cause:** 
- Tests expect pre-existing DataZone domain and projects
- Config files missing domain_name field
- Tests not creating required infrastructure before running

**Fix:**
- Add domain_name to config files
- Update tests to create/cleanup infrastructure
- Or mark as requiring pre-existing environment

---

#### 6c. Test Command Integration (2 FAILURES)
**Tests:**
- `test_test_command_json_output`
- `test_actual_test_execution`

**Root Cause:** Likely related to missing domain configuration

**Fix:** Same as 6b - fix domain configuration

---

## Summary by Category

### Infrastructure/Configuration Issues (HIGH PRIORITY)
1. **Coverage data conflict** - Blocks test completion
2. **Missing domain_name in configs** - Affects 18+ tests
3. **Missing pytest fixtures** - Affects 4 tests

### Test Code Issues (MEDIUM PRIORITY)
4. **Outdated CLI syntax** - 3 commands in bundle_deploy tests
5. **Outdated assertions** - 2 unit tests expecting old error messages
6. **Missing test infrastructure** - Tests assume pre-existing DataZone resources

### Expected Behaviors (LOW PRIORITY)
7. **12 XPassed tests** - Tests marked as expected failures now passing (good!)
8. **8 XFailed tests** - Tests correctly marked as expected failures

---

## Recommended Fix Order

1. **FIRST:** Fix coverage configuration issue (blocks everything)
2. **SECOND:** Add domain_name to config files (fixes 18+ tests)
3. **THIRD:** Add missing pytest fixtures or skip connection API tests
4. **FOURTH:** Update bundle_deploy tests with correct CLI syntax
5. **FIFTH:** Update unit test assertions for new error messages
6. **SIXTH:** Review XPassed tests - remove xfail markers if intentionally fixed

---

## Files Requiring Changes

### Configuration Files
- `tests/scripts/config-4947-dev.yaml` - Add domain_name
- `tests/scripts/config-8272-dev.yaml` - Add domain_name
- `tests/scripts/config-6778.yaml` - Add domain_name
- `tests/scripts/config-9033-dev.yaml` - Add domain_name
- `pytest.ini` - Fix coverage configuration

### Test Files
- `tests/unit/test_bundle.py` - Update error message assertion
- `tests/unit/test_context_resolver.py` - Expect ValueError
- `tests/integration/bundle_deploy_pipeline/test_bundle_deploy_pipeline.py` - Fix CLI syntax
- `tests/integration/bundle_deploy_pipeline/pipeline_tests/test_bundle_validation.py` - Update output format check
- `tests/integration/connections/api_validation/conftest.py` - Add client fixture (create file)
- `tests/integration/multi_target_pipeline/pipeline_tests/test_project_validation.py` - Use domain_tags or add domain_name

### Cleanup Required
- Remove `.coverage*` files before test runs
- Consider adding pre-test cleanup script

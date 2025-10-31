# Unit Test Failure Analysis

## Summary
28 tests failed, 148 passed, 9 xfailed, 11 xpassed

## Root Cause: Schema Breaking Changes

The manifest schema was updated but test fixtures were not updated to match. The schema now requires different structure for bundle configuration.

## Key Schema Changes

### 1. Bundle Storage Configuration
**Old Format (in tests):**
```yaml
bundle:
  storage:
    - connectionName: default.s3_shared
      include: ['src']
```

**New Format (required by schema):**
```yaml
bundle:
  storage:
    - name: code              # NEW: 'name' is now REQUIRED
      connectionName: default.s3_shared
      include: ['src']
```

**Error:** `Path 'bundle -> storage -> 0': 'name' is a required property`

### 2. Bundle Workflow vs Workflows
**Old Format (in tests):**
```yaml
bundle:
  workflow:                   # WRONG: singular 'workflow'
    - connectionName: default.s3_shared
```

**New Format (required by schema):**
```yaml
bundle:
  storage:                    # Workflows are now part of storage items
    - name: workflows
      connectionName: default.s3_shared
```

**Error:** `Path 'bundle': Additional properties are not allowed ('workflow' was unexpected)`

### 3. Bundle Target Configuration Storage
**Old Format (in tests):**
```yaml
bundle_target_configuration:
  storage:                    # WRONG: object format
    connectionName: default.s3_shared
    directory: src
  workflows:                  # WRONG: not allowed here
    connectionName: default.s3_shared
    directory: workflows
```

**New Format (required by schema):**
```yaml
bundle_target_configuration:
  storage:                    # CORRECT: array format
    - name: code
      connectionName: default.s3_shared
      directory: src
```

**Errors:**
- `Path 'targets -> test -> bundle_target_configuration -> storage': {...} is not of type 'array'`
- `Path 'targets -> test -> bundle_target_configuration': Additional properties are not allowed ('workflows' was unexpected)`

## Affected Test Categories

### Category 1: Catalog Asset Tests (4 failures)
**Files:**
- `tests/unit/commands/test_deploy_catalog_assets.py`
- `tests/unit/commands/test_deploy_catalog_negative.py`

**Issue:** Test manifests use old bundle format

**Tests:**
- `test_catalog_asset_manifest_parsing`
- `test_empty_asset_identifier`
- `test_empty_assets_array`
- `test_mixed_valid_invalid_assets`

### Category 2: Bundle Command Tests (3 failures)
**File:** `tests/unit/test_bundle.py`

**Issue:** Tests expect default target behavior that changed

**Tests:**
- `test_bundle_default_target` - expects "Using default target: dev", gets error about no DEV stage
- `test_bundle_no_bundle_section` - expects "No files found", gets target error
- `test_bundle_no_default_target` - expects "no default target found", gets different error message

### Category 3: Create Command Tests (3 failures)
**File:** `tests/unit/test_create.py`

**Issue:** Generated manifests don't pass validation

**Tests:**
- `test_create_with_domain_and_project_no_warnings` - generated manifest fails validation
- `test_create_manifest_is_valid` - describe command returns exit code 1
- `test_create_default_stages` - missing "default: true" in generated manifest

### Category 4: Describe Command Tests (8 failures)
**Files:**
- `tests/unit/test_describe.py`
- `tests/unit/test_describe_comprehensive.py`
- `tests/unit/test_describe_new_features.py`

**Issue:** Test manifests use old format, causing validation failures

**Tests:**
- `test_describe_with_connections`
- `test_complex_manifest_with_workflows`
- `test_workflow_parameter_variations`
- `test_missing_domain_name` - expects exit code 1, gets 0 (validation logic changed)
- `test_default_values_not_hardcoded`
- `test_workflow_defaults`
- `test_special_characters_in_names`
- `test_describe_connections_flag_only`
- `test_describe_connections_flag`

### Category 5: Monitor Command Tests (1 failure)
**File:** `tests/unit/test_monitor.py`

**Issue:** Manifest validation failure

**Tests:**
- `test_monitor_all_targets`

### Category 6: Test Command Tests (7 failures)
**File:** `tests/unit/test_test_command.py`

**Issue:** All test command tests fail due to manifest validation

**Tests:**
- `test_test_command_no_tests_configured`
- `test_test_command_missing_test_folder`
- `test_test_command_with_test_folder`
- `test_test_command_json_output`
- `test_test_command_specific_target`
- `test_test_command_invalid_target`
- `test_test_command_verbose_output`

### Category 7: Validation Tests (1 failure)
**File:** `tests/unit/test_validation.py`

**Issue:** Test expectations don't match new schema

**Tests:**
- `test_missing_bundle_target_config_required_fields`

## Fix Strategy

### Priority 1: Update Test Helper Functions
1. Update `create_manifest_with_catalog()` in `test_deploy_catalog_assets.py`
2. Update manifest creation helpers across all test files

### Priority 2: Update Bundle Format
Fix all test manifests to use:
```yaml
bundle:
  storage:
    - name: code
      connectionName: default.s3_shared
      include: ['src']
    - name: workflows
      connectionName: default.s3_shared
      include: ['workflows']
```

### Priority 3: Update Bundle Target Configuration
Fix all test manifests to use:
```yaml
bundle_target_configuration:
  storage:
    - name: code
      connectionName: default.s3_shared
      directory: src
```

### Priority 4: Update Create Command Template
Fix the template in `src/smus_cicd/commands/create.py` to generate valid manifests

### Priority 5: Review Validation Logic
Check if validation error handling changed and update test expectations

## Recommended Approach

1. Create a test manifest template that matches the new schema
2. Update all test helper functions to use the new template
3. Run tests incrementally by category
4. Update create command to generate valid manifests
5. Review and update validation test expectations

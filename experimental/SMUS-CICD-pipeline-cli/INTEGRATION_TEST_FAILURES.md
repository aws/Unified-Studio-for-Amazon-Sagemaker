# Integration Test Failures Summary

**Test Run Date:** 2025-11-14  
**Total Tests:** 85  
**Passed:** 29 (34%)  
**Failed:** 49 (58%)  
**Skipped:** 4  
**Errors:** 4  
**Duration:** 45 minutes 7 seconds

---

## Root Cause Categories

### 1. Import Path Issues (6 failures)
**Root Cause:** Tests importing from old `smus_cicd.pipeline` module instead of `smus_cicd.application`

**Failed Tests:**
- `test_deploy_catalog_assets.py::TestDeployCatalogAssets::test_catalog_asset_manifest_parsing`
- `test_deploy_catalog_negative.py::TestDeployCatalogNegativeScenarios::test_invalid_manifest_structure`
- `test_deploy_catalog_negative.py::TestDeployCatalogNegativeScenarios::test_empty_asset_identifier`
- `test_deploy_catalog_negative.py::TestDeployCatalogNegativeScenarios::test_invalid_permission_value`
- `test_deploy_catalog_negative.py::TestDeployCatalogNegativeScenarios::test_empty_assets_array`
- `test_deploy_catalog_negative.py::TestDeployCatalogNegativeScenarios::test_mixed_valid_invalid_assets`

**Error Message:**
```
ModuleNotFoundError: No module named 'smus_cicd.pipeline'
```

**Fix Required:**
```python
# Change from:
from smus_cicd.pipeline.bundle_manifest import ApplicationManifest
from smus_cicd.pipeline import ApplicationManifest

# Change to:
from smus_cicd.application import ApplicationManifest
```

---

### 2. Manifest Schema Validation (15+ failures)
**Root Cause:** Test manifests still using old `pipelineName` field instead of `applicationName`

**Failed Tests:**
- `test_datazone_connections_e2e.py::TestDataZoneConnectionsE2E::test_datazone_connections_end_to_end`
- `test_multi_target_app.py::TestMultiTargetApp::test_describe_connect_nonexistent_project`
- `test_multi_target_app.py::TestMultiTargetApp::test_describe_connect_wrong_domain`
- `test_multi_target_app.py::TestMultiTargetApp::test_describe_connect_wrong_region`
- `test_multi_target_app.py::TestMultiTargetApp::test_describe_connect_multiple_targets_mixed_results`
- `test_multi_target_app.py::TestMultiTargetApp::test_describe_connect_invalid_connection_name`
- Multiple airless bundle tests with same issue

**Error Message:**
```
Manifest validation failed:
  - Path 'root': 'applicationName' is a required property
  - Path 'root': Additional properties are not allowed ('pipelineName' was unexpected)
```

**Fix Required:**
Update all test manifest YAML files:
```yaml
# Change from:
pipelineName: MyPipeline

# Change to:
applicationName: MyPipeline
```

---

### 3. Notebook Download Method Signature (4 failures)
**Root Cause:** Tests calling `download_and_validate_notebooks()` without required `workflow_arn` and `run_id` parameters

**Failed Tests:**
- `test_notebooks_workflow.py::TestNotebooksWorkflow::test_notebooks_workflow_deployment`
- `test_ml_deployment_workflow.py::TestMLDeploymentWorkflow::test_ml_deployment_workflow`
- `test_ml_training_workflow.py::TestMLTrainingWorkflow::test_ml_training_workflow`
- `test_basic_app.py::TestBasicApp::test_basic_pipeline_workflow` (partially - notebooks not found)

**Error Message:**
```
TypeError: IntegrationTestBase.download_and_validate_notebooks() missing 2 required positional arguments: 'workflow_arn' and 'run_id'
```

**Fix Required:**
Tests need to retrieve workflow_arn and run_id before calling the method:
```python
# Get workflow info
workflow_arn = get_workflow_arn_from_api()
run_id = get_latest_run_id(workflow_arn)

# Then call with parameters
self.download_and_validate_notebooks(s3_bucket, workflow_arn, run_id)
```

---

### 4. Bundle Structure Path Changes (3 failures)
**Root Cause:** Tests expecting old `storage/src/` path but bundles now use `code/` path

**Failed Tests:**
- `test_multi_target_app.py::TestMultiTargetApp::test_multi_target_comprehensive_workflow`
- `test_multi_target_pipeline_airless.py::TestMultiTargetApp::test_multi_target_comprehensive_workflow`

**Error Message:**
```
AssertionError: storage/src/test-notebook1.ipynb not found in bundle: ['code/test-notebook1.ipynb', ...]
```

**Fix Required:**
Update test assertions:
```python
# Change from:
assert 'storage/src/test-notebook1.ipynb' in bundle_files

# Change to:
assert 'code/test-notebook1.ipynb' in bundle_files
```

---

### 5. Bundle Validation UTF-8 Errors (2 failures)
**Root Cause:** Bundle ZIP files contain binary data that can't be decoded as UTF-8 YAML

**Failed Tests:**
- `test_bundle_validation.py::TestBundleValidation::test_deploy_command_validation`
- `test_bundle_deploy_pipeline.py::TestBundleDeployPipeline::test_bundle_deploy_workflow`

**Error Message:**
```
Manifest validation failed for /path/to/bundle.zip:
  - YAML syntax error: 'utf-8' codec can't decode byte 0x94 in position 10: invalid start byte
```

**Fix Required:**
The deploy command should not try to parse ZIP files as YAML. Need to extract manifest from ZIP first.

---

### 6. Test Environment Configuration (9 failures)
**Root Cause:** Tests expecting `domain_name` in environment config but it's missing

**Failed Tests:**
- `test_project_validation.py::test_environment_variables_available`
- `test_project_validation.py::test_project_context`
- `test_project_validation.py::test_domain_and_project_ids`
- `test_project_validation_overdrive.py::test_environment_variables_available`
- `test_project_validation_overdrive.py::test_project_context`
- `test_project_validation_overdrive.py::test_domain_and_project_ids`

**Error Message:**
```
AssertionError: domain_name should be in test_environment
KeyError: 'domain_name'
```

**Fix Required:**
Update test environment configuration or fix tests to use correct config structure.

---

### 7. Project Profile Not Found (2 failures)
**Root Cause:** Tests trying to create projects with 'All capabilities' profile which doesn't exist

**Failed Tests:**
- `test_multi_target_app.py::TestMultiTargetApp::test_describe_connect_after_deploy`
- `test_multi_target_pipeline_airless.py::TestMultiTargetApp::test_describe_connect_after_deploy`

**Error Message:**
```
❌ Error: Project profile 'All capabilities' not found
```

**Fix Required:**
Use correct project profile name or make profile name configurable.

---

### 8. Active Workflow Conflicts (1 failure)
**Root Cause:** Workflow already has active runs, cannot update

**Failed Tests:**
- `test_genai_workflow.py::TestGenAIWorkflow::test_genai_workflow_deployment`

**Error Message:**
```
❌ Error creating Overdrive workflows: Cannot update workflow IntegrationTestGenAIWorkflow_test_marketing_genai_dev_workflow: 1 active run(s) in progress
```

**Fix Required:**
Tests should wait for or stop active runs before attempting deployment.

---

### 9. Test File Path Issues (6 failures)
**Root Cause:** Tests referencing wrong directory path `tests/integration/multi_target_pipeline/` instead of `tests/integration/multi_target_bundle/`

**Failed Tests:**
- `test_test_command_integration.py::TestTestCommandIntegration::test_test_command_basic`
- `test_test_command_integration.py::TestTestCommandIntegration::test_test_command_json_output`
- `test_test_command_integration.py::TestTestCommandIntegration::test_test_command_verbose`
- `test_test_command_integration.py::TestTestCommandIntegration::test_test_command_all_targets`
- `test_test_command_integration.py::TestTestCommandIntegration::test_test_files_exist`
- `test_test_command_integration.py::TestTestCommandIntegration::test_actual_test_execution`

**Error Message:**
```
File not found: tests/integration/multi_target_pipeline/multi_target_bundle.yaml
```

**Fix Required:**
Update test file paths from `multi_target_pipeline` to `multi_target_bundle`.

---

### 10. Pipeline Name Assertions (3 failures)
**Root Cause:** Tests asserting old pipeline names instead of new application names

**Failed Tests:**
- `test_create_app.py::TestCreateApp::test_create_pipeline_workflow`
- `test_create_app.py::TestCreateApp::test_describe_only`
- `test_delete_app.py::TestDeleteApp::test_delete_pipeline_workflow`

**Error Message:**
```
AssertionError: Pipeline name not found
assert 'CreateTestPipeline' in 'Pipeline: CreateTestBundle...'
```

**Fix Required:**
Tests need to check for correct application/bundle names in output.

---

### 11. Missing AWS Account/Owner Info (2 failures)
**Root Cause:** Describe command not showing expected AWS account and owner information

**Failed Tests:**
- `test_multi_target_app.py::TestMultiTargetApp::test_describe_without_connect_vs_with_connect`
- `test_multi_target_app.py::TestMultiTargetApp::test_describe_connect_project_details`

**Error Message:**
```
AssertionError: assert 'awsAccountId:' in output
AssertionError: Owners field should be present with --connect
```

**Fix Required:**
Enhance describe command to include AWS account ID and owner information.

---

## Summary by Priority

### P0 - Critical (Blocks Most Tests)
1. **Import path changes** - 6 tests blocked
2. **Manifest schema validation** - 15+ tests blocked
3. **Test file path corrections** - 6 tests blocked

### P1 - High (Blocks Feature Tests)
4. **Notebook download signature** - 4 tests blocked
5. **Bundle structure paths** - 3 tests blocked
6. **Test environment config** - 9 tests blocked

### P2 - Medium (Edge Cases)
7. **Bundle validation UTF-8** - 2 tests blocked
8. **Project profile name** - 2 tests blocked
9. **Pipeline name assertions** - 3 tests blocked

### P3 - Low (Flaky/Timing)
10. **Active workflow conflicts** - 1 test (timing issue)
11. **Missing AWS info in describe** - 2 tests (enhancement)

---

## Recommended Fix Order

1. **Global search/replace:** `smus_cicd.pipeline` → `smus_cicd.application`
2. **Global search/replace in YAML:** `pipelineName:` → `applicationName:`
3. **Fix test directory paths:** `multi_target_pipeline` → `multi_target_bundle`
4. **Update notebook download calls** in 4 test files
5. **Fix bundle path assertions:** `storage/src/` → `code/`
6. **Update test environment configuration** with correct structure
7. **Fix bundle validation** to handle ZIP files properly
8. **Make project profile configurable** or use correct default
9. **Add workflow cleanup** before deployment tests
10. **Enhance describe command** with AWS account/owner info

---

## Tests Passing (29)

- `test_multi_target_bundle_airless.py::TestMultiTargetApp::test_basic_bundle_workflow` ✅
- Connection validation tests ✅
- API validation tests ✅
- Permission tests ✅

# Phase 1 Complete: Helper Functions Added

## Summary
Successfully added shared workflow helper functions to enable code reuse between CLI commands and bootstrap actions.

---

## New Helper Functions

### In `helpers/airflow_serverless.py`:

#### 1. `generate_workflow_name(bundle_name, project_name, dag_name) -> str`
- Standardized workflow name generation
- Replaces hyphens with underscores
- Format: `{bundle}_{project}_{dag}`
- **Eliminates duplication in 4 places**

#### 2. `find_workflow_arn(workflow_name, region, connection_info=None) -> str`
- Find workflow ARN by name
- Lists all workflows and matches by name
- Provides helpful error with available workflows
- **Eliminates duplication in 3 places**

#### 3. `start_workflow_run_verified(workflow_arn, region, ...) -> Dict`
- **CRITICAL**: Includes tested verification logic from `run.py`
- Starts workflow and verifies it actually started
- Waits 10 seconds and re-checks status if needed
- Validates status is STARTING/QUEUED/RUNNING
- Raises exception if workflow didn't actually start
- **This is the key reliability feature missing from WorkflowOperations**

Parameters:
- `workflow_arn`: Workflow ARN
- `region`: AWS region
- `run_name`: Optional run name
- `connection_info`: Optional connection info
- `verify_started`: Whether to verify (default: True)
- `wait_seconds`: Wait time before retry (default: 10)

#### 4. `get_workflow_logs(workflow_arn, run_id, region, max_lines=100) -> List[str]`
- Get formatted workflow logs
- Constructs CloudWatch log group path
- Formats timestamps and log streams
- Returns list of formatted log lines

---

### In `helpers/datazone.py`:

#### 1. `is_connection_serverless_airflow(connection_name, domain_id, project_id, region) -> bool`
- Check if a DataZone connection is serverless Airflow
- **Handles DataZone bug**: Both serverless and MWAA have type WORKFLOWS_MWAA
- Distinguishes by checking physicalEndpoints for MWAA ARN
- No MWAA ARN = serverless, Has MWAA ARN = MWAA

#### 2. `target_uses_serverless_airflow(manifest, target_config) -> bool`
- **CRITICAL**: Includes tested detection logic from `monitor.py`
- Queries DataZone at runtime (not naming conventions)
- Resolves domain and project IDs
- Checks each workflow's connection type
- Returns True if any workflow uses serverless Airflow

---

## Test Coverage

### New Test File: `tests/unit/test_workflow_helpers.py`
- **14 tests, all passing** ✅

**Test Classes:**
1. `TestWorkflowNameGeneration` (3 tests)
   - Basic name generation
   - Hyphen replacement
   - Mixed characters

2. `TestWorkflowArnLookup` (2 tests)
   - Successful lookup
   - Not found error

3. `TestWorkflowStartVerification` (4 tests)
   - Immediate success
   - Retry with verification
   - Verification failure
   - No verification mode

4. `TestWorkflowLogs` (1 test)
   - Log retrieval and formatting

5. `TestDataZoneConnectionDetection` (4 tests)
   - Serverless detection (no MWAA ARN)
   - MWAA detection (has MWAA ARN)
   - Target uses serverless
   - Target with no workflows

### Existing Tests Still Pass
- `test_workflow_bootstrap.py`: 7 tests passing ✅
- **Total: 21 tests passing** ✅

---

## Key Benefits

### 1. Single Source of Truth
- Workflow logic now in helpers
- Both commands and bootstrap actions can use same code
- Fix bugs once, benefits all callers

### 2. Tested Logic Preserved
- `start_workflow_run_verified()` includes 10s wait + status check from `run.py`
- `target_uses_serverless_airflow()` includes DataZone bug workaround from `monitor.py`
- All tested logic now available to bootstrap actions

### 3. No Breaking Changes
- All new functions are additive
- Existing code continues to work
- Can migrate incrementally

### 4. Better Reliability
- Bootstrap actions can now use verification logic
- Prevents false positives (API success but workflow didn't start)
- Proper serverless detection at runtime

---

## Code Duplication Eliminated

### Before:
```
Workflow name generation: 4 places
Workflow ARN lookup: 3 places
Start verification: 1 place (run.py only)
DataZone detection: 1 place (monitor.py only)
```

### After:
```
Workflow name generation: 1 helper function
Workflow ARN lookup: 1 helper function
Start verification: 1 helper function (available to all)
DataZone detection: 2 helper functions (available to all)
```

---

## Next Steps (Phase 2)

### Update WorkflowOperations to use helpers:

```python
# workflows/operations.py - BEFORE
bundle_name = manifest.application_name
project_name = target_config.project.name.replace("-", "_")
safe_pipeline = bundle_name.replace("-", "_")
safe_dag = workflow_name.replace("-", "_")
expected_workflow_name = f"{safe_pipeline}_{project_name}_{safe_dag}"

workflows = airflow_serverless.list_workflows(region=region)
workflow_arn = None
for wf in workflows:
    if wf["name"] == expected_workflow_name:
        workflow_arn = wf["workflow_arn"]
        break

result = airflow_serverless.start_workflow_run(workflow_arn, region=region)
```

```python
# workflows/operations.py - AFTER
from ..helpers import airflow_serverless

workflow_name = airflow_serverless.generate_workflow_name(
    bundle_name=manifest.application_name,
    project_name=target_config.project.name,
    dag_name=workflow_name
)

workflow_arn = airflow_serverless.find_workflow_arn(
    workflow_name=workflow_name,
    region=region
)

result = airflow_serverless.start_workflow_run_verified(
    workflow_arn=workflow_arn,
    region=region,
    verify_started=True  # Now includes verification!
)
```

**Benefits:**
- 15+ lines → 10 lines
- Includes verification logic
- More readable
- Easier to maintain

---

## Files Modified

### Added:
- `tests/unit/test_workflow_helpers.py` (14 tests)

### Modified:
- `src/smus_cicd/helpers/airflow_serverless.py` (+180 lines)
  - Added 4 helper functions
- `src/smus_cicd/helpers/datazone.py` (+110 lines)
  - Added 2 helper functions

### Documentation:
- `CODE_REUSE_COMPARISON.md` - Detailed comparison of CLI vs WorkflowOperations
- `HELPER_REFACTORING_PLAN.md` - Complete refactoring plan
- `PHASE1_COMPLETE.md` - This document

---

## Validation

✅ All 14 new tests pass
✅ All 7 existing bootstrap tests pass
✅ No breaking changes to existing code
✅ Helper functions ready for use
✅ Tested logic preserved and available

---

## Usage Examples

### Generate Workflow Name:
```python
from smus_cicd.helpers import airflow_serverless

name = airflow_serverless.generate_workflow_name(
    bundle_name="my-app",
    project_name="test-project",
    dag_name="etl-pipeline"
)
# Returns: "my_app_test_project_etl_pipeline"
```

### Find Workflow ARN:
```python
arn = airflow_serverless.find_workflow_arn(
    workflow_name="my_app_test_project_etl_pipeline",
    region="us-east-1"
)
# Returns: "arn:aws:airflow-serverless:us-east-1:123:workflow/..."
# Raises exception with available workflows if not found
```

### Start Workflow with Verification:
```python
result = airflow_serverless.start_workflow_run_verified(
    workflow_arn=arn,
    region="us-east-1",
    verify_started=True  # Waits 10s and verifies status
)
# Returns: {"success": True, "run_id": "...", "status": "RUNNING"}
# Raises exception if workflow didn't actually start
```

### Check if Connection is Serverless:
```python
from smus_cicd.helpers import datazone

is_serverless = datazone.is_connection_serverless_airflow(
    connection_name="default.workflow_serverless",
    domain_id="dzd_123",
    project_id="prj_456",
    region="us-east-1"
)
# Returns: True (no MWAA ARN in physicalEndpoints)
```

### Check if Target Uses Serverless:
```python
uses_serverless = datazone.target_uses_serverless_airflow(
    manifest=manifest,
    target_config=target_config
)
# Returns: True if any workflow uses serverless Airflow
```

---

## Ready for Phase 2

Phase 1 is complete and validated. The helper functions are ready to be used by:
1. WorkflowOperations (bootstrap actions)
2. CLI commands (run, monitor, logs, deploy)

Phase 2 will update these consumers to use the new helpers, eliminating all code duplication.

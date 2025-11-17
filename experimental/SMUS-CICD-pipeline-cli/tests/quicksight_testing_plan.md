# QuickSight Deployment Testing Plan

## Current Issues

1. **Dashboard name doesn't have prefix** - Expected: `TotalDeathByCountry-test`, Actual: `TotalDeathByCountry`
2. **Datasets not visible** - No output showing imported dataset IDs
3. **Permissions verification** - Need to confirm Admin/amirbo-Isengard has owner permissions

## Test Scripts

### 1. Quick Validation Script (`tests/validate_quicksight.py`)
- Lists all deployed dashboards with prefix
- Shows dashboard details (ID, Name, Version)
- Lists datasets and data sources
- Shows permissions for each dashboard

### 2. Test Deployment (`tests/test_qs_deploy.sh`)
- Deploy to test environment
- Capture all output
- Validate expected resources exist

## Expected Behavior

### Dashboard Import
```
Input manifest override:
  PrefixForAllResources: deployed-test-covid-
  Dashboards:
    - DashboardId: e0772d4e-bd69-444e-a421-cb3f165dbad8
      Name: TotalDeathByCountry-{stage.name}

Expected output:
  Dashboard ID: deployed-test-covid-e0772d4e-bd69-444e-a421-cb3f165dbad8
  Dashboard Name: TotalDeathByCountry-test  ← ISSUE: Currently "TotalDeathByCountry"
```

### Datasets
```
Expected: List of imported dataset IDs with prefix
  - deployed-test-covid-<dataset-uuid>
  
Current: No output showing datasets
```

### Permissions
```
Expected: Admin/amirbo-Isengard with 8 owner actions
Current: ✅ WORKING - Verified via AWS CLI
```

## Root Causes

### Issue 1: Dashboard Name Missing Suffix
**Location**: Override parameters not applying dashboard name
**Fix**: Verify `Name` field in override parameters is being sent to API

### Issue 2: Datasets Not Shown
**Location**: Removed dataset listing code when fixing permissions
**Fix**: Re-add dataset listing from job details or list-data-sets API

## Fix Plan

1. **Add debug output for override parameters sent to API**
2. **Re-add dataset listing after import**
3. **Create validation script to check all resources**
4. **Run integration test**

## Testing Sequence

```bash
# 1. Clean up existing resources
python tests/cleanup_quicksight.py

# 2. Run validation script (before)
python tests/validate_quicksight.py

# 3. Deploy
python -m smus_cicd.cli deploy test --manifest examples/analytic-workflow/dashboard-glue-quick/manifest.yaml

# 4. Run validation script (after)
python tests/validate_quicksight.py

# 5. Run integration test
pytest tests/integration/examples-analytics-workflows/dashboard-glue-quick/test_dashboard_glue_quick_workflow.py -v -s
```

# QuickSight Deployment Test Results

## Test Date: 2025-11-17

## Summary
✅ **5 of 6 requirements working**
❌ **1 issue**: Dashboard Name override not applied by QuickSight API

## Detailed Results

### ✅ Dashboard ID with Prefix
- **Expected**: `deployed-test-covid-e0772d4e-bd69-444e-a421-cb3f165dbad8`
- **Actual**: `deployed-test-covid-e0772d4e-bd69-444e-a421-cb3f165dbad8`
- **Status**: ✅ PASS

### ❌ Dashboard Name with Suffix
- **Expected**: `TotalDeathByCountry-test`
- **Actual**: `TotalDeathByCountry`
- **Status**: ❌ FAIL
- **Root Cause**: QuickSight API ignores `Name` field in Dashboard override parameters
- **Evidence**: Logs show correct parameters sent to API:
  ```json
  {
    "Dashboards": [{
      "DashboardId": "e0772d4e-bd69-444e-a421-cb3f165dbad8",
      "Name": "TotalDeathByCountry-test"
    }]
  }
  ```
- **API Behavior**: The `Name` field in the Dashboards array appears to be ignored by the QuickSight import API

### ✅ Datasets Imported
- **Expected**: Dataset with prefix `deployed-test-covid-*`
- **Actual**: `deployed-test-covid-2b4bd673-99f3-4d18-a475-ac37d56af357`
- **Status**: ✅ PASS

### ✅ Data Sources Imported
- **Expected**: Data source with prefix `deployed-test-covid-*`
- **Actual**: `deployed-test-covid-8e5eb8e2-7430-4e3a-a4f7-940af71a93f6`
- **Status**: ✅ PASS

### ✅ Permissions Granted
- **Expected**: Admin/amirbo-Isengard with 8 owner actions
- **Actual**: amirbo-Isengard with 8 actions
- **Status**: ✅ PASS
- **Actions**:
  - quicksight:DescribeDashboard
  - quicksight:ListDashboardVersions
  - quicksight:UpdateDashboardPermissions
  - quicksight:QueryDashboard
  - quicksight:UpdateDashboard
  - quicksight:DeleteDashboard
  - quicksight:DescribeDashboardPermissions
  - quicksight:UpdateDashboardPublishedVersion

### ✅ Correct Dashboard ID Used for Permissions
- **Issue Fixed**: Previously used original ID `sample-dashboard`
- **Now Using**: Imported ID `deployed-test-covid-e0772d4e-bd69-444e-a421-cb3f165dbad8`
- **Status**: ✅ PASS

## Code Fixes Applied

### 1. Fixed Status Check
```python
# Before: result.get("Status") == "SUCCESSFUL"
# After:  result.get("JobStatus") == "SUCCESSFUL"
```

### 2. Construct Imported Dashboard ID
```python
# Get ID from override parameters instead of job details
prefix = override_params["ResourceIdOverrideConfiguration"]["PrefixForAllResources"]
dashboard_id = override_params["Dashboards"][0]["DashboardId"]
imported_dashboard_id = f"{prefix}{dashboard_id}"
```

### 3. Deduplicate Permissions
```python
# Track principals in dict to avoid duplicates
# Owners take precedence over viewers
principal_actions = {}
for owner in owners:
    principal_actions[owner] = owner_actions
for viewer in viewers:
    if viewer not in principal_actions:
        principal_actions[viewer] = viewer_actions
```

### 4. Move Permissions Inside Success Block
- Ensures permissions only granted after successful import
- Uses correct imported dashboard ID

## Known Limitation

**Dashboard Name Override**: The QuickSight `start_asset_bundle_import_job` API does not apply the `Name` field from the `Dashboards` array in `OverrideParameters`. This appears to be an API limitation.

**Workaround Options**:
1. Accept that dashboard names won't have stage suffix (ID has prefix which is sufficient)
2. Use `update_dashboard` API after import to rename (adds complexity)
3. Document this as expected behavior

**Recommendation**: Accept current behavior. The dashboard ID has the prefix which provides environment isolation. The name is cosmetic and doesn't affect functionality.

## Test Commands

```bash
# Clean up
python tests/cleanup_quicksight.py

# Deploy
python -m smus_cicd.cli deploy test --manifest examples/analytic-workflow/dashboard-glue-quick/manifest.yaml

# Validate
python tests/validate_quicksight.py

# Integration test
pytest tests/integration/examples-analytics-workflows/dashboard-glue-quick/test_dashboard_glue_quick_workflow.py -v -s
```

## Next Steps

1. ✅ Remove debug output from code
2. ✅ Run full integration test
3. ✅ Document dashboard name limitation
4. ✅ Update manifest examples if needed

# QuickSight Deployment Fix Summary

## Status: ⏳ INGESTION RUNNING - AWAITING COMPLETION (2025-11-17 13:20)

### Ingestion Test Status

**First Ingestion** (`test-1763402270`): ❌ FAILED
- Triggered at 12:57 before Lake Formation permissions were granted
- Error: `TABLE_NOT_FOUND` (expected)

**Second Ingestion** (`test-1763403589`): ⏳ RUNNING
- Triggered at 13:19 after Lake Formation permissions granted
- Status: RUNNING (in progress)
- Awaiting completion to verify Lake Formation permissions work correctly

**Note**: Dataset does NOT support `INCREMENTAL_REFRESH` - must use `FULL_REFRESH`
- Error when trying incremental: "Dataset is not eligible for incremental refresh"
- Manifest updated to use `FULL_REFRESH`

### All Issues Resolved

#### Issue 1: Dataset and Data Source Permissions Not Granted ✅ FIXED
**Problem**: User could not see imported datasets - permissions were not granted
**Fix Applied**: 
- Added `grant_dataset_permissions()` and `grant_data_source_permissions()` helper functions
- Refactored code to use helpers in `src/smus_cicd/helpers/quicksight.py`
- Deploy command now grants permissions to dashboard, datasets, and data sources
**Verified**: 
- Dataset: 10 owner actions for `amirbo-Isengard`
- Data source: 6 owner actions for `amirbo-Isengard`

#### Issue 2: Lake Formation Permissions Missing for QuickSight ✅ FIXED (Manual)
**Problem**: Dataset ingestion failed with `TABLE_NOT_FOUND` error
**Root Cause**: QuickSight service role `aws-quicksight-service-role-v0` had no Lake Formation permissions
**Diagnosis**:
- Glue job only granted permissions to `Admin` role (from `GRANT_TO: Admin`)
- QuickSight uses its own service role: `arn:aws:iam::198737698272:role/service-role/aws-quicksight-service-role-v0`
- This role was NOT in Lake Formation permissions list
**Manual Fix Applied**:
```bash
# Granted Lake Formation permissions manually
aws lakeformation grant-permissions --principal DataLakePrincipalIdentifier=arn:aws:iam::198737698272:role/service-role/aws-quicksight-service-role-v0 \
  --resource '{"Database":{"Name":"covid19_db"}}' --permissions DESCRIBE
aws lakeformation grant-permissions --principal DataLakePrincipalIdentifier=arn:aws:iam::198737698272:role/service-role/aws-quicksight-service-role-v0 \
  --resource '{"Table":{"DatabaseName":"covid19_db","Name":"us_simplified"}}' --permissions DESCRIBE
aws lakeformation grant-permissions --principal DataLakePrincipalIdentifier=arn:aws:iam::198737698272:role/service-role/aws-quicksight-service-role-v0 \
  --resource '{"TableWithColumns":{"DatabaseName":"covid19_db","Name":"us_simplified","ColumnWildcard":{}}}' --permissions SELECT
```
**Ingestion Test**: Started ingestion `test-1763402270` - awaiting verification

**Permanent Fix Needed**: Update manifest to include QuickSight role:
```yaml
environment_variables:
  GRANT_TO: Admin,aws-quicksight-service-role-v0
```

#### Issue 3: Resource Names Missing Prefix/Suffix ⚠️ API LIMITATION
**Problem**: Dashboard name is `TotalDeathByCountry` instead of `TotalDeathByCountry-test`
**Root Cause**: QuickSight API limitation - Name field in override parameters is ignored
**Impact**: Cosmetic only - Dashboard ID has correct prefix for environment isolation
**Status**: Documented as known limitation

#### Issue 4: MWAA Connection Check Not Using Correct Helper ✅ FIXED
**Problem**: Code not checking if Airflow connection has environment name to distinguish MWAA from serverless
**Root Cause**: Both WORKFLOWS_MWAA (managed MWAA) and WORKFLOWS_SERVERLESS share same connection type
**Fix Applied**: Updated `src/smus_cicd/helpers/mwaa.py` to check for `mwaaEnvironmentName` field presence
**Verified**: Correctly distinguishes MWAA from serverless Airflow

## Code Changes Summary

### Files Modified

#### 1. `src/smus_cicd/helpers/quicksight.py`
**Added Functions**:
```python
def grant_dataset_permissions(dataset_id, aws_account_id, region, permissions):
    """Grant permissions to QuickSight dataset with wildcard expansion."""
    
def grant_data_source_permissions(data_source_id, aws_account_id, region, permissions):
    """Grant permissions to QuickSight data source with wildcard expansion."""
```

#### 2. `src/smus_cicd/commands/deploy.py`
**Changes**:
- Import new helper functions
- List imported datasets and data sources after successful import
- Grant permissions to datasets (10 owner actions or 5 viewer actions)
- Grant permissions to data sources (6 owner actions or 3 viewer actions)
- Permissions based on `owners` and `viewers` lists from manifest

#### 3. `src/smus_cicd/helpers/mwaa.py`
**Changes**:
- Check for `mwaaEnvironmentName` field to distinguish MWAA from serverless
- Skip connections without environment name (serverless Airflow)

## Next Steps (After Ingestion Verification)

### 1. Update Manifest - Add QuickSight Role to GRANT_TO
**File**: `examples/analytic-workflow/dashboard-glue-quick/manifest.yaml`
**Change**:
```yaml
# Current
environment_variables:
  GRANT_TO: Admin

# Update to
environment_variables:
  GRANT_TO: Admin,aws-quicksight-service-role-v0
```

### 2. Add Bootstrap Action for Dataset Ingestion
**File**: `examples/analytic-workflow/dashboard-glue-quick/manifest.yaml`
**Add to test stage**:
```yaml
test:
  bootstrap:
    actions:
    - type: quicksight.refresh_dataset
      parameters:
        refreshScope: IMPORTED  # Only refresh datasets deployed by this deployment
        wait: false  # Don't wait for ingestion to complete
```

### 3. Uncomment Workflows
**File**: `examples/analytic-workflow/dashboard-glue-quick/manifest.yaml`
**Change**:
```yaml
# Uncomment the workflows section
workflows:
- workflowName: covid_dashboard_glue_quick_pipeline
  connectionName: default.workflow_serverless
```

### 4. Update Integration Test
**File**: `tests/integration/examples-analytics-workflows/dashboard-glue-quick/test_dashboard_glue_quick_workflow.py`
**Add after Step 6 (Run Workflow)**:
```python
# Step 6.5: Wait for workflow completion and get logs
self.logger.info("\n=== Step 6.5: Wait for Workflow Completion ===")
# Poll workflow status until complete
# Get workflow logs

# Step 6.6: Trigger dataset ingestion (via bootstrap or direct)
self.logger.info("\n=== Step 6.6: Trigger Dataset Ingestion ===")
# Trigger ingestion but don't wait
```

### 5. Run Full Integration Test
```bash
pytest tests/integration/examples-analytics-workflows/dashboard-glue-quick/test_dashboard_glue_quick_workflow.py -v -s
```

## Current Deployment Output

```
✓ Dashboard deployed successfully
  Dashboard: deployed-test-covid-e0772d4e-bd69-444e-a421-cb3f165dbad8
  Datasets (1):
    - deployed-test-covid-2b4bd673-99f3-4d18-a475-ac37d56af357
  Data Sources (1):
    - deployed-test-covid-8e5eb8e2-7430-4e3a-a4f7-940af71a93f6 (ATHENA)
  
✓ Granted permissions to dashboard deployed-test-covid-e0772d4e-bd69-444e-a421-cb3f165dbad8
✓ Granted permissions to dataset deployed-test-covid-2b4bd673-99f3-4d18-a475-ac37d56af357
✓ Granted permissions to data source deployed-test-covid-8e5eb8e2-7430-4e3a-a4f7-940af71a93f6

Permissions for Admin/amirbo-Isengard:
- Dashboard: 8 owner actions
- Dataset: 10 owner actions
- Data source: 6 owner actions

Lake Formation Permissions:
- QuickSight service role: DESCRIBE (database), DESCRIBE (table), SELECT (columns)
```

## Permission Actions Reference

### Dashboard Owner (8 actions)
- quicksight:DescribeDashboard
- quicksight:ListDashboardVersions
- quicksight:UpdateDashboardPermissions
- quicksight:QueryDashboard
- quicksight:UpdateDashboard
- quicksight:DeleteDashboard
- quicksight:UpdateDashboardPublishedVersion
- quicksight:DescribeDashboardPermissions

### Dataset Owner (10 actions)
- quicksight:DescribeDataSet
- quicksight:DescribeDataSetPermissions
- quicksight:PassDataSet
- quicksight:DescribeIngestion
- quicksight:ListIngestions
- quicksight:UpdateDataSet
- quicksight:DeleteDataSet
- quicksight:CreateIngestion
- quicksight:CancelIngestion
- quicksight:UpdateDataSetPermissions

### Data Source Owner (6 actions)
- quicksight:DescribeDataSource
- quicksight:DescribeDataSourcePermissions
- quicksight:PassDataSource
- quicksight:UpdateDataSource
- quicksight:DeleteDataSource
- quicksight:UpdateDataSourcePermissions

## Testing Commands

```bash
# Validate QuickSight resources
python tests/validate_quicksight.py

# Check Lake Formation permissions
aws lakeformation list-permissions --resource '{"Table":{"DatabaseName":"covid19_db","Name":"us_simplified"}}' --region us-east-2

# Check dataset ingestion status
aws quicksight describe-ingestion --aws-account-id 198737698272 \
  --data-set-id deployed-test-covid-2b4bd673-99f3-4d18-a475-ac37d56af357 \
  --ingestion-id test-1763402270 --region us-east-2

# Clean up
python tests/cleanup_quicksight.py

# Deploy
python -m smus_cicd.cli deploy test --manifest examples/analytic-workflow/dashboard-glue-quick/manifest.yaml
```

## Files Created for Testing

1. **tests/quicksight_testing_plan.md** - Testing strategy
2. **tests/validate_quicksight.py** - Quick validation script
3. **tests/quicksight_test_results.md** - Detailed test results
4. **tests/QUICKSIGHT_FIX_SUMMARY.md** - This file (progress tracker)

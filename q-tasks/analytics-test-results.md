# Analytics Workflows Test Results
**Date:** 2025-11-20 17:04
**Duration:** 21m 30s
**Environment:** Account 198737698272, us-east-2

## Summary
- ✅ **2 PASSED**
- ❌ **3 FAILED**

## Test Results

### ✅ PASSED (2/5)

1. **ML Deployment** - PASSED
2. **GenAI Workflow** - PASSED

### ❌ FAILED (3/5)

#### 1. ML Training Workflow
**Error:** Bundle failed - No files found
```
Bundle source: dev target
Bundle destination: dev
Creating bundle for target: dev
Project: dev-marketing
❌ No files found
```

**Root Cause:** Test is trying to bundle from dev target, but we removed connectionName from manifest
**Fix Needed:** Test needs to use direct deployment, not bundling

---

#### 2. Notebooks Workflow  
**Error:** Workflow name mismatch
```
Workflow 'IntegrationTestNotebooks_test_marketing_parallel_notebooks_workflow' not found

Available: IntegrationTestNotebooks_test_notebooks_parallel_notebooks_workflow
```

**Root Cause:** Old workflow with wrong project name existed in Airflow
**Status:** ✅ FIXED - Redeployed, workflow now has correct name
**New Issue:** Workflow runs but fails (separate issue from naming)

---

#### 3. Dashboard Glue QuickSight
**Error:** Dashboard not found after deploy
```
Dashboard with prefix deployed-test-covid- not found after deploy
```

**Root Cause:** Bundle command bug
- Checks `dashboard_config.source == "export"` (old attribute)
- Manifest has `assetBundle: quicksight/sample-dashboard.qs`
- Since `source` doesn't exist, tries to export from QuickSight
- Export fails: Dashboard `sample-dashboard` not found in QuickSight
- Bundle created without QuickSight file
- Deploy can't import (file missing from bundle)

**Fix Needed:** 
- Bundle command should check `assetBundle` attribute
- If `assetBundle` provided → Copy local file to bundle
- If no `assetBundle` → Export from QuickSight service
- See `q-tasks/quicksight-refactor.md` for full refactor plan

## Key Insights

### Direct Deployment Impact
Removing `connectionName` from manifests broke tests that expect bundling:
- ML Training test explicitly bundles from dev
- Dashboard test may need bundle for QuickSight

### Workflow Naming Issues
Project name inconsistency causing workflow lookup failures:
- Notebooks uses `test_notebooks` vs `test_marketing`

### What Worked
- ML Deployment and GenAI workflows passed
- Direct deployment worked for these cases
- Storage/workflow files deployed successfully

## Action Items

1. **ML Training Test** - Update test to use direct deployment instead of bundling
2. **Notebooks Manifest** - Fix project name consistency (test_marketing vs test_notebooks)
3. **Dashboard QuickSight** - Verify bundling requirement, may need to keep connectionName
4. **Test Suite** - Update integration tests to support both deployment modes

## Next Steps

1. Fix notebooks project name in manifest
2. Update ML training test to skip bundle step
3. Verify dashboard-glue-quick needs bundling for QuickSight
4. Re-run tests

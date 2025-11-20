# Direct Deployment Fixes - Progress Tracker

**Started:** 2025-11-20
**Goal:** Fix ML training workflow to use direct branch deployment and improve documentation

## Context
- ML training workflow was bundling from dev environment, getting stale config (sklearn 1.2-1 instead of 1.5-1)
- Root cause: `connectionName` in content.storage triggers bundling from deployed environment
- Solution: Remove connectionName to deploy directly from branch

## Completed ✅

### Code Changes
- [x] ML training manifest - removed connectionName from content.storage
- [x] Created smus-direct-deploy.yml workflow (no bundling)
- [x] Updated analytic-ml-training.yml to use direct deploy workflow
- [x] Dashboard-glue-quick manifest - removed connectionName from storage (keeps bundle for QuickSight)

### Analysis
- [x] Verified deploy.py logic (lines 401-465)
- [x] Identified all manifests with incorrect pattern
- [x] Created comprehensive analysis document (connectionName-analysis.md)
- [x] Confirmed QuickSight requires bundling (deploy.py:1693-1720)

## In Progress 🔄

### Critical Bug Found 🐛
- [x] **workflow.create fails silently** - Returns False when no project role found, but bootstrap executor logs as "Successfully executed"
  - Location: `workflow_create_handler.py:95` returns False
  - Bootstrap executor doesn't propagate failure correctly
  - Result: Workflow never created/updated, Airflow uses cached old version
  
- [ ] **Investigate why project user role not found**
  - `datazone.get_project_user_role_arn()` returns None
  - Project exists and was created outside CICD
  - Need to check if role lookup works for externally created projects

### Documentation
- [ ] Add "Deployment Modes" section to README.md (line ~280)
- [ ] Update all example manifests in README.md to show correct pattern
- [ ] Merge DIRECT-BRANCH-DEPLOYMENT.md content into README.md
- [ ] Add schema comments to application-manifest-schema.yaml

### Remaining Manifest Fixes
- [ ] examples/analytic-workflow/ml/deployment/manifest.yaml
- [ ] examples/analytic-workflow/data-notebooks/manifest.yaml
- [ ] examples/analytic-workflow/genai/manifest.yaml

## Not Started ⏳

### Code Improvements
- [ ] Add validation warning in deploy.py when pattern seems wrong
- [ ] Update schema with better connectionName documentation

### Testing
- [ ] Test ML training workflow with direct deployment
- [ ] Verify sklearn 1.5-1 is deployed correctly
- [ ] Test dashboard-glue-quick mixed mode deployment
- [ ] Verify all other workflows still work

## Test Results Summary

**Ran:** 5 analytics workflow tests in parallel (21m 30s)
**Passed:** 2/5 (ML Deployment, GenAI)
**Failed:** 3/5

### Failed Tests

1. **ML Training** - Test tries to bundle from dev (needs update for direct deployment)
2. **Notebooks** - ✅ FIXED - Old workflow had wrong name, redeployed with correct name
3. **Dashboard QuickSight** - Bundle command bug (checks `source` instead of `assetBundle`)
   - See `q-tasks/quicksight-refactor.md` for full analysis and refactor plan

## Files Modified (Not Committed)
```
M .github/workflows/analytic-ml-training.yml
M .github/workflows/smus-direct-deploy.yml
M experimental/SMUS-CICD-pipeline-cli/examples/analytic-workflow/ml/training/manifest.yaml
M experimental/SMUS-CICD-pipeline-cli/examples/analytic-workflow/dashboard-glue-quick/manifest.yaml
? q-tasks/connectionName-analysis.md
? q-tasks/direct-deployment-fixes.md
```

## Key Findings

### Root Cause: Workflow Not Updated in Airflow
1. ✅ S3 files deployed correctly with sklearn 1.5-1
2. ✅ Direct deployment working (no bundling)
3. ❌ workflow.create bootstrap action fails silently
4. ❌ Airflow still using cached old workflow definition

### Bug Details
**File:** `src/smus_cicd/bootstrap/handlers/workflow_create_handler.py:95`
```python
role_arn = datazone.get_project_user_role_arn(project_name, domain_id, region)
if not role_arn:
    typer.echo("❌ No project user role found")
    return False  # Returns False but bootstrap executor logs success
```

**Log Evidence:**
```
🚀 Creating 1 MWAA Serverless workflow(s)...
❌ No project user role found
Successfully executed: workflow.create  # <-- Should be FAILED
```

**Impact:** 
- Workflow never created/updated in Airflow
- S3 has correct files but Airflow uses cached old DAG
- Tests run with sklearn 1.2-1 instead of 1.5-1

### Questions to Investigate
1. Why does `get_project_user_role_arn()` return None?
2. Does it work for projects created outside CICD?
3. Why doesn't bootstrap executor propagate False return as failure?

## Key Decisions

1. **Direct deployment as default** - Simpler, faster, better for CI/CD
2. **Keep bundle workflow for QuickSight** - Required by implementation
3. **Mixed mode supported** - Some items bundled, some direct
4. **Test apps keep connectionName** - They specifically test bundling

## Next Steps

### Immediate (Unblock Tests)
1. ✅ Fix notebooks project name - DONE (redeployed with correct workflow name)
2. **Fix QuickSight bundle bug** (Phase 1 from quicksight-refactor.md)
   - Update bundle.py line 239: check `assetBundle` instead of `source`
   - Add local file copy logic when `assetBundle` provided
   - Test dashboard-glue-quick workflow
3. **Update ML training test**
   - Remove bundle step (use direct deployment)
   - Or update manifest to keep connectionName for bundling

### Short Term (Documentation)
1. Add "Deployment Modes" section to README.md (line ~280)
2. Fix remaining example manifests:
   - ml/deployment - remove connectionName
   - genai - remove connectionName
3. Update integration tests to support both deployment modes
4. Add validation warning in deploy.py for wrong patterns

### Long Term (QuickSight Refactor)
See `q-tasks/quicksight-refactor.md` Phase 2 for full refactor:
- Align QuickSight with storage pattern (`name` + `type`)
- Move permissions to deployment_configuration
- Add recursive export support
- Update all manifests, tests, and documentation

## References
- Analysis: `q-tasks/connectionName-analysis.md`
- Deploy code: `src/smus_cicd/commands/deploy.py:401-465`
- Direct deploy doc: `DIRECT-BRANCH-DEPLOYMENT.md`

# QuickSight Configuration Refactor

## Current Issues

1. **Bundle command uses wrong attribute** - Checks `source` instead of `assetBundle`
2. **Inconsistent with storage pattern** - Uses `dashboardId` + `assetBundle` instead of `name` + `include`
3. **Permissions in wrong place** - `owners`/`viewers` in content instead of deployment_configuration
4. **No type specification** - Can't distinguish dashboard vs dataset vs analysis

## Proposed Structure

### Content Section (What to bundle/deploy)
```yaml
content:
  quicksight:
  - name: sample-dashboard        # Logical name (like storage)
    type: dashboard               # Asset type: dashboard, dataset, analysis, datasource
    assetBundle: quicksight/local-file.qs  # OPTIONAL: Use local file instead of export
    recursive: true               # OPTIONAL: Export with dependencies
```

### Deployment Configuration (Where/How to deploy)
```yaml
stages:
  test:
    deployment_configuration:
      quicksight:
        items:
        - name: sample-dashboard
          dashboardId: deployed-test-covid-dashboard  # Target dashboard ID
          owners:
          - arn:aws:quicksight:us-east-2:*:user/default/Admin/*
          viewers:
          - arn:aws:quicksight:us-east-2:*:user/default/User/*
        overrideParameters:
          ResourceIdOverrideConfiguration:
            PrefixForAllResources: deployed-{stage.name}-
```

## Bundle Command Behavior

**If `assetBundle` is provided:**
- Copy local file from `assetBundle` path to `quicksight/{name}/` in bundle
- Skip QuickSight export

**If `assetBundle` is NOT provided:**
- Export from QuickSight service using `name` as dashboard ID
- Save to `quicksight/{name}/` in bundle
- If `recursive: true`, export all dependencies (datasets, datasources)

## Deploy Command Behavior

**With bundle:**
- Extract from `quicksight/{name}/` in bundle.zip
- Import to QuickSight
- Apply permissions from `deployment_configuration.quicksight.items[].owners/viewers`
- Apply overrides from `deployment_configuration.quicksight.overrideParameters`

**Without bundle (direct deployment):**
- If `assetBundle` provided: Use local file
- If no `assetBundle`: Skip (can't export during deploy)
- Apply permissions and overrides

## Changes Required

### 1. Schema Updates
- [ ] Add `name` field (required)
- [ ] Add `type` field (dashboard, dataset, analysis, datasource)
- [ ] Make `assetBundle` optional (for local files)
- [ ] Add `recursive` flag (optional, default false)
- [ ] Remove `dashboardId` from content
- [ ] Move `owners`/`viewers` to deployment_configuration

### 2. Bundle Command (`bundle.py`)
- [ ] Change from `dashboard_config.source` to `dashboard_config.assetBundle`
- [ ] If `assetBundle` exists: Copy local file to bundle
- [ ] If no `assetBundle`: Export from QuickSight using `name`
- [ ] Support `recursive` flag for dependency export
- [ ] Save to `quicksight/{name}/` directory structure

### 3. Deploy Command (`deploy.py`)
- [ ] Look in `quicksight/{name}/` instead of using `assetBundle` path
- [ ] Get permissions from `deployment_configuration.quicksight.items[]`
- [ ] Match by `name` between content and deployment_configuration
- [ ] Support direct deployment with local `assetBundle` files

### 4. Documentation
- [ ] Update manifest examples
- [ ] Document bundle vs direct deployment
- [ ] Explain recursive export
- [ ] Show permission configuration

## Migration Path

**Old format:**
```yaml
content:
  quicksight:
  - dashboardId: sample-dashboard
    assetBundle: quicksight/sample-dashboard.qs
    owners: [...]
    viewers: [...]
```

**New format:**
```yaml
content:
  quicksight:
  - name: sample-dashboard
    type: dashboard
    assetBundle: quicksight/sample-dashboard.qs  # Optional

stages:
  test:
    deployment_configuration:
      quicksight:
        items:
        - name: sample-dashboard
          dashboardId: deployed-test-covid-dashboard
          owners: [...]
          viewers: [...]
```

## Dashboard Test Case Fix

For `dashboard-glue-quick` test:
1. Remove `assetBundle` from content (want to export from dev)
2. Bundle command will export from dev-marketing QuickSight
3. Deploy will import to test-marketing QuickSight
4. Permissions configured in deployment_configuration

## Benefits

1. **Consistent with storage** - Same `name` + `include` pattern
2. **Flexible bundling** - Local files OR QuickSight export
3. **Proper separation** - Content (what) vs deployment (where/how)
4. **Type safety** - Can handle different QuickSight asset types
5. **Recursive export** - Bundle dashboard with dependencies

## Implementation Priority

### Phase 1 - Quick Fix (Unblock Tests)
**Goal:** Fix bundle command to work with current manifest structure

- [ ] Update `bundle.py` line 239: Change `dashboard_config.source` to `getattr(dashboard_config, 'assetBundle', 'export')`
- [ ] If `assetBundle != 'export'`: Copy local file to bundle at `quicksight/{name}/`
- [ ] If `assetBundle == 'export'`: Export from QuickSight service
- [ ] Test dashboard-glue-quick workflow
- [ ] Verify bundle contains QuickSight file
- [ ] Verify deploy imports successfully

**Files to modify:**
- `src/smus_cicd/commands/bundle.py` (1 line change + add local file copy logic)

**Test cases to update:**
- None (works with existing manifests)

---

### Phase 2 - Schema Refactor (Breaking Change)
**Goal:** Align QuickSight with storage pattern, separate content from deployment config

#### 2.1 Schema Changes
- [ ] Update `application-manifest-schema.yaml`:
  - Add `name` field (required)
  - Add `type` field (dashboard, dataset, analysis, datasource)
  - Keep `assetBundle` optional
  - Add `recursive` flag (optional)
  - Remove `dashboardId` from content
  - Remove `owners`/`viewers` from content
- [ ] Update `application_manifest.py` dataclasses
- [ ] Add `deployment_configuration.quicksight` schema
- [ ] Add migration guide in CHANGELOG.md

#### 2.2 Bundle Command Updates
- [ ] Use `name` instead of `dashboardId` for QuickSight export
- [ ] Support `recursive` flag for dependency export
- [ ] Create `quicksight/{name}/` directory structure in bundle
- [ ] Handle multiple asset types (dashboard, dataset, etc)

#### 2.3 Deploy Command Updates
- [ ] Look in `quicksight/{name}/` directory in bundle
- [ ] Match content items with deployment_configuration by `name`
- [ ] Get permissions from `deployment_configuration.quicksight.items[]`
- [ ] Apply `dashboardId` override from deployment_configuration
- [ ] Support direct deployment with local `assetBundle` files

#### 2.4 Update All Manifests
- [ ] `examples/analytic-workflow/dashboard-glue-quick/manifest.yaml`
- [ ] Any other examples using QuickSight
- [ ] Test manifests in `tests/integration/`

#### 2.5 Update Tests
- [ ] `tests/integration/examples-analytics-workflows/dashboard-glue-quick/test_dashboard_glue_quick_workflow.py`
  - Update to expect new manifest structure
  - Verify bundle exports from QuickSight
  - Verify deploy applies permissions correctly
- [ ] Add unit tests for new QuickSight logic
- [ ] Add integration test for recursive export

#### 2.6 Documentation
- [ ] Update README.md with new QuickSight structure
- [ ] Add examples showing:
  - Local file bundling (`assetBundle: path`)
  - QuickSight export (no `assetBundle`)
  - Recursive export (`recursive: true`)
  - Permission configuration in deployment_configuration
- [ ] Update DIRECT-BRANCH-DEPLOYMENT.md
- [ ] Add migration guide for existing manifests
- [ ] Document asset types (dashboard, dataset, analysis, datasource)

---

### Phase 3 - Advanced Features (Future)
- [ ] Support multiple QuickSight asset types
- [ ] Implement recursive dependency export
- [ ] Add validation for QuickSight asset existence
- [ ] Support QuickSight themes and templates
- [ ] Add dry-run mode for bundle/deploy

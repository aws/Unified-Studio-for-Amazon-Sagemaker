# connectionName Usage Analysis & Documentation Improvements

## Current State Analysis

### Code Behavior (from deploy.py lines 400-470)

The deploy command determines deployment method based on `connectionName` presence:

```python
# Line 401-408: Check if bundle is needed
has_bundle_items = any(
    s.connectionName
    for s in (
        manifest.content.storage
        if manifest.content and manifest.content.storage
        else []
    )
)

# Line 447-465: Deployment decision logic
for storage_config in storage_configs:
    content_item = content_map.get(storage_config.name)
    
    # Deploy from local filesystem if:
    # 1. content_item exists
    # 2. content_item has NO connectionName
    # 3. manifest_dir is available
    if content_item and not content_item.connectionName and manifest_dir:
        result = _deploy_local_storage_item(...)
    
    # Deploy from bundle if:
    # 1. bundle_path exists (created when has_bundle_items=True)
    elif bundle_path:
        result = _deploy_storage_item(...)
```

**Key Finding:** `connectionName` in `content.storage` controls whether bundling happens, NOT where files are deployed.

### Correct Pattern

```yaml
content:
  storage:
  - name: training-code
    # NO connectionName here = deploy from local filesystem
    include:
    - ml/training/code
  
  workflows:
  - workflowName: ml_training_workflow
    connectionName: default.workflow_serverless  # Required for workflows

stages:
  test:
    deployment_configuration:
      storage:
      - name: training-code
        connectionName: default.s3_shared  # Required - specifies target S3
        targetDirectory: ml/bundle/training-code
```

## Issues Found

### 1. Inconsistent Examples

**Files with INCORRECT pattern (connectionName in content.storage):**
- ✅ `examples/analytic-workflow/ml/training/manifest.yaml` - FIXED
- ✅ `examples/analytic-workflow/dashboard-glue-quick/manifest.yaml` - FIXED (but keeps bundle workflow for QuickSight)
- ❌ `examples/analytic-workflow/ml/deployment/manifest.yaml` - HAS connectionName
- ❌ `examples/analytic-workflow/data-notebooks/manifest.yaml` - HAS connectionName
- ❌ `examples/analytic-workflow/genai/manifest.yaml` - HAS connectionName
- ❌ `tests/integration/basic_app/manifest.yaml` - HAS connectionName (OK - tests bundling)
- ❌ `tests/integration/multi_target_app/manifest.yaml` - HAS connectionName (OK - tests bundling)

**Special Case: dashboard-glue-quick**
- Removed connectionName from storage items
- Keeps bundle workflow because QuickSight dashboards MUST be bundled
- QuickSight deploy code extracts `.qs` files from bundle zip (deploy.py:1693-1720)
- Storage/workflows can deploy directly, but QuickSight needs bundle

### 2. Documentation Issues

**README.md (lines 289-453):**
- All 4 example manifests show `connectionName` in content.storage
- No explanation of when to include/exclude connectionName
- No mention of direct branch deployment vs bundle deployment

**DIRECT-BRANCH-DEPLOYMENT.md:**
- ✅ Correctly explains the pattern
- ✅ Shows correct example
- ❌ But it's a separate doc - users won't find it easily
- ❌ Doesn't explain WHY you'd choose one over the other

### 3. Missing Guidance

No documentation explains:
1. **When to use connectionName in content.storage:**
   - Use when deploying from pre-existing S3 bundles
   - Use in multi-stage workflows (dev → bundle → test)
   
2. **When to omit connectionName in content.storage:**
   - Use for direct branch deployment (CI/CD from git)
   - Use for local development/testing
   - Simpler, faster workflow

3. **deployment_configuration is ALWAYS required:**
   - Specifies WHERE files go in target environment
   - Always needs connectionName regardless of source

## Recommended Fixes

### Priority 1: Fix All Example Manifests

Update these files to remove `connectionName` from content.storage:
- `examples/analytic-workflow/ml/deployment/manifest.yaml`
- `examples/analytic-workflow/data-notebooks/manifest.yaml`
- `examples/analytic-workflow/genai/manifest.yaml`

Keep connectionName in test apps (they test bundling):
- `tests/integration/basic_app/manifest.yaml`
- `tests/integration/multi_target_app/manifest.yaml`

**Special handling:**
- `dashboard-glue-quick` - Remove connectionName from storage BUT keep bundle workflow
  - Reason: QuickSight dashboards require bundling (extracted from zip)
  - Storage/workflows can deploy directly, QuickSight needs bundle

### Priority 2: Update README.md

Add new section after line 280:

```markdown
## Deployment Modes

### Direct Branch Deployment (Recommended for CI/CD)

Deploy directly from your git branch without bundling:

```yaml
content:
  storage:
  - name: my-code
    # NO connectionName = deploy from local filesystem
    include:
    - src/
```

**Benefits:**
- Faster deployments
- Simpler workflow
- Always uses latest code from branch

### Bundle-Based Deployment

Deploy from pre-created S3 bundles:

```yaml
content:
  storage:
  - name: my-code
    connectionName: default.s3_shared  # Deploy from S3 bundle
    include:
    - src/
```

**Use when:**
- Multi-stage promotion (dev → test → prod)
- Need to deploy same artifact to multiple environments
- Deploying from external S3 location

### Important: deployment_configuration Always Required

Regardless of source, you must specify target location:

```yaml
stages:
  test:
    deployment_configuration:
      storage:
      - name: my-code
        connectionName: default.s3_shared  # Always required
        targetDirectory: my-app/code
```
```

### Priority 3: Add Validation Warning

In `deploy.py`, add warning when pattern seems wrong:

```python
# After line 408
if has_bundle_items and not bundle_file:
    typer.echo("⚠️  WARNING: content.storage has connectionName but no bundle provided")
    typer.echo("    This will create a bundle from local files first.")
    typer.echo("    For direct deployment, remove connectionName from content.storage")
```

### Priority 4: Schema Documentation

Update `application-manifest-schema.yaml` to add comments:

```yaml
StorageConfig:
  properties:
    connectionName:
      type: string
      description: |
        OPTIONAL: S3 connection for bundle-based deployment.
        - Include: Deploy from pre-existing S3 bundle (requires bundle step)
        - Omit: Deploy directly from local filesystem (recommended for CI/CD)
        Note: deployment_configuration.storage.connectionName is always required
```

## Testing Checklist

- [ ] Fix ml/deployment manifest
- [ ] Fix data-notebooks manifest  
- [ ] Fix dashboard-glue-quick manifest
- [ ] Fix genai manifest
- [ ] Update README.md with deployment modes section
- [ ] Add validation warning in deploy.py
- [ ] Update schema documentation
- [ ] Test direct deployment still works
- [ ] Test bundle deployment still works
- [ ] Verify all GitHub workflows use correct pattern

## Summary

**Root Cause:** Documentation and examples show bundle-based pattern (with connectionName) as the default, when direct deployment (without connectionName) is simpler and more appropriate for most CI/CD use cases.

**Impact:** Users (including us) get confused about when/where to use connectionName, leading to:
- Unnecessary bundling steps
- Stale configuration issues (bundling from wrong source)
- More complex workflows than needed

**Solution:** Make direct deployment the documented default, clearly explain both modes, and fix all examples to use the simpler pattern.

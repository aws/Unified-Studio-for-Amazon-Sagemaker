# QuickSight Configuration Migration

## Summary
Moved `overrideParameters` and `permissions` from content-level to stage-level `deployment_configuration.quicksight`.

---

## Changes Made

### 1. Manifest Structure Change

**OLD (DEPRECATED):**
```yaml
content:
  quicksight:
    - dashboardId: sample-dashboard
      assetBundle: quicksight/sample-dashboard.qs
      overrideParameters:  # ❌ DEPRECATED
        ResourceIdOverrideConfiguration:
          PrefixForAllResources: deployed-{proj.name}-
      permissions:  # ❌ DEPRECATED
        - principal: arn:aws:quicksight:us-east-1:123:user/default/admin
          actions:
            - quicksight:DescribeDashboard
```

**NEW (CORRECT):**
```yaml
content:
  quicksight:
    - dashboardId: sample-dashboard
      assetBundle: quicksight/sample-dashboard.qs
      # Only dashboardId and assetBundle in content

stages:
  dev:
    deployment_configuration:
      quicksight:  # ✅ NEW LOCATION
        overrideParameters:
          ResourceIdOverrideConfiguration:
            PrefixForAllResources: deployed-{proj.name}-
        permissions:
          - principal: arn:aws:quicksight:us-east-1:123:user/default/admin
            actions:
              - quicksight:DescribeDashboard
```

---

## Rationale

**Why this change?**
1. **Stage-specific configuration**: Override parameters and permissions are deployment-specific, not content-specific
2. **Consistency**: Matches pattern of `deployment_configuration.storage`, `deployment_configuration.git`
3. **Flexibility**: Different stages can have different permissions and overrides
4. **Separation of concerns**: Content defines WHAT to deploy, deployment_configuration defines HOW to deploy it

---

## Files Modified

### Code:
1. `src/smus_cicd/commands/deploy.py`
   - Read `overrideParameters` from `deployment_configuration.quicksight`
   - Read `permissions` from `deployment_configuration.quicksight`
   - Backward compatibility: Falls back to old location if new location not found

2. `src/smus_cicd/application/application-manifest-schema.yaml`
   - Removed `overrideParameters` and `permissions` from content.quicksight
   - Added `deployment_configuration.quicksight` with `overrideParameters` and `permissions`
   - Marked old stage-level `quicksight` as DEPRECATED

### Examples:
1. `examples/analytic-workflow/dashboard-glue-quick/manifest.yaml`
   - Moved `overrideParameters` and `permissions` to `deployment_configuration.quicksight`
   - Applied to both `dev` and `test` stages

2. `examples/quicksight-bootstrap-example.yaml`
   - Updated to show correct structure

### Documentation:
- `QUICKSIGHT_CONFIG_MIGRATION.md` (this file)
- **TODO**: Update `docs/quicksight-deployment.md`
- **TODO**: Update `docs/manifest-schema.md`

---

## Migration Guide

### For Existing Manifests:

**Step 1**: Identify QuickSight configuration in content
```yaml
content:
  quicksight:
    - dashboardId: my-dashboard
      overrideParameters: {...}  # Find this
      permissions: [...]  # Find this
```

**Step 2**: Move to deployment_configuration in each stage
```yaml
stages:
  dev:
    deployment_configuration:
      quicksight:
        overrideParameters: {...}  # Move here
        permissions: [...]  # Move here
```

**Step 3**: Keep only dashboardId and assetBundle in content
```yaml
content:
  quicksight:
    - dashboardId: my-dashboard
      assetBundle: quicksight/my-dashboard.qs
```

---

## Backward Compatibility

The code maintains backward compatibility:
- If `deployment_configuration.quicksight` exists, use it
- Otherwise, fall back to old `target_config.quicksight` location
- No breaking changes for existing manifests (but they should migrate)

---

## Testing

**Integration Test**: `examples/analytic-workflow/dashboard-glue-quick/`
- Uses new structure with `deployment_configuration.quicksight`
- Tests both `dev` and `test` stages
- Verifies override parameters work correctly

---

## Benefits

1. ✅ **Stage-specific configuration**: Each stage can have different permissions
2. ✅ **Cleaner separation**: Content vs deployment configuration
3. ✅ **Consistency**: Matches existing patterns
4. ✅ **Flexibility**: Easier to manage multi-stage deployments
5. ✅ **Maintainability**: Clearer structure for future enhancements

---

## Example: Multi-Stage Configuration

```yaml
content:
  quicksight:
    - dashboardId: sales-dashboard
      assetBundle: quicksight/sales-dashboard.qs

stages:
  dev:
    deployment_configuration:
      quicksight:
        overrideParameters:
          ResourceIdOverrideConfiguration:
            PrefixForAllResources: dev-
        permissions:
          - principal: arn:aws:quicksight:us-east-1:123:user/default/dev-team
            actions: [quicksight:DescribeDashboard]
  
  prod:
    deployment_configuration:
      quicksight:
        overrideParameters:
          ResourceIdOverrideConfiguration:
            PrefixForAllResources: prod-
        permissions:
          - principal: arn:aws:quicksight:us-east-1:123:user/default/prod-team
            actions: [quicksight:DescribeDashboard, quicksight:QueryDashboard]
```

Different prefixes and permissions per stage!

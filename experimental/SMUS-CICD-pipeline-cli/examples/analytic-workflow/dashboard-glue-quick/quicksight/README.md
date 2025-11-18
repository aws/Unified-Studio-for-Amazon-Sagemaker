# QuickSight Dashboard Test Setup

This directory contains a sample QuickSight dashboard bundle for integration testing.

## Files

- **`sample-dashboard.qs`** - Exported QuickSight dashboard bundle (stored in git)
- **`setup_test_dashboard.py`** - Script to import dashboard before testing

## Test Strategy

The integration test uses dashboard name prefixes to avoid conflicts:

1. **Setup**: Import `sample-dashboard.qs` as `test-covid-dashboard` in us-east-2 (dev)
2. **Bundle**: Export `test-covid-dashboard` → bundled as `bundled-test-covid-dashboard`
3. **Deploy**: Import from bundle as `deployed-test-covid-dashboard` in us-east-1 (test)

This ensures:
- Original dashboard (`test-covid-dashboard`) remains unchanged
- Bundle/deploy cycle uses different IDs to avoid conflicts
- Test can be run multiple times without cleanup

## Usage

### 1. Setup Test Dashboard

```bash
cd examples/analytic-workflow/dashboard-glue-quick/quicksight
python setup_test_dashboard.py
```

This imports the dashboard to dev environment (us-east-2) as `test-covid-dashboard`.

### 2. Run Bundle Command

```bash
smus-cli bundle --targets dev --manifest-file examples/analytic-workflow/dashboard-glue-quick/manifest.yaml
```

This exports `test-covid-dashboard` and includes it in the bundle as `bundled-test-covid-dashboard`.

### 3. Run Deploy Command

```bash
smus-cli deploy --targets test --manifest-file examples/analytic-workflow/dashboard-glue-quick/manifest.yaml
```

This imports the dashboard from the bundle to test environment (us-east-1) as `deployed-test-covid-dashboard`.

## Dashboard Details

- **Original Dashboard**: `TotalDeathByCountry` (ID: `e0772d4e-bd69-444e-a421-cb3f165dbad8`)
- **Exported**: 2025-11-16 with `IncludeAllDependencies=True`
- **Size**: 3,972 bytes (includes datasets and data sources)
- **Region**: us-east-2
- **Format**: QUICKSIGHT_JSON (binary compressed)

## Cleanup

To clean up test dashboards:

```bash
# Delete test dashboard in dev (us-east-2)
aws quicksight delete-dashboard \
  --aws-account-id 123456789012 \
  --dashboard-id test-covid-dashboard \
  --region us-east-2

# Delete deployed dashboard in test (us-east-1)
aws quicksight delete-dashboard \
  --aws-account-id 123456789012 \
  --dashboard-id deployed-test-covid-dashboard \
  --region us-east-1
```

## Notes

- The manifest references `bundled-test-covid-dashboard` which will be created during bundle
- Permissions are granted to user `amirbo` - update in manifest for your user
- Dashboard bundle format is QuickSight Asset Bundle (QUICKSIGHT_JSON)

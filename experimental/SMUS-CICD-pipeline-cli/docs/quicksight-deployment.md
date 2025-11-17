# QuickSight Dashboard Deployment

Deploy Amazon QuickSight dashboards across environments using the SMUS CI/CD pipeline.

## Overview

The QuickSight deployment feature enables you to:
- Export dashboards from one environment (e.g., dev)
- Bundle dashboards with your application code
- Deploy dashboards to multiple environments (test, prod)
- Override parameters per environment (datasets, data sources)
- Manage dashboard permissions automatically

## Configuration

### Manifest Structure

QuickSight dashboards can be configured in two locations:

1. **Global dashboards** (`content.quicksight`) - deployed to all stages
2. **Stage-specific dashboards** (`stages.<stage>.quicksight`) - deployed only to that stage

```yaml
applicationName: my-analytics-app

content:
  quicksight:
    - dashboardId: sales-dashboard
      source: export
      overrideParameters:
        DataSetArn: "arn:aws:quicksight:us-east-1:123456789012:dataset/prod-sales-data"
      permissions:
        - principal: "arn:aws:quicksight:us-east-1:123456789012:user/default/admin"
          actions:
            - "quicksight:DescribeDashboard"
            - "quicksight:ListDashboardVersions"
            - "quicksight:QueryDashboard"

stages:
  prod:
    project:
      name: prod-analytics
    domain:
      region: us-east-1
    quicksight:
      - dashboardId: prod-metrics-dashboard
        source: s3://my-bucket/dashboards/metrics.qs
        permissions:
          - principal: "arn:aws:quicksight:us-east-1:123456789012:group/default/analysts"
            actions:
              - "quicksight:DescribeDashboard"
              - "quicksight:QueryDashboard"
```

## Dashboard Configuration Fields

### Required Fields

- **dashboardId** (string): QuickSight dashboard ID

### Optional Fields

- **source** (string): Dashboard bundle source
  - `export` - Export from dev environment during bundle creation
  - `s3://bucket/path/file.qs` - Use existing bundle file
  - Default: `export`

- **overrideParameters** (object): Parameters to override during import
  - Common overrides: `DataSetArn`, `DataSourceArn`, `ThemeArn`
  - Format: Key-value pairs matching QuickSight asset bundle parameters

- **permissions** (array): Dashboard permissions to grant after deployment
  - **principal** (string): ARN of user or group
  - **actions** (array): QuickSight permission actions

## Workflow

### 1. Bundle Phase

When running `smus-cli bundle`, dashboards with `source: export` are exported:

```bash
smus-cli bundle --targets dev
```

**What happens:**
1. Connects to QuickSight in dev environment
2. Exports dashboard as asset bundle
3. Downloads bundle to `quicksight/{dashboardId}.qs` in bundle zip
4. Bundle is ready for deployment

### 2. Deploy Phase

When running `smus-cli deploy`, dashboards are imported:

```bash
smus-cli deploy --targets prod
```

**What happens:**
1. Extracts dashboard bundle from zip
2. Imports dashboard to target environment
3. Applies override parameters (datasets, data sources)
4. Grants permissions to specified principals
5. Dashboard is live in target environment

## Use Cases

### Use Case 1: Promote Dashboard from Dev to Prod

**Scenario:** You have a dashboard in dev that you want to deploy to prod with different datasets.

```yaml
content:
  quicksight:
    - dashboardId: sales-dashboard
      source: export
      overrideParameters:
        DataSetArn: "arn:aws:quicksight:us-east-1:123456789012:dataset/${stage}-sales-data"
```

**Steps:**
1. Create dashboard in dev environment
2. Add to manifest with `source: export`
3. Run `smus-cli bundle --targets dev`
4. Run `smus-cli deploy --targets prod`

### Use Case 2: Deploy Pre-Built Dashboard

**Scenario:** You have a dashboard bundle stored in S3 that you want to deploy.

```yaml
stages:
  prod:
    quicksight:
      - dashboardId: metrics-dashboard
        source: s3://my-dashboards/metrics-v1.qs
        permissions:
          - principal: "arn:aws:quicksight:us-east-1:123456789012:group/default/viewers"
            actions: ["quicksight:DescribeDashboard", "quicksight:QueryDashboard"]
```

### Use Case 3: Environment-Specific Dashboards

**Scenario:** Different dashboards for different environments.

```yaml
stages:
  dev:
    quicksight:
      - dashboardId: dev-debug-dashboard
        source: export
  
  prod:
    quicksight:
      - dashboardId: prod-executive-dashboard
        source: export
        permissions:
          - principal: "arn:aws:quicksight:us-east-1:123456789012:group/default/executives"
            actions: ["quicksight:DescribeDashboard", "quicksight:QueryDashboard"]
```

## Override Parameters

Override parameters allow you to customize dashboards per environment. Common parameters:

### Dataset ARN
```yaml
overrideParameters:
  DataSetArn: "arn:aws:quicksight:us-east-1:123456789012:dataset/prod-dataset"
```

### Data Source ARN
```yaml
overrideParameters:
  DataSourceArn: "arn:aws:quicksight:us-east-1:123456789012:datasource/prod-source"
```

### Theme ARN
```yaml
overrideParameters:
  ThemeArn: "arn:aws:quicksight:us-east-1:123456789012:theme/corporate-theme"
```

### Multiple Parameters
```yaml
overrideParameters:
  DataSetArn: "arn:aws:quicksight:us-east-1:123456789012:dataset/prod-sales"
  DataSourceArn: "arn:aws:quicksight:us-east-1:123456789012:datasource/prod-db"
  ThemeArn: "arn:aws:quicksight:us-east-1:123456789012:theme/dark-mode"
```

## Permissions

Grant dashboard access to users and groups after deployment.

### Permission Actions

Common QuickSight dashboard actions:
- `quicksight:DescribeDashboard` - View dashboard metadata
- `quicksight:ListDashboardVersions` - List dashboard versions
- `quicksight:QueryDashboard` - View dashboard data
- `quicksight:UpdateDashboard` - Modify dashboard
- `quicksight:DeleteDashboard` - Delete dashboard
- `quicksight:UpdateDashboardPermissions` - Manage permissions

### User Permissions
```yaml
permissions:
  - principal: "arn:aws:quicksight:us-east-1:123456789012:user/default/john.doe"
    actions:
      - "quicksight:DescribeDashboard"
      - "quicksight:QueryDashboard"
```

### Group Permissions
```yaml
permissions:
  - principal: "arn:aws:quicksight:us-east-1:123456789012:group/default/analysts"
    actions:
      - "quicksight:DescribeDashboard"
      - "quicksight:QueryDashboard"
```

### Multiple Principals
```yaml
permissions:
  - principal: "arn:aws:quicksight:us-east-1:123456789012:group/default/viewers"
    actions: ["quicksight:DescribeDashboard", "quicksight:QueryDashboard"]
  - principal: "arn:aws:quicksight:us-east-1:123456789012:group/default/editors"
    actions: ["quicksight:DescribeDashboard", "quicksight:QueryDashboard", "quicksight:UpdateDashboard"]
```

## Troubleshooting

### Dashboard Export Fails

**Error:** `Failed to start export: AccessDeniedException`

**Solution:** Ensure AWS account ID is configured in `~/.smus/config.yaml`:
```yaml
aws:
  account_id: "123456789012"
  region: us-east-1
```

### Dashboard Import Fails

**Error:** `Import failed: ResourceNotFoundException`

**Solution:** Verify dashboard bundle exists in bundle zip or S3 location.

### Permission Grant Fails

**Error:** `Failed to grant permissions: InvalidParameterValueException`

**Solution:** Verify principal ARN format:
- User: `arn:aws:quicksight:REGION:ACCOUNT:user/default/USERNAME`
- Group: `arn:aws:quicksight:REGION:ACCOUNT:group/default/GROUPNAME`

### Override Parameters Not Applied

**Error:** Dashboard deployed but using wrong dataset

**Solution:** Check parameter names match QuickSight asset bundle format. Use exact ARN format.

### Export Timeout

**Error:** `Export timed out after 300s`

**Solution:** Large dashboards may take longer. The timeout is currently fixed at 5 minutes. Consider:
- Simplifying dashboard complexity
- Reducing number of visuals
- Optimizing dataset queries

## Best Practices

1. **Use `source: export` for dev dashboards** - Ensures latest version is bundled
2. **Override datasets per environment** - Keep dashboard logic same, swap data sources
3. **Grant minimal permissions** - Only give users the actions they need
4. **Test in dev first** - Validate dashboard works before promoting to prod
5. **Version dashboard bundles** - Store bundles in S3 with version tags
6. **Document override parameters** - Comment what each parameter does in manifest

## IAM Permissions Required

The AWS credentials used must have these QuickSight permissions:

### For Bundle (Export)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "quicksight:StartAssetBundleExportJob",
        "quicksight:DescribeAssetBundleExportJob"
      ],
      "Resource": "*"
    }
  ]
}
```

### For Deploy (Import)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "quicksight:StartAssetBundleImportJob",
        "quicksight:DescribeAssetBundleImportJob",
        "quicksight:UpdateDashboardPermissions"
      ],
      "Resource": "*"
    }
  ]
}
```

## Examples

See `examples/analytic-workflow/etl/manifest.yaml` for a complete example with QuickSight deployment.

## Related Documentation

- [Manifest Schema](manifest-schema.md) - Complete manifest reference
- [Event Initialization](event-bootstrap.md) - Trigger events on deployment
- [CLI Commands](cli-commands.md) - Bundle and deploy command reference

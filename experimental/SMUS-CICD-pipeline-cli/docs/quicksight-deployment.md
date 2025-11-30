# QuickSight Dashboard Deployment

← [Back to Main README](../README.md)


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

QuickSight dashboards are configured in two places:

1. **Content** (`content.quicksight`) - Defines WHAT dashboards to deploy
2. **Deployment Configuration** (`stages.<stage>.deployment_configuration.quicksight`) - Defines HOW to deploy them (overrides, permissions)

```yaml
applicationName: my-analytics-app

content:
  quicksight:
    - dashboardId: sales-dashboard
      assetBundle: export  # or quicksight/sales-dashboard.qs

stages:
  dev:
    domain:
      region: us-east-2
    project:
      name: dev-analytics
    deployment_configuration:
      quicksight:
        overrideParameters:
          ResourceIdOverrideConfiguration:
            PrefixForAllResources: dev-
        permissions:
          - principal: "arn:aws:quicksight:${DEV_DOMAIN_REGION:us-east-2}:*:user/default/admin"
            actions:
              - "quicksight:DescribeDashboard"
              - "quicksight:QueryDashboard"
  
  prod:
    domain:
      region: us-east-1
    project:
      name: prod-analytics
    deployment_configuration:
      quicksight:
        overrideParameters:
          ResourceIdOverrideConfiguration:
            PrefixForAllResources: prod-
        permissions:
          - principal: "arn:aws:quicksight:us-east-1:*:group/default/analysts"
            actions:
              - "quicksight:DescribeDashboard"
              - "quicksight:QueryDashboard"
```

## Dashboard Configuration Fields

### Content Level (content.quicksight)

- **dashboardId** (string, required): QuickSight dashboard ID
- **source** (string, optional): Dashboard bundle source
  - `export` - Export from dev environment during bundle creation (default)
  - `quicksight/dashboard.qs` - Path in bundle zip

### Deployment Configuration Level (deployment_configuration.quicksight)

- **overrideParameters** (object, optional): Parameters to override during import
  - Common overrides: `ResourceIdOverrideConfiguration`, `DataSetArn`, `DataSourceArn`
  - Format: AWS QuickSight OverrideParameters structure
  - Supports variable substitution: `{proj.name}`, `${ENV_VAR}`

- **permissions** (array, optional): Dashboard permissions to grant after deployment
  - **principal** (string): ARN of user or group (use `*` for account wildcard)
  - **actions** (array): QuickSight permission actions

**Note:** Use `*` instead of hardcoded account IDs in ARNs. Use `${REGION_VAR}` for regions.

## Workflow

### 1. Bundle Phase

When running `smus-cli bundle`, dashboards with `assetBundle: export` are exported:

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
3. Applies override parameters from `deployment_configuration.quicksight`
4. Grants permissions to specified principals
5. Dashboard and datasets are live in target environment
6. Imported dataset IDs are captured for bootstrap actions

## Use Cases

### Use Case 1: Promote Dashboard from Dev to Prod

**Scenario:** You have a dashboard in dev that you want to deploy to prod with different resource prefixes.

```yaml
content:
  quicksight:
    - dashboardId: sales-dashboard
      assetBundle: export

stages:
  dev:
    deployment_configuration:
      quicksight:
        overrideParameters:
          ResourceIdOverrideConfiguration:
            PrefixForAllResources: dev-
  
  prod:
    deployment_configuration:
      quicksight:
        overrideParameters:
          ResourceIdOverrideConfiguration:
            PrefixForAllResources: prod-
```

**Steps:**
1. Create dashboard in dev environment
2. Add to manifest with `assetBundle: export`
3. Run `smus-cli bundle --targets dev`
4. Run `smus-cli deploy --targets prod`

### Use Case 2: Environment-Specific Permissions

**Scenario:** Different permissions for different environments.

```yaml
content:
  quicksight:
    - dashboardId: analytics-dashboard
      assetBundle: export

stages:
  dev:
    deployment_configuration:
      quicksight:
        permissions:
          - principal: "arn:aws:quicksight:us-east-2:*:user/default/dev-team"
            actions: ["quicksight:DescribeDashboard", "quicksight:QueryDashboard"]
  
  prod:
    deployment_configuration:
      quicksight:
        permissions:
          - principal: "arn:aws:quicksight:us-east-1:*:group/default/executives"
            actions: ["quicksight:DescribeDashboard", "quicksight:QueryDashboard"]
```

### Use Case 3: Refresh Dashboards After ETL

**Scenario:** Automatically refresh QuickSight datasets after deploying ETL workflows.

```yaml
content:
  quicksight:
    - dashboardId: sales-dashboard
      assetBundle: export
  workflows:
    - workflowName: etl_pipeline
      connectionName: default.workflow_serverless

stages:
  prod:
    deployment_configuration:
      quicksight:
        overrideParameters:
          ResourceIdOverrideConfiguration:
            PrefixForAllResources: prod-
    bootstrap:
      actions:
        - type: workflow.run
          workflowName: etl_pipeline
          wait: true
        - type: quicksight.refresh_dataset
          refreshScope: IMPORTED  # Refreshes datasets from dashboard import
          wait: true
```

## Override Parameters

Override parameters allow you to customize dashboards per environment. Common parameters:

### Resource ID Prefix (Recommended)
```yaml
overrideParameters:
  ResourceIdOverrideConfiguration:
    PrefixForAllResources: prod-
```

### Dataset ARN
```yaml
overrideParameters:
  DataSetArn: "arn:aws:quicksight:us-east-1:*:dataset/prod-dataset"
```

### Data Source ARN
```yaml
overrideParameters:
  DataSourceArn: "arn:aws:quicksight:us-east-1:*:datasource/prod-source"
```

### Multiple Parameters
```yaml
overrideParameters:
  ResourceIdOverrideConfiguration:
    PrefixForAllResources: ${STAGE}-
  DataSetArn: "arn:aws:quicksight:${REGION}:*:dataset/${STAGE}-sales"
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

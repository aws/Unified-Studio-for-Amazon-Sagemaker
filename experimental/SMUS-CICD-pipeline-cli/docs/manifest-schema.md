# Application Manifest Schema

← [Back to Main README](../README.md) | 📖 [Complete Manifest Guide](manifest.md)

This document defines the schema for SMUS CI/CD application manifests. For detailed explanations, examples, and best practices, see the [Application Manifest Guide](manifest.md).

## Schema Overview

The manifest defines your application structure with these main sections:

### Required Fields
- **`applicationName`** - Unique application identifier
- **`stages`** - Deployment environments (dev, test, prod, etc.)

### Optional Fields
- **`content`** - Application content (storage, git, workflows, quicksight)

## Complete Schema Structure

### Application Identity
```yaml
applicationName: MyDataApp    # Required: Unique application name
```

### Content Configuration
```yaml
content:
  # Storage content (S3 files, data, models)
  storage:
    - name: code               # Required: Unique name for this content
      connectionName: default.s3_shared  # Required: Connection name
      include: ['src/']        # Optional: Include patterns
      exclude: ['*.pyc']       # Optional: Exclude patterns
      append: false            # Optional: Append vs replace (default: false)
  
  # Git repositories
  git:
    - repository: my-repo      # Required: Repository name
      url: https://github.com/user/repo.git  # Required: Git URL
      branch: main             # Optional: Branch name (default: main)
      include: ['src/']        # Optional: Include patterns
      exclude: ['*.pyc']       # Optional: Exclude patterns
  
  # Workflows (Airflow DAGs)
  workflows:
    - workflowName: daily_etl  # Required: Workflow name
      connectionName: project.workflow_serverless  # Required: Connection
  
  # QuickSight dashboards
  quicksight:
    - dashboardId: sales-dashboard  # Required: Dashboard ID
      assetBundle: quicksight/sales-dashboard.qs  # Required: Asset bundle path
  
  # Catalog assets
  catalog:
    assets:
      - selector:
          search:
            assetType: GlueTable  # Required: Asset type
            identifier: db.table  # Required: Asset identifier
        permission: READ       # Required: Permission level
        requestReason: "Pipeline access"  # Required: Justification
```

### Stage Configuration
```yaml
stages:
  dev:                         # Stage name (required)
    stage: DEV                 # Optional: Stage identifier
    domain:
      region: us-east-1        # Required: AWS region
      tags:                    # Optional: Domain tags
        purpose: development
    project:
      name: dev-project        # Required: Project name
      create: true             # Optional: Auto-create project (default: false)
      owners:                  # Optional: Project owners (required if create: true)
        - Eng1
        - arn:aws:iam::*:role/MyRole
      contributors: []         # Optional: Project contributors
      role:
        # Option 1: Use existing role
        arn: arn:aws:iam::123456789012:role/MyProjectRole
        
        # Option 2: Create new role with policies
        name: my-custom-role   # Optional: Custom role name
        policies:              # Policy ARNs to attach
          - arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
          - arn:aws:iam::123456789012:policy/MyCustomPolicy
    
    environment_variables:     # Optional: Environment variables
      S3_PREFIX: dev
      DATABASE: dev_db
    
    deployment_configuration:  # Optional: Stage-specific deployment config
      storage:
        - name: code           # Required: Name matching content.storage item
          connectionName: default.s3_shared
          targetDirectory: src # Required: Target directory
      quicksight:              # Optional: QuickSight overrides
        overrideParameters:
          ResourceIdOverrideConfiguration:
            PrefixForAllResources: dev-
        permissions:
          - principal: arn:aws:quicksight:us-east-1:123456789012:user/default/admin
            actions:
              - quicksight:DescribeDashboard
    
    bootstrap:                 # Optional: Initialization actions
      actions:
        # Event action - Emit EventBridge events
        - type: event
          eventSource: com.mycompany.app
          eventDetailType: ApplicationDeployed
          eventBusName: default  # Optional: Event bus (default: "default")
          detail:              # Optional: Event detail with variables
            application: ${application.name}
            stage: ${stage.name}
            project: ${project.name}
            region: ${domain.region}
          resources:           # Optional: Resource ARNs
            - arn:aws:s3:::my-bucket
        
        # Workflow action - Trigger workflows
        - type: workflow
          workflowName: setup_dag
          connectionName: project.workflow_mwaa
          engine: MWAA         # Optional: Engine type
          parameters:          # Optional: Workflow parameters
            key: value
        
        # DataZone connection action
        - type: datazone.create_connection
          connectionName: custom.athena
          connectionType: ATHENA
          properties:
            workgroup: primary
```

## Supported Variables

Variables can be used in workflow files and bootstrap event details:

### Application Variables
- `${application.name}` - Application name from manifest

### Stage Variables
- `${stage.name}` - Stage name (dev, test, prod)

### Project Variables
- `${project.name}` - DataZone project name
- `${proj.connection.CONNECTION_NAME.PROPERTY}` - Connection properties
- `${proj.iam_role_name}` - Project IAM role name
- `${proj.iam_role_arn}` - Project IAM role ARN

### Domain Variables
- `${domain.name}` - DataZone domain name
- `${domain.region}` - AWS region

### Environment Variables
- `${env.VAR_NAME}` - Environment variable
- `${VAR_NAME:default}` - Environment variable with default value

See [Substitutions & Variables](substitutions-and-variables.md) for complete documentation.

## Validation Rules

### Naming Conventions
- **Application names**: Must start with letter, alphanumeric + underscore/hyphen
- **Stage names**: Must start with letter, alphanumeric + underscore/hyphen
- **Regions**: Must match AWS region pattern (e.g., `us-east-1`)

### Constraints
- At least one stage must be defined
- Storage/git content items must have unique names
- Connection names should follow DataZone conventions (default.*, project.*)
- File patterns should use forward slashes

### Bootstrap Actions
- Event actions require `eventSource` and `eventDetailType`
- Workflow actions require `workflowName` and `connectionName`
- Variables are resolved at deployment time
- Actions are processed sequentially

## Common Patterns

### Minimal Manifest
```yaml
applicationName: SimpleApp

content:
  storage:
    - name: code
      connectionName: default.s3_shared
      include: ['src/']

stages:
  dev:
    domain:
      region: us-east-1
    project:
      name: dev-project
```

### Multi-Stage with Workflows
```yaml
applicationName: ETLPipeline

content:
  storage:
    - name: scripts
      connectionName: default.s3_shared
      include: ['scripts/']
  workflows:
    - workflowName: daily_etl
      connectionName: project.workflow_serverless

stages:
  test:
    domain:
      region: us-east-1
    project:
      name: test-analytics
      create: true
      owners: [Eng1]
    environment_variables:
      DATABASE: test_db
  
  prod:
    domain:
      region: us-east-1
    project:
      name: prod-analytics
    environment_variables:
      DATABASE: prod_db
```

### Git + Storage + QuickSight
```yaml
applicationName: AnalyticsDashboard

content:
  git:
    - repository: analytics-code
      url: https://github.com/myorg/analytics.git
  storage:
    - name: data
      connectionName: default.s3_shared
      include: ['data/']
  quicksight:
    - dashboardId: sales-dashboard
      assetBundle: quicksight/sales.qs

stages:
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
```

## Related Documentation

- **[Manifest Guide](manifest.md)** - Complete manifest documentation
- **[CLI Commands](cli-commands.md)** - Command reference
- **[Bootstrap Actions](bootstrap-actions.md)** - Initialization actions
- **[QuickSight Deployment](quicksight-deployment.md)** - Dashboard deployment
- **[Substitutions & Variables](substitutions-and-variables.md)** - Variable resolution

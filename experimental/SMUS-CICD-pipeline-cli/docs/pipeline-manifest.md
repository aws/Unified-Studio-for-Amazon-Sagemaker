# Pipeline Manifest Reference

← [Back to Main README](../README.md)

The pipeline manifest is a YAML file that defines your CI/CD pipeline configuration, including targets, workflows, and deployment settings.

## Environment Variable Parameterization

**NEW**: Pipeline manifests support environment variable substitution using `${VARIABLE_NAME}` or `${VARIABLE_NAME:default_value}` syntax. This enables flexible configuration across different environments without maintaining separate manifest files.

### Basic Syntax
```yaml
# Use environment variables with defaults in target configurations
targets:
  dev:
    domain:
      name: ${DOMAIN_NAME:my-default-domain}
      region: ${AWS_REGION:us-east-1}
    project:
      name: ${PROJECT_PREFIX:myapp}-dev

# Use environment variables without defaults (empty string if not set)
database:
  password: ${DB_PASSWORD}
```

### Multi-Environment Example
```yaml
pipelineName: ${PIPELINE_NAME:MyPipeline}

targets:
  dev:
    domain:
      name: ${DOMAIN_NAME}
      region: ${DEV_DOMAIN_REGION:us-east-2}
    project:
      name: ${PROJECT_PREFIX:myapp}-dev-${TEAM_NAME}
  
  prod:
    domain:
      name: ${DOMAIN_NAME}
      region: ${PROD_DOMAIN_REGION:us-east-1}
    project:
      name: ${PROJECT_PREFIX:myapp}-prod-${TEAM_NAME}
```

**Usage:**
```bash
# Set environment variables
export DOMAIN_NAME=production-domain
export DEV_DOMAIN_REGION=us-west-2
export PROJECT_PREFIX=dataplatform
export TEAM_NAME=analytics

# Deploy with substituted values
smus-cli deploy --pipeline pipeline.yaml --target prod
```

### Usage Examples

#### 1. Local Development
```bash
# Set environment variables
export AWS_REGION=us-west-2
export PROJECT_PREFIX=myteam
export DB_HOST=dev-db.company.com

# Run CLI commands - variables are automatically substituted
smus-cli describe --pipeline pipeline.yaml
smus-cli deploy --pipeline pipeline.yaml --targets dev
```

#### 2. CI/CD Environments
```bash
# GitHub Actions / CI environment
export AWS_REGION=us-east-2
export PROJECT_PREFIX=production
export DOMAIN_NAME=prod-datazone-domain

# Deploy to production
smus-cli deploy --pipeline pipeline.yaml --targets prod
```

#### 3. Multi-Environment Configuration
```yaml
# Same pipeline.yaml works across environments
targets:
  dev:
    domain:
      name: ${DOMAIN_NAME}  # Required - no default
      region: ${AWS_REGION:us-east-1}  # Optional - defaults to us-east-1
    project:
      name: ${ENV_PREFIX:dev}-${TEAM_NAME}-project
  
  staging:
    domain:
      name: ${DOMAIN_NAME}
      region: ${AWS_REGION:us-east-1}
    project:
      name: ${ENV_PREFIX:staging}-${TEAM_NAME}-project
  
  prod:
    domain:
      name: ${DOMAIN_NAME}
      region: ${AWS_REGION:us-east-1}
    project:
      name: ${ENV_PREFIX:prod}-${TEAM_NAME}-project
```

### Variable Resolution Rules

1. **Environment Variable Set**: Uses the environment variable value
   ```bash
   export AWS_REGION=us-west-2
   # ${AWS_REGION:us-east-1} → "us-west-2"
   ```

2. **Environment Variable Not Set**: Uses default value if provided
   ```bash
   unset AWS_REGION
   # ${AWS_REGION:us-east-1} → "us-east-1"
   ```

3. **No Default Value**: Uses empty string if variable not set
   ```bash
   unset DB_PASSWORD
   # ${DB_PASSWORD} → ""
   ```

### Common Use Cases

#### Multi-Region Deployments
```yaml
targets:
  dev:
    domain:
      region: ${DEV_DOMAIN_REGION:us-east-2}

# Deploy to different regions
export DEV_DOMAIN_REGION=us-west-2  # West Coast
export DEV_DOMAIN_REGION=eu-west-1  # Europe
```

#### Team-Specific Projects
```yaml
targets:
  dev:
    project:
      name: ${TEAM_NAME}-dev-project
      
# Each team sets their identifier
export TEAM_NAME=data-science    # → "data-science-dev-project"
export TEAM_NAME=ml-platform     # → "ml-platform-dev-project"
```

#### Environment-Specific Configuration
```yaml
bundle:
  storage:
    - connectionName: ${STORAGE_CONNECTION:default.s3_shared}
  
workflows:
  - workflowName: ${WORKFLOW_NAME:default_workflow}
    connectionName: ${MWAA_CONNECTION:project.workflow_mwaa}
```

### Integration Test Configuration

The integration tests use environment variables for flexible testing:

```yaml
# tests/integration/*/pipeline.yaml
targets:
  test:
    domain:
      name: cicd-test-domain
      region: ${DEV_DOMAIN_REGION:us-east-2}
```

**GitHub Actions** automatically sets:
```bash
export DEV_DOMAIN_REGION=us-east-2
```

**Local testing** can override:
```bash
export DEV_DOMAIN_REGION=us-east-1  # Use local domain
python -m pytest tests/integration/
```

### Best Practices

1. **Always provide defaults** for optional configuration
2. **Use descriptive variable names** (e.g., `DEV_DOMAIN_REGION` not `REGION`)
3. **Document required variables** in your pipeline README
4. **Group related variables** with consistent prefixes
5. **Validate critical variables** are set before deployment

## Quick Links

- **[Pipeline Manifest Schema Documentation](pipeline-manifest-schema.md)** - Complete schema reference with validation rules and examples
- **[CLI Commands Reference](cli-commands.md)** - Detailed command documentation

## Complete Example

```yaml
pipelineName: MarketingDataPipeline
bundlesDirectory: ./bundles

# What to include in deployment bundles
bundle:
  workflow:
    - connectionName: default.s3_shared
      append: true
      include: ['workflows/']
      exclude: ['.ipynb_checkpoints/', '__pycache__/', '*.pyc']
  storage:
    - connectionName: default.s3_shared
      append: false
      include: ['src/']
      exclude: ['.ipynb_checkpoints/', '__pycache__/', '*.pyc']
  git:
    repository: MyDataPipeline
    url: https://github.com/myorg/data-pipeline.git
    targetDir: git
  catalog:
    assets:
      - selector:
          search:
            assetType: GlueTable
            identifier: covid19_db.countries_aggregated
        permission: READ
        requestReason: Required access for pipeline deployment

# Target environments
targets:
  dev: 
    domain:
      name: ${DOMAIN_NAME:my-studio-domain}
      region: ${AWS_REGION:us-east-1}
    default: true
    project: 
      name: dev-marketing
      
  test: 
    domain:
      name: ${DOMAIN_NAME:my-studio-domain}
      region: ${AWS_REGION:us-east-1}
    project: 
      name: test-marketing
    initialization:
      project: 
        create: true
        profileName: 'All capabilities'
        owners: ['alice@company.com']
        contributors: ['bob@company.com', 'charlie@company.com']                     
      environments: 
        - EnvironmentConfigurationName: 'OnDemand Workflows'
    tests:
      folder: tests/integration/
    bundle_target_configuration:
      storage:
        connectionName: default.s3_shared
        directory: 'src'
      workflows:
        connectionName: default.s3_shared
        directory: 'workflows'   
    workflows:
      - workflowName: marketing_etl_dag
        parameters:
          environment: test
          debug_mode: true

  prod:
    domain:
      name: ${DOMAIN_NAME:my-studio-domain}
      region: ${AWS_REGION:us-east-1}
    project: 
      name: prod-marketing
    initialization:
      project: 
        create: true
        profileName: 'All capabilities'
        owners: ['alice@company.com']
        contributors: []                     
      environments: 
        - EnvironmentConfigurationName: 'OnDemand Workflows'
    bundle_target_configuration:
      storage:
        connectionName: default.s3_shared
        directory: 'src'
      workflows:
        connectionName: default.s3_shared
        directory: 'workflows'
    workflows:
      - workflowName: marketing_etl_dag
        parameters:
          environment: production
          debug_mode: false

# Global workflows (apply to all targets)
workflows:
  - workflowName: marketing_etl_dag
    connectionName: project.workflow_connection
    triggerPostDeployment: true
    logging: console
    engine: Workflows
    parameters:
      data_source: s3://marketing-data/
      output_bucket: s3://marketing-results/
```

## Section Reference

### Pipeline Metadata

```yaml
pipelineName: MarketingDataPipeline
bundlesDirectory: ./bundles  # Local directory
# OR
bundlesDirectory: s3://my-datazone-bucket/bundles  # S3 location
```

- **`pipelineName`** (required): Name of your pipeline, used for bundle filenames and identification
- **`bundlesDirectory`** (optional): Directory or S3 location where bundle zip files are created/stored (default: `./bundles`)

### Domain Configuration

Each target must specify its domain configuration:

```yaml
targets:
  dev:
    domain:
      name: my-studio-domain
      region: us-east-1
    project:
      name: dev-project
```

- **`domain.name`** (required): SageMaker Unified Studio domain name
- **`domain.region`** (required): AWS region where the domain exists

### Bundle Configuration

Defines what content to include in deployment packages:

#### Workflow Bundles

```yaml
bundle:
  workflow:
    - connectionName: default.s3_shared
      append: true
      include: ['workflows/']
      exclude: ['.ipynb_checkpoints/', '__pycache__/']
```

- **`connectionName`** (required): S3 connection name in the source project
- **`append`** (optional): Whether to append to existing files (default: `true`)
- **`include`** (optional): List of paths/patterns to include
- **`exclude`** (optional): List of paths/patterns to exclude

#### Storage Bundles

```yaml
bundle:
  storage:
    - connectionName: default.s3_shared
      append: false
      include: ['src/', 'data/']
      exclude: ['*.tmp', '.DS_Store']
```

- **`append`** (optional): Whether to append to existing files (default: `false` for storage)

#### Git Repositories

```yaml
bundle:
  git:
    repository: MyDataPipeline
    url: https://github.com/myorg/data-pipeline.git
    targetDir: git
```

- **`repository`** (optional): Repository name for identification
- **`url`** (required): Git repository URL
- **`targetDir`** (optional): Directory name in bundle (default: `git`)

#### Catalog Assets

```yaml
bundle:
  catalog:
    assets:
      - selector:
          search:
            assetType: GlueTable
            identifier: covid19_db.countries_aggregated
        permission: READ
        requestReason: Required access for pipeline deployment
      - selector:
          search:
            assetType: GlueTable
            identifier: sales_db.customer_data
        permission: READ
        requestReason: Customer analytics pipeline
```

- **`assets`** (required): List of catalog assets to request access to
- **`selector.search.assetType`** (required): Type of asset (currently supports `GlueTable`)
- **`selector.search.identifier`** (required): Asset identifier (e.g., `database.table`)
- **`permission`** (required): Access level requested (e.g., `READ`)
- **`requestReason`** (required): Business justification for access request

**Note**: Catalog asset access is processed during deployment. The system will:
1. Search for assets in the DataZone catalog
2. Create subscription requests if needed
3. Wait for approval (up to 5 minutes)
4. Verify subscription grants are completed
5. Fail deployment if access cannot be obtained

### Target Configuration

Each target represents a deployment environment:

```yaml
targets:
  dev:
    domain:
      name: my-studio-domain
      region: us-east-1
    default: true
    project:
      name: dev-marketing
```

- **`default`** (optional): Mark as default target for commands
- **`project.name`** (required): SageMaker Unified Studio project name

#### Target Initialization

```yaml
targets:
  test:
    domain:
      name: my-studio-domain
      region: us-east-1
    initialization:
      project:
        create: true
        profileName: 'All capabilities'
        owners: ['alice@company.com']
        contributors: ['bob@company.com']
        userParameters:
          - EnvironmentConfigurationName: 'Lakehouse Database'
            parameters:
              - name: glueDbName
                value: my_unique_db_name
      environments:
        - EnvironmentConfigurationName: 'OnDemand Workflows'
```

- **`project.create`** (optional): Whether to auto-create project (default: `false`)
- **`project.profileName`** (required if create=true): Project profile name
- **`project.owners`** (optional): List of project owner email addresses
- **`project.contributors`** (optional): List of project contributor email addresses
- **`project.userParameters`** (optional): Override project profile parameters during creation
  - **`EnvironmentConfigurationName`**: Name of environment configuration to override
  - **`parameters`**: Array of parameter name/value pairs to override
- **`environments`** (optional): List of environments to create post-project creation

#### Bundle Target Configuration

```yaml
targets:
  test:
    domain:
      name: my-studio-domain
      region: us-east-1
    bundle_target_configuration:
      storage:
        connectionName: default.s3_shared
        directory: 'src'
      workflows:
        connectionName: default.s3_shared
        directory: 'workflows'
```

- **`storage.connectionName`** (required): Target S3 connection for storage files
- **`storage.directory`** (optional): Target directory path
- **`workflows.connectionName`** (required): Target S3 connection for workflow files
- **`workflows.directory`** (optional): Target directory path

#### Target-Specific Workflows

```yaml
targets:
  test:
    domain:
      name: my-studio-domain
      region: us-east-1
    workflows:
      - workflowName: marketing_etl_dag
        parameters:
          environment: test
          debug_mode: true
```

- **`workflowName`** (required): Name of workflow to configure
- **`parameters`** (optional): Target-specific workflow parameters

#### Target Tests

```yaml
targets:
  test:
    domain:
      name: my-studio-domain
      region: us-east-1
    tests:
      folder: tests/integration/
```

- **`folder`** (required): Relative path to folder containing Python test files

Test files receive environment variables:
- `SMUS_DOMAIN_ID`: SageMaker Unified Studio domain ID
- `SMUS_PROJECT_ID`: Project ID
- `SMUS_PROJECT_NAME`: Project name
- `SMUS_TARGET_NAME`: Target name
- `SMUS_REGION`: AWS region
- `SMUS_DOMAIN_NAME`: Domain name

### Global Workflows

```yaml
workflows:
  - workflowName: marketing_etl_dag
    connectionName: project.workflow_connection
    triggerPostDeployment: true
    logging: console
    engine: Workflows
    parameters:
      data_source: s3://marketing-data/
```

- **`workflowName`** (required): Workflow/DAG name in the workflow engine
- **`connectionName`** (required): Workflow connection name in projects
- **`triggerPostDeployment`** (optional): Whether to trigger after deployment (default: `false`)
- **`logging`** (optional): Logging level (`console`, `none`) (default: `none`)
- **`engine`** (optional): Workflow engine type (default: `Workflows`)
- **`parameters`** (optional): Global workflow parameters (merged with target-specific)

## Validation Rules

### Required Fields
- `pipelineName`
- Each target must have `domain.name`, `domain.region`, and `project.name`

### Optional Sections
- `bundle` - If omitted, no bundling operations
- `workflows` - If omitted, no workflow operations
- `initialization` - If omitted, assumes projects exist

### Connection Names
- Must match actual connection names in SageMaker Unified Studio projects
- Format: `{connection_name}` (e.g., `default.s3_shared`, `project.workflow_connection`)

### File Patterns
- Support glob patterns: `*.py`, `**/*.yaml`
- Exclude patterns take precedence over include patterns
- Paths are relative to bundle source directories

## Bundle Storage Locations

The `bundlesDirectory` can be either a local directory or an S3 location:

### Local Storage
```yaml
bundlesDirectory: ./bundles
bundlesDirectory: /absolute/path/to/bundles
bundlesDirectory: ~/bundles  # Expands to user home directory
```

### S3 Storage
```yaml
bundlesDirectory: s3://my-bucket/bundles
bundlesDirectory: s3://sagemaker-unified-studio-<aws-account-id>-us-east-1-domain/bundles
```

**S3 Benefits:**
- **Centralized Storage**: Share bundles across team members and CI/CD systems
- **Version History**: S3 versioning can track bundle changes over time
- **Cross-Region Access**: Access bundles from different AWS regions
- **Integration**: Works seamlessly with DataZone domain S3 buckets

**Note**: When using S3 storage, the CLI will:
1. Create bundles locally in a temporary directory
2. Upload the completed bundle to the specified S3 location
3. Download bundles from S3 when needed for deployment

## Best Practices

### Bundle Storage
- **Local Development**: Use local directories (`./bundles`) for development and testing
- **Production/CI**: Use S3 locations for production pipelines and CI/CD systems
- **DataZone Integration**: Use your DataZone domain S3 bucket with `/bundles` prefix
- **Permissions**: Ensure your AWS credentials have read/write access to the S3 bucket

### Naming Conventions
- Use descriptive pipeline names: `MarketingDataPipeline`, `CustomerAnalytics`
- Use consistent target names: `dev`, `test`, `prod`
- Use clear project names: `{team}-{environment}` (e.g., `marketing-dev`)

### Bundle Configuration
- Always exclude temporary files: `.ipynb_checkpoints/`, `__pycache__/`, `*.pyc`
- Use `append: true` for workflows (allows incremental updates)
- Use `append: false` for storage (ensures clean deployments)

### Target Organization
- Mark one target as `default: true` for convenience
- Use initialization only for non-production environments
- Keep production targets minimal and explicit

### Workflow Parameters
- Use global parameters for common settings
- Use target-specific parameters for environment differences
- Avoid hardcoded values - use parameters instead

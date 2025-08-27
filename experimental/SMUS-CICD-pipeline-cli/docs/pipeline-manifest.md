# Pipeline Manifest Reference

← [Back to Main README](../README.md)

The pipeline manifest is a YAML file that defines your CI/CD pipeline configuration, including targets, workflows, and deployment settings.

## Quick Links

- **[Pipeline Manifest Schema Documentation](pipeline-manifest-schema.md)** - Complete schema reference with validation rules and examples
- **[CLI Commands Reference](cli-commands.md)** - Detailed command documentation

## Complete Example

```yaml
pipelineName: MarketingDataPipeline
bundlesDirectory: ./bundles

# Domain configuration
domain:
  name: my-studio-domain
  region: us-east-1

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

# Target environments
targets:
  dev: 
    default: true
    project: 
      name: dev-marketing
      
  test: 
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

```yaml
domain:
  name: my-studio-domain
  region: us-east-1
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

### Target Configuration

Each target represents a deployment environment:

```yaml
targets:
  dev:
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
- `domain.name` and `domain.region`
- At least one target with `project.name`

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

# Application Deployment Manifest

← [Back to Main README](../README.md)

The Application Deployment Manifest is a YAML file that defines **what** your application is and **where** it should be deployed in Amazon SageMaker Unified Studio.

## What is an Application Deployment Manifest?

The manifest is a **declarative configuration** that defines:

- **Application identity**: Name and description
- **Content**: Code from git, data/models from storage
- **Activation**: How to run it (workflows, events, etc.)
- **Stages**: Where to deploy (dev, test, prod environments)
- **Configuration**: Environment-specific settings

### Who Owns What

- **Data Teams** own the manifest - Define what to deploy and where
- **DevOps Teams** own CI/CD automation - Define how and when to deploy

## Content Sources

Your application content can come from:
- **Git repositories** - for source code
- **Storage (S3)** - for data, models, large files
- **Both together** - common pattern for most applications

**Workflow:**
```bash
# Step 1: Create bundle archive
smus-cli bundle --manifest manifest.yaml --output ./bundles/

# Step 2: Deploy the same bundle to multiple targets
smus-cli deploy --manifest manifest.yaml --stage test --manifest myapp-v1.0.0.tar.gz
smus-cli deploy --manifest manifest.yaml --stage prod --manifest myapp-v1.0.0.tar.gz
```

**What happens:**
1. `bundle` command packages all content (storage files + git repos) into a `.tar.gz` archive
2. `deploy` command extracts the archive and syncs content to the target project
3. Same archive can be deployed to multiple targets for consistency

**Best for:**
- Need versioned artifacts for audit trail
- Want to deploy the exact same artifact to multiple targets
- Require rollback capability
- Compliance and governance requirements
- CI/CD pipelines that create artifacts once, deploy many times

## Quick Links

- **[Manifest Schema Documentation](manifest-schema.md)** - Complete schema reference with validation rules
- **[Substitutions and Variables](substitutions-and-variables.md)** - Dynamic variable resolution in workflows
- **[CLI Commands Reference](cli-commands.md)** - Detailed command documentation

## Minimal Example

For simple use cases, the manifest can be very straightforward:

```yaml
applicationName: SimpleETLPipeline

# Application content to deploy
content:
  # Code from git repository
  git:
    - repository: etl-pipeline
      url: https://github.com/myorg/etl-pipeline.git
  
  # Data files from storage
  storage:
    - name: reference-data
      connectionName: default.s3_shared
      include: ['data/reference/']

# How to activate/run the application
activation:
  workflows:
    - workflowName: etl_workflow
      engine: airflow-serverless

# Where to deploy
stages:
  test:
    stage: TEST
    domain:
      name: my-studio-domain
      region: us-east-1
    project:
      name: test-project
    deployment_configuration:
      storage:
        - name: reference-data
          connectionName: default.s3_shared
          stageDirectory: 'data'
```

This minimal example:
- Defines application code from git repository
- Includes reference data from S3 storage
- Creates a serverless Airflow workflow after deployment
- Uses an existing project (no initialization needed)
- Perfect for git-based workflows with data dependencies

## Comprehensive Example

This example demonstrates most features of the manifest:

```yaml
applicationName: MLTrainingPipeline

# Optional: Directory for storing bundle archives (local path or S3)
# Only used when creating bundles with `smus-cli bundle` command
bundlesDirectory: s3://sagemaker-unified-studio-123456789012-us-east-1-domain/bundles

# Application content - what to include in deployments
content:
  # Application code from git
  git:
    - repository: MLTrainingPipeline
      url: https://github.com/myorg/ml-training.git
    - repository: SharedUtilities
      url: https://github.com/myorg/shared-utils.git
  
  # Models and data from storage
  storage:
    - name: pretrained-models
      connectionName: default.s3_shared
      append: false
      include: ['models/pretrained/']
      exclude: ['*.tmp', '.DS_Store']

# How to activate/run the application
activation:
  workflows:
    - workflowName: ml_training_workflow
      engine: airflow-serverless
    
    - name: training-data
      connectionName: default.s3_shared
      append: false
      include: ['data/training/']
      exclude: ['.ipynb_checkpoints/']
  
  # DataZone catalog assets
  catalog:
    assets:
      - selector:
          search:
            assetType: GlueTable
            identifier: ml_features_db.customer_features
        permission: READ
        requestReason: Required for model training

# Target environments
stages:
  test:
    stage: DEV
    domain:
      name: ${DOMAIN_NAME:my-studio-domain}
      region: ${AWS_REGION:us-east-1}
    project:
      name: dev-marketing
    
    # Deployment configuration: where content gets deployed in the target project
    # Maps content items to target locations and connections
    deployment_configuration:
      storage:
        - name: code
          connectionName: default.s3_shared
          stageDirectory: 'src'
        - name: workflows
          connectionName: default.s3_shared
          stageDirectory: 'workflows'
    
    # Target-specific workflow parameters
    environment_variables:
      S3_PREFIX: "dev"
      DEBUG_MODE: true
      MAX_RETRIES: 3

  test:
    stage: TEST
    domain:
      name: ${DOMAIN_NAME:my-studio-domain}
      region: ${AWS_REGION:us-east-1}
    project:
      name: test-marketing
    
    # Auto-create project and resources
    initialization:
      project:
        create: true
        profileName: 'All capabilities'
        owners: ['alice@company.com']
        contributors: ['bob@company.com']
        role:
          arn: arn:aws:iam::123456789012:role/MyProjectRole
        userParameters:
          - EnvironmentConfigurationName: 'Lakehouse Database'
            parameters:
              - name: glueDbName
                value: test_marketing_db
      
      environments:
        - EnvironmentConfigurationName: 'OnDemand Workflows'
      
      # Create connections
      connections:
        - name: s3-data-lake
          type: S3
          properties:
            s3Uri: "s3://test-data-bucket/data/"
        
        - name: athena-analytics
          type: ATHENA
          properties:
            workgroupName: "test-workgroup"
        
        - name: spark-processing
          type: SPARK_GLUE
          properties:
            glueVersion: "4.0"
            workerType: "G.1X"
            numberOfWorkers: 5
        
        - name: mwaa-workflows
          type: WORKFLOWS_MWAA
          properties:
            mwaaEnvironmentName: "test-airflow-env"
        
        - name: serverless-workflows
          type: WORKFLOWS_SERVERLESS
          properties: {}
    
    deployment_configuration:
      storage:
        - name: code
          connectionName: default.s3_shared
          stageDirectory: 'src'
        - name: workflows
          connectionName: default.s3_shared
          stageDirectory: 'workflows'
    
    environment_variables:
      S3_PREFIX: "test"
      DEBUG_MODE: false
      MAX_RETRIES: 5

  prod:
    stage: PROD
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
    
    deployment_configuration:
      storage:
        - name: code
          connectionName: default.s3_shared
          stageDirectory: 'src'
        - name: workflows
          connectionName: default.s3_shared
          stageDirectory: 'workflows'
      catalog:
        disable: true  # Disable catalog processing for prod
    
    environment_variables:
      S3_PREFIX: "prod"
      DEBUG_MODE: false
      MAX_RETRIES: 10

# How to activate/run the application (apply to all stages unless overridden)
activation:
  workflows:
    - workflowName: marketing_etl_dag
      connectionName: project.workflow_mwaa
      engine: MWAA
      triggerPostDeployment: true
      logging: console
      parameters:
        data_source: s3://marketing-data/
        output_bucket: s3://marketing-results/
  
  tests:
    folder: tests/integration/
```

---

## Content Section

The `content` section defines what to package and deploy to target environments.

### Bundle Storage Location

```yaml
bundlesDirectory: ./bundles  # Local directory
# OR
bundlesDirectory: s3://my-bucket/bundles  # S3 location
```

- **Local Storage**: Use for development and testing (`./bundles`, `~/bundles`)
- **S3 Storage**: Use for production and CI/CD systems
  - Centralized storage across teams
  - Version history with S3 versioning
  - Cross-region access
  - Integration with DataZone domain S3 buckets

### Storage Items

Package source code, libraries, and data files:

```yaml
content:
  storage:
    - name: code
      connectionName: default.s3_shared
      append: false
      include: ['src/', 'lib/', 'data/']
      exclude: ['.ipynb_checkpoints/', '__pycache__/', '*.pyc', '.DS_Store']
    
    - name: workflows
      connectionName: default.s3_shared
      append: true
      include: ['workflows/', 'dags/']
      exclude: ['.ipynb_checkpoints/', '__pycache__/', '*.pyc']
```

**Properties:**
- `name` (required): Unique identifier for this content item
- `connectionName` (required): S3 connection name in source project
- `append` (optional): Append to existing files (default: `false`)
- `include` (optional): Paths/patterns to include
- `exclude` (optional): Paths/patterns to exclude

**Best Practices:**
- Use `append: true` for workflows (incremental updates)
- Use `append: false` for source code (clean deployments)
- Always exclude temporary files: `.ipynb_checkpoints/`, `__pycache__/`, `*.pyc`
- Use descriptive names: `code`, `workflows`, `data`, `models`

### Git Repositories

Include Git repositories in your application content:

```yaml
content:
  git:
    - repository: MyDataPipeline
      url: https://github.com/myorg/data-pipeline.git
    - repository: SharedLibraries
      url: https://github.com/myorg/shared-libs.git
```

**Properties:**
- `repository` (required): Repository name (used in deployment path: `repositories/{repository-name}/`)
- `url` (required): Git repository URL

**Note:** Git repositories are always cloned to `repositories/{repository-name}/` in the bundle. No `targetDir` configuration needed.

### Catalog Assets

Request access to DataZone catalog assets:

```yaml
bundle:
  catalog:
    assets:
      - selector:
          search:
            assetType: GlueTable
            identifier: covid19_db.countries_aggregated
        permission: READ
        requestReason: Required for analytics pipeline
      
      - selector:
          search:
            assetType: GlueTable
            identifier: sales_db.customer_data
        permission: READ
        requestReason: Customer analytics
```

**Properties:**
- `assets` (required): List of catalog assets
- `selector.search.assetType` (required): Asset type (currently `GlueTable`)
- `selector.search.identifier` (required): Asset identifier (`database.table`)
- `permission` (required): Access level (`READ`, `WRITE`)
- `requestReason` (required): Business justification

**Deployment Process:**
1. Search for assets in DataZone catalog
2. Create subscription requests if needed
3. Wait for approval (up to 5 minutes)
4. Verify subscription grants
5. Fail deployment if access cannot be obtained

---

## Target Section

Targets represent deployment environments (dev, test, prod). Each target defines domain, project, and environment-specific configurations.

### Basic Target Configuration

```yaml
stages:
  dev:
    stage: DEV
    domain:
      name: my-studio-domain
      region: us-east-1
    project:
      name: dev-marketing
```

**Required Properties:**
- `stage` (required): Deployment stage name (`DEV`, `TEST`, `PROD`)
- `domain.name` (required): SageMaker Unified Studio domain name
- `domain.region` (required): AWS region where domain exists
- `project.name` (required): Project name in the domain

### Target Initialization

Auto-create projects, environments, and connections:

```yaml
stages:
  test:
    stage: TEST
    domain:
      name: my-studio-domain
      region: us-east-1
    project:
      name: test-marketing
    
    initialization:
      project:
        create: true
        profileName: 'All capabilities'
        owners: ['alice@company.com']
        contributors: ['bob@company.com', 'charlie@company.com']
        userParameters:
          - EnvironmentConfigurationName: 'Lakehouse Database'
            parameters:
              - name: glueDbName
                value: my_unique_db_name
      
      environments:
        - EnvironmentConfigurationName: 'OnDemand Workflows'
        - EnvironmentConfigurationName: 'Lakehouse Database'
      
      connections:
        - name: s3-data-lake
          type: S3
          properties:
            s3Uri: "s3://my-data-bucket/data/"
```

**Project Properties:**
- `create` (optional): Auto-create project (default: `false`)
- `profileName` (required if create=true): Project profile name
- `owners` (optional): List of owner email addresses or IAM ARNs
  - Use `*` as wildcard for account ID: `arn:aws:iam::*:role/MyRole` (replaced with current account)
- `contributors` (optional): List of contributor email addresses or IAM ARNs
  - Use `*` as wildcard for account ID: `arn:aws:iam::*:role/MyRole` (replaced with current account)
- `role` (optional): Customer-provided IAM role for the project
  - `arn`: IAM role ARN (e.g., `arn:aws:iam::123456789012:role/MyProjectRole`)
  - Use `*` as wildcard for account ID: `arn:aws:iam::*:role/MyProjectRole` (replaced with current account)
  - The role must have a trust policy allowing DataZone and Airflow Serverless service principals
- `userParameters` (optional): Override project profile parameters
  - `EnvironmentConfigurationName`: Environment configuration to override
  - `parameters`: Array of name/value pairs

**Environments:**
- List of environment configurations to create
- `EnvironmentConfigurationName`: Name of environment configuration

**Connections:**
- See [Connections](#connections) section for all supported types

### Bundle Target Configuration

Specify where bundles are deployed in each target using name-based matching:

```yaml
stages:
  test:
    stage: TEST
    domain:
      name: my-studio-domain
      region: us-east-1
    project:
      name: test-marketing
    
    deployment_configuration:
      storage:
        - name: code                    # Matches bundle.storage[name=code]
          connectionName: default.s3_shared
          stageDirectory: 'src'
        - name: workflows               # Matches bundle.storage[name=workflows]
          connectionName: default.s3_shared
          stageDirectory: 'workflows'
      git:
        - connectionName: default.s3_shared
          stageDirectory: 'repos'      # All git repos deploy here
      catalog:
        disable: false
```

**Properties:**
- `storage` (list): Storage deployment configuration
  - `name` (required): Name matching bundle storage item
  - `connectionName` (required): Target S3 connection
  - `stageDirectory` (required): Target directory path (use `.` or `''` for root)
- `git` (list): Git deployment configuration
  - `connectionName` (required): Target S3 connection
  - `stageDirectory` (required): Target directory path
- `catalog.disable` (optional): Disable catalog asset processing (default: `false`)

**Note:** Use `stageDirectory: '.'` or `stageDirectory: ''` to deploy to the connection root without a subdirectory.

### Target Tests

---

## Activation Section

The `activation` section defines how to run and trigger your application. Currently supports workflows and tests, with future support for events, CloudFormation stacks, and other activation methods.

### Workflows

Workflows define DAGs or pipelines to trigger after deployment. Apply to all stages unless overridden:

```yaml
activation:
  workflows:
    - workflowName: marketing_etl_dag
      connectionName: project.workflow_mwaa
      engine: MWAA
      triggerPostDeployment: true
      logging: console
      parameters:
        data_source: s3://marketing-data/
        output_bucket: s3://marketing-results/
```

**Properties:**
- `workflowName` (required): Workflow/DAG name in the workflow engine
- `connectionName` (required): Workflow connection name (required for MWAA, optional for airflow-serverless)
- `engine` (optional): Workflow engine type (`MWAA`, `airflow-serverless`) (default: `MWAA`)
- `triggerPostDeployment` (optional): Trigger after deployment (default: `false`)
- `logging` (optional): Logging level (`console`, `file`, `none`) (default: `console`)
- `parameters` (optional): Global workflow parameters

### Tests

Integration tests to run after deployment:

```yaml
activation:
  tests:
    folder: tests/integration/
```

**Properties:**
- `folder` (required): Relative path to folder containing Python test files

**Environment Variables Available to Tests:**
- `SMUS_DOMAIN_ID`: Domain ID
- `SMUS_PROJECT_ID`: Project ID
- `SMUS_PROJECT_NAME`: Project name
- `SMUS_STAGE_NAME`: Target name
- `SMUS_REGION`: AWS region
- `SMUS_DOMAIN_NAME`: Domain name

### Future Activation Methods

The `activation` section will support additional methods:
- **Events**: Trigger EventBridge events for event-driven architectures
- **CloudFormation**: Deploy resources (S3 buckets, ECR repos) alongside application
- **Custom**: Extensible framework for team-specific activation needs

---

## Connections

Connections define integrations with AWS services and data sources. They are created during target initialization.

### Connection Configuration

```yaml
initialization:
  connections:
    - name: connection-name
      type: CONNECTION_TYPE
      properties:
        # Type-specific properties
```

### Supported Connection Types

#### S3 - Object Storage

```yaml
- name: s3-data-lake
  type: S3
  properties:
    s3Uri: "s3://my-data-bucket/data/"
```

**Properties:**
- `s3Uri` (required): S3 bucket URI with optional prefix

#### IAM - Identity and Access Management

```yaml
- name: iam-lineage-sync
  type: IAM
  properties:
    glueLineageSyncEnabled: true
```

**Properties:**
- `glueLineageSyncEnabled` (required): Enable Glue lineage sync (`true`/`false`)

#### SPARK_GLUE - Spark on AWS Glue

```yaml
- name: spark-processing
  type: SPARK_GLUE
  properties:
    glueVersion: "4.0"
    workerType: "G.1X"
    numberOfWorkers: 5
    maxRetries: 1
```

**Properties:**
- `glueVersion` (required): Glue version (`"4.0"`, `"5.0"`)
- `workerType` (required): Worker type (`"G.1X"`, `"G.2X"`)
- `numberOfWorkers` (required): Number of workers
- `maxRetries` (optional): Maximum retries

#### ATHENA - SQL Query Engine

```yaml
- name: athena-analytics
  type: ATHENA
  properties:
    workgroupName: "primary"
```

**Properties:**
- `workgroupName` (required): Athena workgroup name

#### REDSHIFT - Data Warehouse

```yaml
- name: redshift-warehouse
  type: REDSHIFT
  properties:
    storage:
      clusterName: "analytics-cluster"
      # OR
      workgroupName: "analytics-workgroup"
    databaseName: "analytics"
    host: "analytics-cluster.abc123.us-east-1.redshift.amazonaws.com"
    port: 5439
```

**Properties:**
- `storage.clusterName` (required for provisioned): Redshift cluster name
- `storage.workgroupName` (required for serverless): Redshift serverless workgroup
- `databaseName` (required): Database name
- `host` (required): Redshift endpoint hostname
- `port` (required): Port number (typically `5439`)

#### SPARK_EMR - Spark on EMR

```yaml
- name: spark-emr-processing
  type: SPARK_EMR
  properties:
    computeArn: "arn:aws:emr-serverless:us-east-1:123456789012:/applications/00abc123def456"
    runtimeRole: "arn:aws:iam::123456789012:role/EMRServerlessExecutionRole"
```

**Properties:**
- `computeArn` (required): EMR compute ARN (serverless application or cluster)
- `runtimeRole` (required): IAM role ARN for execution

#### MLFLOW - ML Experiment Tracking

```yaml
- name: mlflow-experiments
  type: MLFLOW
  properties:
    trackingServerName: "wine-classification-mlflow-v2"
    trackingServerArn: "arn:aws:sagemaker:us-east-1:123456789012:mlflow-tracking-server/wine-classification-mlflow-v2"
```

**Properties:**
- `trackingServerName` (required): MLflow tracking server name
- `trackingServerArn` (required): MLflow tracking server ARN

#### WORKFLOWS_MWAA - Apache Airflow Workflows

```yaml
- name: mwaa-workflows
  type: WORKFLOWS_MWAA
  properties:
    mwaaEnvironmentName: "production-airflow-env"
```

**Properties:**
- `mwaaEnvironmentName` (required): MWAA environment name

#### WORKFLOWS_SERVERLESS - Serverless Airflow Workflows

```yaml
- name: serverless-workflows
  type: WORKFLOWS_SERVERLESS
  properties: {}
```

**Properties:**
- No properties required (empty structure)

### Connection Examples

Complete example with multiple connection types:

```yaml
initialization:
  connections:
    - name: s3-raw-data
      type: S3
      properties:
        s3Uri: "s3://raw-data-bucket/incoming/"
    
    - name: iam-lineage
      type: IAM
      properties:
        glueLineageSyncEnabled: true
    
    - name: spark-etl
      type: SPARK_GLUE
      properties:
        glueVersion: "4.0"
        workerType: "G.2X"
        numberOfWorkers: 10
    
    - name: athena-queries
      type: ATHENA
      properties:
        workgroupName: "analytics-workgroup"
    
    - name: redshift-dw
      type: REDSHIFT
      properties:
        storage:
          clusterName: "analytics-cluster"
        databaseName: "analytics"
        host: "analytics-cluster.abc123.us-east-1.redshift.amazonaws.com"
        port: 5439
    
    - name: emr-processing
      type: SPARK_EMR
      properties:
        computeArn: "arn:aws:emr-serverless:us-east-1:123456789012:/applications/00abc123def456"
        runtimeRole: "arn:aws:iam::123456789012:role/EMRServerlessExecutionRole"
    
    - name: ml-tracking
      type: MLFLOW
      properties:
        trackingServerName: "ml-experiments-server"
        trackingServerArn: "arn:aws:sagemaker:us-east-1:123456789012:mlflow-tracking-server/ml-experiments-server"
    
    - name: airflow-orchestration
      type: WORKFLOWS_MWAA
      properties:
        mwaaEnvironmentName: "production-airflow-env"
    
    - name: serverless-workflows
      type: WORKFLOWS_SERVERLESS
      properties: {}
```

---

## Parameterization

The bundle manifest supports two types of parameterization:

1. **Manifest-level parameterization**: Environment variables in the manifest itself
2. **Workflow-level parameterization**: Parameters passed to workflow DAG files

### Manifest-Level Parameterization

Use environment variables in the manifest with `${VAR_NAME:default_value}` syntax:

```yaml
bundleName: ${BUNDLE_NAME:MarketingBundle}

stages:
  dev:
    domain:
      name: ${DOMAIN_NAME:my-studio-domain}
      region: ${AWS_REGION:us-east-1}
    project:
      name: ${PROJECT_PREFIX:dev}-${TEAM_NAME:marketing}-project
```

**Usage:**
```bash
export DOMAIN_NAME=prod-datazone-domain
export AWS_REGION=us-west-2
export PROJECT_PREFIX=analytics
export TEAM_NAME=datascience

smus-cli deploy --manifest manifest.yaml --stage dev
```

**Resolution Rules:**
1. If environment variable is set: Use the value
2. If environment variable is not set: Use default value
3. If no default value: Use empty string

### Workflow-Level Parameterization

Parameters can be defined at two levels:

#### 1. Global Workflow Parameters

Defined in the `activation.workflows` section, apply to all stages:

```yaml
activation:
  workflows:
    - workflowName: marketing_etl_dag
      connectionName: project.workflow_mwaa
      parameters:
        data_source: s3://marketing-data/
        output_bucket: s3://marketing-results/
        timeout: 3600
```

#### 2. Stage Environment Variables

Defined in `stages[].environment_variables`, substituted in workflow files:

```yaml
stages:
  dev:
    environment_variables:
      S3_PREFIX: "dev"
      DEBUG_MODE: true
      MAX_RETRIES: 3
  
  test:
    environment_variables:
      S3_PREFIX: "test"
      DEBUG_MODE: false
      MAX_RETRIES: 5
```

### Using Parameters in Workflow DAG Files

Environment variables are substituted in workflow files using `${VAR_NAME}` or `$VAR_NAME` syntax:

```yaml
# workflows/dags/marketing_dag.yaml
my_dag:
  dag_id: "data_processing"
  tasks:
    extract_data:
      operator: "airflow.providers.amazon.aws.operators.s3.S3ListOperator"
      bucket: "my-data-bucket"
      prefix: ${S3_PREFIX}        # Resolves to "dev" or "test"
    
    process_data:
      operator: "airflow.operators.python.PythonOperator"
      python_callable: "process_data"
      op_kwargs:
        debug: $DEBUG_MODE       # Resolves to true or false
        retries: $MAX_RETRIES    # Resolves to 3 or 5
```

### Parameter Resolution Process

During deployment, the CLI:
1. Reads target's `environment_variables` configuration
2. Scans workflow files for `${VAR_NAME}` and `$VAR_NAME` patterns
3. Replaces variables with target-specific values
4. Uploads resolved files to the deployment environment

**Example Resolution:**

**Source workflow file:**
```yaml
prefix: ${S3_PREFIX}
debug: $DEBUG_MODE
```

**Dev target result:**
```yaml
prefix: dev
debug: true
```

**Test target result:**
```yaml
prefix: test
debug: false
```

### Supported Variable Types

Environment variables support multiple data types:

```yaml
environment_variables:
  STRING_VAR: "my-string"      # String value
  BOOLEAN_VAR: true            # Boolean value
  NUMBER_VAR: 42               # Numeric value
  PREFIX_VAR: "data/staging"   # Path/prefix strings
```

### Complete Parameterization Example

```yaml
applicationName: ${APPLICATION_NAME:DataApplication}

stages:
  dev:
    domain:
      name: ${DOMAIN_NAME}
      region: ${AWS_REGION:us-east-1}
    project:
      name: ${PROJECT_PREFIX}-dev-project
    
    # Environment variables for workflow file substitution
    environment_variables:
      S3_PREFIX: "dev"
      DEBUG_MODE: true
      MAX_RETRIES: 3
      DB_HOST: "dev-db.company.com"

activation:
  # Global workflow parameters
  workflows:
    - workflowName: etl_dag
      connectionName: project.workflow_mwaa
      parameters:
        data_source: s3://data-bucket/
        timeout: 3600
```

**Workflow DAG file (`workflows/dags/etl_dag.yaml`):**
```yaml
etl_dag:
  dag_id: "etl_pipeline"
  default_args:
    retries: $MAX_RETRIES
  tasks:
    extract:
      operator: "airflow.providers.amazon.aws.operators.s3.S3ListOperator"
      bucket: "data-bucket"
      prefix: ${S3_PREFIX}
    
    transform:
      operator: "airflow.operators.python.PythonOperator"
      python_callable: "transform_data"
      op_kwargs:
        debug: $DEBUG_MODE
        db_host: ${DB_HOST}
```

**Final merged parameters for dev target:**
- From global: `data_source`, `timeout`
- From environment_variables (substituted in DAG): `S3_PREFIX`, `DEBUG_MODE`, `MAX_RETRIES`, `DB_HOST`

---

## Validation Rules

### Required Fields
- `applicationName`
- `content` with at least `workflows` defined
- `targets` (at least one target)
- Each target must have: `stage`, `domain.name`, `domain.region`, `project.name`

### Optional Sections
- `content.storage` - If omitted, no storage items to deploy
- `content.git` - If omitted, no git repositories to include
- `content.catalog` - If omitted, no catalog assets to subscribe
- `bundlesDirectory` - If omitted, defaults to `./bundles/` for bundle operations
- `initialization` - If omitted, assumes projects exist

### Connection Names
- Must match actual connection names in SageMaker Unified Studio projects
- Format: `{connection_name}` (e.g., `default.s3_shared`, `project.workflow_mwaa`)

### File Patterns
- Support glob patterns: `*.py`, `**/*.yaml`
- Exclude patterns take precedence over include patterns
- Paths are relative to content source directories

---

## Best Practices

### Application Content
- Always exclude temporary files: `.ipynb_checkpoints/`, `__pycache__/`, `*.pyc`
- Use `append: true` for workflows (incremental updates)
- Use `append: false` for storage (clean deployments)
- Use S3 storage for production and CI/CD systems
- Consider using git repositories for version-controlled source code

### Deployment Strategy
- **Bundle-based**: Use when you need versioned artifacts, audit trails, or rollback capability
- **Direct**: Use for simpler workflows, rapid iterations, or git-based deployments
- Both modes work with any combination of storage and git sources

### Target Organization
- Use initialization only for non-production environments
- Keep production targets minimal and explicit
- Use consistent naming: `dev`, `test`, `prod`

### Parameterization
- Use manifest-level parameters for infrastructure configuration
- Use workflow-level parameters for application configuration
- Use environment variables for target-specific values in workflows
- Always provide default values for optional parameters
- Use descriptive variable names (e.g., `DEV_DOMAIN_REGION` not `REGION`)

### Workflow Parameters
- Define common parameters globally
- Override with target-specific parameters for environment differences
- Use environment variables for values that change per target
- Avoid hardcoded values - use parameters instead

### Connection Management
- Create connections during initialization for new projects
- Use descriptive connection names
- Document connection requirements in project README
- Test connections after creation

---

## Terminology Glossary

### Application Deployment Manifest
YAML file that declares:
- **WHAT**: Application identity, dependencies, and configuration
- **WHERE**: Targets where the application should run (dev, test, prod)

### Application
The data/analytics workload being deployed (ETL workflows, ML models, APIs, etc.)

### Target
Environment where application runs (dev, test, prod). Each target specifies a domain, region, and project.

### Content
The application content to deploy, which can include:
- **Workflows**: Airflow DAGs or other workflow definitions
- **Storage**: Files and directories from S3 or local paths
- **Git**: Source code from git repositories
- **Catalog**: DataZone catalog assets

### GitHub Workflows
CI/CD automation that defines:
- **HOW**: Deployment mechanism (bundle-based, branch-based, etc.)
- **WHEN**: Deployment triggers (on push, on schedule, manual, etc.)

### Deployment
Process of promoting application to a target (executed by GitHub workflows)

### Separation of Concerns
- **Data/science teams** own: Application Deployment Manifest (what & where)
- **CI/CD/platform teams** own: GitHub workflows (how & when)

### Why "manifest"?
- Standard term in infrastructure-as-code (Kubernetes, Docker, Terraform)
- Implies declarative configuration
- Short and familiar in CLI usage (`--manifest`)

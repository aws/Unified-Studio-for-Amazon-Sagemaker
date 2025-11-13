# Connections Guide

← [Back to Main README](../README.md)

Connections define integrations with AWS services and data sources in SageMaker Unified Studio projects. This guide covers how to create, configure, and use connections in your data applications.

---

## Overview

Connections enable your workflows to interact with:
- **Data Storage** - S3, Redshift, RDS
- **Compute Engines** - Spark (Glue/EMR), Athena
- **ML Services** - SageMaker, MLflow
- **Orchestration** - MWAA, Serverless Airflow

**Two ways to create connections:**
1. **Manifest-based** (recommended) - Define in `bundle.yaml` for automated creation
2. **Console-based** - Create manually in SMUS console

---

## Default Connections

Every SMUS project includes these connections automatically:

| Connection Name | Type | Purpose |
|----------------|------|---------|
| `default.s3_shared` | S3 | Project S3 bucket |
| `project.workflow_mwaa` | MWAA | MWAA environment (if enabled) |
| `project.athena` | Athena | Athena workgroup |
| `project.default_lakehouse` | Lakehouse | Lakehouse connection |

---

## Creating Connections via Manifest

Define connections in your bundle manifest under `initialization.connections`:

```yaml
targets:
  test:
    domain:
      name: my-domain
      region: us-east-1
    project:
      name: test-project
      create: true
    initialization:
      project:
        create: true
        profileName: 'All capabilities'
        owners: [admin@example.com]
      environments:
        - EnvironmentConfigurationName: 'OnDemand Workflows'
      
      connections:
        - name: s3-raw-data
          type: S3
          properties:
            s3Uri: "s3://raw-data-bucket/incoming/"
        
        - name: spark-etl
          type: SPARK_GLUE
          properties:
            glueVersion: "4.0"
            workerType: "G.2X"
            numberOfWorkers: 10
```

**Benefits:**
- Automated creation during deployment
- Version controlled in Git
- Consistent across environments
- Repeatable infrastructure

---

## Connection Types

### S3 - Object Storage

Access S3 buckets for data storage and retrieval.

```yaml
- name: s3-data-lake
  type: S3
  properties:
    s3Uri: "s3://my-data-bucket/data/"
```

**Properties:**
- `s3Uri` (required): S3 bucket URI with optional prefix

**Use cases:**
- Raw data ingestion
- Processed data storage
- Model artifacts
- Backup and archival

**Example workflow usage:**
```yaml
tasks:
  upload_data:
    operator: "airflow.providers.amazon.aws.transfers.local_to_s3.LocalFilesystemToS3Operator"
    filename: "/tmp/data.csv"
    dest_bucket: "${proj.connection.s3_data_lake.bucket}"
    dest_key: "raw/data.csv"
```

---

### IAM - Identity and Access Management

Configure IAM settings for Glue lineage synchronization.

```yaml
- name: iam-lineage-sync
  type: IAM
  properties:
    glueLineageSyncEnabled: true
```

**Properties:**
- `glueLineageSyncEnabled` (required): Enable Glue lineage sync (`true`/`false`)

**Use cases:**
- Data lineage tracking
- Governance and compliance
- Impact analysis

---

### SPARK_GLUE - Spark on AWS Glue

Run Spark jobs on AWS Glue serverless compute.

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
- `workerType` (required): Worker type
  - `"G.1X"` - 4 vCPU, 16 GB memory
  - `"G.2X"` - 8 vCPU, 32 GB memory
  - `"G.4X"` - 16 vCPU, 64 GB memory
  - `"G.8X"` - 32 vCPU, 128 GB memory
- `numberOfWorkers` (required): Number of workers (2-100)
- `maxRetries` (optional): Maximum retries (default: 0)

**Use cases:**
- ETL transformations
- Data quality checks
- Feature engineering
- Large-scale data processing

**Example workflow usage:**
```yaml
tasks:
  transform_data:
    operator: "airflow.providers.amazon.aws.operators.glue.GlueJobOperator"
    job_name: "customer-data-transform"
    script_location: "s3://${proj.s3.root}/scripts/transform.py"
    glue_version: "${proj.connection.spark_processing.glueVersion}"
    num_of_dpus: "${proj.connection.spark_processing.numberOfWorkers}"
```

---

### ATHENA - SQL Query Engine

Execute SQL queries on data lakes using Amazon Athena.

```yaml
- name: athena-analytics
  type: ATHENA
  properties:
    workgroupName: "primary"
```

**Properties:**
- `workgroupName` (required): Athena workgroup name

**Use cases:**
- Ad-hoc SQL queries
- Data validation
- Reporting and analytics
- Data exploration

**Example workflow usage:**
```yaml
tasks:
  validate_data:
    operator: "airflow.providers.amazon.aws.operators.athena.AthenaOperator"
    query: |
      SELECT COUNT(*) as record_count 
      FROM ${proj.connection.athena.database}.processed_data
      WHERE date = '{{ ds }}'
    output_location: "s3://${proj.s3.root}/query-results/"
    workgroup: "${proj.connection.athena_analytics.workgroupName}"
```

---

### REDSHIFT - Data Warehouse

Connect to Amazon Redshift for data warehousing operations.

```yaml
- name: redshift-warehouse
  type: REDSHIFT
  properties:
    storage:
      clusterName: "analytics-cluster"
      # OR for serverless:
      # workgroupName: "analytics-workgroup"
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

**Use cases:**
- Data warehousing
- Complex analytics
- Business intelligence
- Historical data analysis

**Example workflow usage:**
```yaml
tasks:
  load_to_redshift:
    operator: "airflow.providers.amazon.aws.transfers.s3_to_redshift.S3ToRedshiftOperator"
    redshift_conn_id: "${proj.connection.redshift_warehouse.id}"
    table: "customer_data"
    s3_bucket: "${proj.s3.root}"
    s3_key: "processed/customers.csv"
    copy_options: ["CSV", "IGNOREHEADER 1"]
```

---

### SPARK_EMR - Spark on EMR

Run Spark jobs on Amazon EMR clusters or EMR Serverless.

```yaml
- name: spark-emr-processing
  type: SPARK_EMR
  properties:
    computeArn: "arn:aws:emr-serverless:us-east-1:123456789012:/applications/00abc123def456"
    runtimeRole: "arn:aws:iam::123456789012:role/EMRServerlessExecutionRole"
```

**Properties:**
- `computeArn` (required): EMR compute ARN
  - EMR Serverless: `arn:aws:emr-serverless:REGION:ACCOUNT:/applications/APP_ID`
  - EMR Cluster: `arn:aws:elasticmapreduce:REGION:ACCOUNT:cluster/CLUSTER_ID`
- `runtimeRole` (required): IAM role ARN for execution

**Use cases:**
- Large-scale Spark processing
- Machine learning with Spark MLlib
- Graph processing
- Stream processing

**Example workflow usage:**
```yaml
tasks:
  run_spark_job:
    operator: "airflow.providers.amazon.aws.operators.emr.EmrServerlessStartJobOperator"
    application_id: "${proj.connection.spark_emr_processing.applicationId}"
    execution_role_arn: "${proj.connection.spark_emr_processing.runtimeRole}"
    job_driver:
      sparkSubmit:
        entryPoint: "s3://${proj.s3.root}/scripts/process.py"
```

---

### MLFLOW - ML Experiment Tracking

Track machine learning experiments using MLflow.

```yaml
- name: mlflow-experiments
  type: MLFLOW
  properties:
    trackingServerName: "ml-tracking-server"
    trackingServerArn: "arn:aws:sagemaker:us-east-1:123456789012:mlflow-tracking-server/ml-tracking-server"
```

**Properties:**
- `trackingServerName` (required): MLflow tracking server name
- `trackingServerArn` (required): MLflow tracking server ARN

**Use cases:**
- Experiment tracking
- Model versioning
- Hyperparameter tuning
- Model comparison

**Example workflow usage:**
```yaml
tasks:
  train_model:
    operator: "airflow.operators.python.PythonOperator"
    python_callable: "train_model"
    op_kwargs:
      mlflow_tracking_uri: "${proj.connection.mlflow_experiments.trackingUri}"
      experiment_name: "customer-churn"
```

---

### WORKFLOWS_MWAA - Apache Airflow

Connect to Amazon Managed Workflows for Apache Airflow (MWAA).

```yaml
- name: mwaa-workflows
  type: WORKFLOWS_MWAA
  properties:
    mwaaEnvironmentName: "production-airflow-env"
```

**Properties:**
- `mwaaEnvironmentName` (required): MWAA environment name

**Use cases:**
- Complex workflow orchestration
- Multi-step data pipelines
- Scheduled batch processing
- Cross-service coordination

**Example workflow usage:**
```yaml
workflows:
  - workflowName: data_pipeline
    connectionName: mwaa-workflows
    engine: MWAA
    triggerPostDeployment: true
```

---

### WORKFLOWS_SERVERLESS - Serverless Airflow

Use serverless Airflow workflows (no MWAA environment required).

```yaml
- name: serverless-workflows
  type: WORKFLOWS_SERVERLESS
  properties: {}
```

**Properties:**
- No properties required (empty structure)

**Use cases:**
- Simple workflows
- Cost-optimized orchestration
- Quick prototyping
- Lightweight pipelines

**Example workflow usage:**
```yaml
workflows:
  - workflowName: simple_etl
    engine: airflow-serverless
    triggerPostDeployment: true
```

---

## Complete Example

Full manifest with multiple connection types:

```yaml
bundleName: CustomerSegmentationModel

targets:
  test:
    domain:
      name: my-domain
      region: us-east-1
    project:
      name: test-data-platform
      create: true
    
    initialization:
      project:
        create: true
        profileName: 'All capabilities'
        owners: [admin@example.com]
      
      environments:
        - EnvironmentConfigurationName: 'OnDemand Workflows'
      
      connections:
        # Storage
        - name: s3-raw-data
          type: S3
          properties:
            s3Uri: "s3://raw-data-bucket/incoming/"
        
        # Compute
        - name: spark-etl
          type: SPARK_GLUE
          properties:
            glueVersion: "4.0"
            workerType: "G.2X"
            numberOfWorkers: 10
        
        - name: spark-emr
          type: SPARK_EMR
          properties:
            computeArn: "arn:aws:emr-serverless:us-east-1:123456789012:/applications/00abc123def456"
            runtimeRole: "arn:aws:iam::123456789012:role/EMRServerlessExecutionRole"
        
        # Analytics
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
        
        # ML
        - name: ml-tracking
          type: MLFLOW
          properties:
            trackingServerName: "ml-experiments-server"
            trackingServerArn: "arn:aws:sagemaker:us-east-1:123456789012:mlflow-tracking-server/ml-experiments-server"
        
        # Orchestration
        - name: airflow-orchestration
          type: WORKFLOWS_MWAA
          properties:
            mwaaEnvironmentName: "production-airflow-env"
        
        - name: serverless-workflows
          type: WORKFLOWS_SERVERLESS
          properties: {}
        
        # Governance
        - name: iam-lineage
          type: IAM
          properties:
            glueLineageSyncEnabled: true

bundle:
  storage:
    - name: workflows
      connectionName: default.s3_shared
      include: ['workflows/']
```

---

## Using Connections in Workflows

Reference connections in your workflow files using variable substitution:

### Basic Connection Reference

```yaml
tasks:
  my_task:
    operator: "airflow.providers.amazon.aws.operators.s3.S3ListOperator"
    bucket: "${proj.connection.s3_raw_data.bucket}"
    prefix: "data/"
```

### Connection Properties

Access specific connection properties:

```yaml
# S3 connection
bucket: "${proj.connection.s3_data_lake.bucket}"
prefix: "${proj.connection.s3_data_lake.prefix}"

# Spark Glue connection
glue_version: "${proj.connection.spark_etl.glueVersion}"
worker_type: "${proj.connection.spark_etl.workerType}"
num_workers: "${proj.connection.spark_etl.numberOfWorkers}"

# Athena connection
workgroup: "${proj.connection.athena_analytics.workgroupName}"

# Redshift connection
host: "${proj.connection.redshift_dw.host}"
port: "${proj.connection.redshift_dw.port}"
database: "${proj.connection.redshift_dw.databaseName}"
```

### Connection ID

Use connection ID for Airflow operators:

```yaml
tasks:
  transfer_data:
    operator: "airflow.providers.amazon.aws.transfers.s3_to_redshift.S3ToRedshiftOperator"
    redshift_conn_id: "${proj.connection.redshift_dw.id}"
    s3_bucket: "${proj.s3.root}"
    s3_key: "data/customers.csv"
    table: "customers"
```

**See more:** [Substitutions and Variables Guide](substitutions-and-variables.md)

---

## Creating Connections via Console

For existing projects or manual setup:

1. Navigate to SageMaker Unified Studio console
2. Select your domain and project
3. Go to **Connections** tab
4. Click **Create connection**
5. Select connection type
6. Configure properties
7. Click **Create**

**When to use console:**
- Existing projects without manifest
- One-off connections
- Testing connection configurations
- Quick prototyping

**When to use manifest:**
- New project setup
- Automated deployments
- CI/CD pipelines
- Consistent environments

---

## Best Practices

### Connection Naming

Use descriptive, consistent names:
- ✅ `s3-raw-data`, `spark-etl`, `athena-analytics`
- ❌ `conn1`, `my-connection`, `test`

### Connection Organization

Group connections by purpose:
```yaml
connections:
  # Storage
  - name: s3-raw-data
  - name: s3-processed-data
  
  # Compute
  - name: spark-etl
  - name: spark-ml
  
  # Analytics
  - name: athena-queries
  - name: redshift-warehouse
```

### Environment-Specific Connections

Use different connections per environment:
```yaml
targets:
  test:
    initialization:
      connections:
        - name: redshift-warehouse
          properties:
            storage:
              clusterName: "test-cluster"
  
  prod:
    initialization:
      connections:
        - name: redshift-warehouse
          properties:
            storage:
              clusterName: "prod-cluster"
```

### Connection Documentation

Document connection requirements in your README:
```markdown
## Required Connections

- `s3-raw-data` - S3 bucket for raw data ingestion
- `spark-etl` - Glue Spark for ETL processing
- `athena-analytics` - Athena for SQL queries
```

### Testing Connections

Validate connections after creation:
```bash
# Describe project to see connections
smus-cli describe --bundle bundle.yaml --targets test --connect

# Test workflow that uses connections
smus-cli run --targets test --workflow test_connections
```

---

## Troubleshooting

### Connection Not Found

**Error:** `Connection 'my-connection' not found in project`

**Solution:**
1. Verify connection name in manifest matches exactly
2. Check connection was created: `smus-cli describe --bundle bundle.yaml --connect`
3. Ensure project initialization completed successfully

### Connection Properties Invalid

**Error:** `Invalid properties for connection type SPARK_GLUE`

**Solution:**
1. Check required properties are provided
2. Verify property values match expected types
3. Review [Bundle Manifest Reference](bundle-manifest.md#connections) for correct schema

### Connection Permission Denied

**Error:** `Access denied to connection resource`

**Solution:**
1. Verify IAM role has required permissions
2. Check project role includes connection access
3. Ensure connection resource (S3 bucket, Redshift cluster) exists

### Variable Substitution Not Working

**Error:** `${proj.connection.my_connection.property}` appears literally in workflow

**Solution:**
1. Verify connection name matches manifest
2. Check property name is correct for connection type
3. Ensure variable substitution is enabled in workflow files

---

## Next Steps

- **[Bundle Manifest Reference](bundle-manifest.md)** - Complete connection schema
- **[Substitutions and Variables](substitutions-and-variables.md)** - Variable usage guide
- **[Admin Quick Start](getting-started/admin-quickstart.md)** - Infrastructure setup
- **[CLI Commands](cli-commands.md)** - Connection management commands

---

**Questions?** See [Bundle Manifest Reference - Connections](bundle-manifest.md#connections) for complete schema details.

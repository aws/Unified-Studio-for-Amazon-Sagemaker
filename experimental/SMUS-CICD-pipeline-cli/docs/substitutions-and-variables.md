# Substitutions and Variables

← [Back to Main README](../README.md) | [Bundle Manifest Reference](bundle-manifest.md)

Dynamic variable substitution for workflow YAMLs that resolves project-specific values at deployment time.

## Overview

Variables enable **single workflow definitions** that work across all targets (dev, test, prod) without hardcoded values. The system automatically discovers project connections and resolves placeholders during deployment.

## Variable Syntax

Variables use the format: `{namespace.property.path}`

**Supported Namespaces:**
- `env` - Environment variables from manifest
- `proj` - Project properties and connections
- `stage` - Stage/target properties
- `domain` - Domain properties

## Available Variables

### Environment Variables

Access environment variables defined in your bundle manifest:

```yaml
{env.VARIABLE_NAME}
```

### Stage Properties

| Variable | Description | Example |
|----------|-------------|---------|
| `{stage.name}` | Current stage/target name | `dev`, `test`, `prod` |

### Project Properties

| Variable | Description | Example |
|----------|-------------|---------|
| `{proj.id}` | Project ID | `5vqwb22pn2da5j` |
| `{proj.name}` | Project name | `test-marketing` |
| `{proj.domain_id}` | Domain ID | `dzd-5b6m4h6c1yfch3` |
| `{proj.iam_role}` | IAM role ARN | `arn:aws:iam::123:role/ProjectRole` |
| `{proj.iam_role_arn}` | IAM role ARN (alias) | `arn:aws:iam::123:role/ProjectRole` |
| `{proj.iam_role_name}` | IAM role name only | `ProjectRole` |
| `{proj.kms_key_arn}` | KMS key ARN | `arn:aws:kms:us-east-1:123:key/abc` |

### Domain Properties

| Variable | Description | Example |
|----------|-------------|---------|
| `{domain.id}` | Domain ID | `dzd-5b6m4h6c1yfch3` |
| `{domain.name}` | Domain name | `MyDomain` |
| `{domain.region}` | Domain region | `us-east-1` |

### Connection Properties

Access any project connection using: `{proj.connection.<connection-name>.<property>}`

**Common Connections:**

| Variable | Description | Example |
|----------|-------------|---------|
| **S3 Shared** | | |
| `{proj.connection.default.s3_shared.s3Uri}` | Shared S3 bucket path | `s3://bucket/shared/` |
| `{proj.connection.default.s3_shared.bucket_name}` | Bucket name only | `bucket` |
| `{proj.connection.default.s3_shared.environmentUserRole}` | Connection IAM role | `arn:aws:iam::123:role/Role` |
| **Spark** | | |
| `{proj.connection.default.spark.glueVersion}` | Glue version | `4.0` |
| `{proj.connection.default.spark.workerType}` | Worker type | `G.1X` |
| `{proj.connection.default.spark.numberOfWorkers}` | Number of workers | `10` |
| **Athena** | | |
| `{proj.connection.default.sql.workgroupName}` | Athena workgroup | `sagemaker-studio-workgroup-abc` |
| **MLflow** | | |
| `{proj.connection.project.mlflow-server.mlflow.trackingServerArn}` | MLflow server ARN | `arn:aws:sagemaker:us-east-1:123:mlflow-tracking-server/name` |
| `{proj.connection.project.mlflow-server.mlflow.trackingServerName}` | MLflow server name | `my-mlflow-server` |

**Note:** The resolver automatically discovers ALL connections in your project. If you add a new connection, it's immediately available for use.

## Example Usage

### Before (Hardcoded)

```yaml
tasks:
  process_data:
    operator: airflow.providers.amazon.aws.operators.glue.GlueJobOperator
    script_location: 's3://hardcoded-bucket/scripts/process.py'
    iam_role_name: HardcodedRole
    region_name: us-east-1
    create_job_kwargs:
      GlueVersion: '4.0'
```

### After (Variables)

```yaml
tasks:
  process_data:
    operator: airflow.providers.amazon.aws.operators.glue.GlueJobOperator
    script_location: '{proj.connection.default.s3_shared.s3Uri}scripts/process.py'
    iam_role_name: '{proj.iam_role_name}'
    region_name: '{env.AWS_REGION}'
    create_job_kwargs:
      GlueVersion: '{proj.connection.default.spark.glueVersion}'
      Tags:
        Environment: '{stage.name}'
```

### Target-Specific Resolution

The same workflow YAML resolves differently per target:

| Variable | Dev Target | Test Target | Prod Target |
|----------|-----------|-------------|-------------|
| `{stage.name}` | `dev` | `test` | `prod` |
| `{proj.name}` | `dev-marketing` | `test-marketing` | `prod-marketing` |
| `{proj.connection.default.s3_shared.s3Uri}` | `s3://dev-bucket/` | `s3://test-bucket/` | `s3://prod-bucket/` |
| `{env.AWS_REGION}` | `us-west-2` | `us-east-1` | `us-east-1` |

## Bundle Manifest Configuration

Define environment variables in your manifest:

```yaml
stages:
  dev:
    project:
      name: dev-marketing
    environment_variables:
      AWS_REGION: us-west-2
      S3_PREFIX: dev
      
  test:
    project:
      name: test-marketing
    environment_variables:
      AWS_REGION: us-east-1
      S3_PREFIX: test
```

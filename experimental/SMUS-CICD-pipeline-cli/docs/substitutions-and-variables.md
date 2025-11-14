# Substitutions and Variables

← [Back to Main README](../README.md) | [Bundle Manifest Reference](bundle-manifest.md)

Dynamic variable substitution system for workflow YAMLs that resolves project-specific and environment values at deployment time.

## Overview

The context resolver allows workflow YAMLs to use placeholder variables that are automatically replaced with actual values from the target project during deployment. This enables:

- **Single workflow definition** works across all targets (dev, test, prod)
- **No hardcoded values** in workflow YAMLs
- **Automatic discovery** of project connections and properties
- **Type-safe resolution** with validation

## Variable Syntax

Variables use the format: `{namespace.property.path}`

### Supported Namespaces

1. **`env`** - Environment variables
2. **`proj`** - Project properties and connections

## Available Variables

### Environment Variables

Access any environment variable defined in the bundle manifest:

```yaml
{env.VARIABLE_NAME}
```

**Example:**
```yaml
region_name: '{env.AWS_REGION}'
s3_prefix: '{env.S3_PREFIX}'
```

### Project Properties

Direct project-level properties:

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `{proj.id}` | Project ID | `5vqwb22pn2da5j` |
| `{proj.name}` | Project name | `test-marketing` |
| `{proj.domain_id}` | Domain ID | `dzd-5b6m4h6c1yfch3` |
| `{proj.iam_role}` | Project IAM role ARN | `arn:aws:iam::123:role/ProjectRole` |
| `{proj.iam_role_arn}` | Project IAM role ARN (alias) | `arn:aws:iam::123:role/ProjectRole` |
| `{proj.iam_role_name}` | Project IAM role name only | `ProjectRole` |
| `{proj.kms_key_arn}` | KMS key ARN | `arn:aws:kms:us-east-1:123:key/abc` |

### Connection Properties

Access properties from any project connection using:

```yaml
{proj.connection.<connection-name>.<property>}
```

#### S3 Shared Connection (`default.s3_shared`)

| Variable | Description |
|----------|-------------|
| `{proj.connection.default.s3_shared.s3Uri}` | Shared S3 bucket path |
| `{proj.connection.default.s3_shared.environmentUserRole}` | Connection IAM role |

#### MLflow Connection (`project.mlflow-server.mlflow`)

| Variable | Description |
|----------|-------------|
| `{proj.connection.project.mlflow-server.mlflow.trackingServerArn}` | MLflow tracking server ARN |
| `{proj.connection.project.mlflow-server.mlflow.trackingServerName}` | MLflow tracking server name |

#### Spark Connection (`default.spark`)

| Variable | Description |
|----------|-------------|
| `{proj.connection.default.spark.glueVersion}` | Glue version (e.g., `4.0`) |
| `{proj.connection.default.spark.workerType}` | Worker type (e.g., `G.1X`) |
| `{proj.connection.default.spark.numberOfWorkers}` | Number of workers |

#### Athena Connection (`default.sql`)

| Variable | Description |
|----------|-------------|
| `{proj.connection.default.sql.workgroupName}` | Athena workgroup name |

## Usage Example

### Before (Hardcoded Values)

```yaml
tasks:
  covid_database_discovery:
    operator: airflow.providers.amazon.aws.operators.glue.GlueJobOperator
    script_location: 's3://demo-bucket/glue-scripts/glue_s3_list_job.py'
    iam_role_name: OverdriveExecutionRole
    region_name: us-east-1
    create_job_kwargs:
      GlueVersion: '4.0'
```

### After (Context Variables)

```yaml
tasks:
  covid_database_discovery:
    operator: airflow.providers.amazon.aws.operators.glue.GlueJobOperator
    script_location: '{proj.connection.default.s3_shared.s3Uri}etl/glue_s3_list_job.py'
    iam_role_name: '{proj.iam_role}'
    region_name: '{env.AWS_REGION}'
    create_job_kwargs:
      GlueVersion: '{proj.connection.default.spark.glueVersion}'
```

## How It Works

### 1. Deployment Time Resolution

When you run `deploy test`, the system:

1. Loads the target configuration from the bundle manifest
2. Initializes the MaxDome Project SDK for the target project
3. Queries all project connections dynamically
4. Downloads workflow YAMLs from S3
5. Resolves all `{env.*}` and `{proj.*}` variables
6. Uploads resolved YAMLs back to S3
7. Creates Overdrive workflows with resolved content

### 2. Target-Specific Values

The same workflow YAML automatically gets different values per target:

**Dev Target:**
- `{proj.name}` → `dev-marketing`
- `{proj.connection.default.s3_shared.s3Uri}` → `s3://dev-bucket/`
- `{env.AWS_REGION}` → `us-west-2`

**Test Target:**
- `{proj.name}` → `test-marketing`
- `{proj.connection.default.s3_shared.s3Uri}` → `s3://test-bucket/`
- `{env.AWS_REGION}` → `us-east-1`

### 3. Dynamic Connection Discovery

The resolver automatically discovers ALL connections in the project, not just predefined ones. If you add a new connection to your project, it's immediately available:

```yaml
# New Redshift connection added to project
script_location: '{proj.connection.my-redshift.host}'
```

## Bundle Manifest Configuration

Define environment variables in your bundle manifest:

```yaml
stages:
  test:
    project:
      name: test-marketing
    environment_variables:
      AWS_REGION: us-east-1
      S3_PREFIX: test
      CUSTOM_VAR: value
```

## Error Handling

### Missing Variables

If a variable cannot be resolved, it remains unchanged in the output:

```yaml
# Input
role: '{proj.connection.does-not-exist.role}'

# Output (if connection not found)
role: '{proj.connection.does-not-exist.role}'
```

### Invalid Syntax

Variables must follow the exact syntax `{namespace.path}`:

- ✅ `{env.AWS_REGION}`
- ✅ `{proj.iam_role}`
- ✅ `{proj.connection.default.s3_shared.s3Uri}`
- ❌ `${env.AWS_REGION}` (wrong brackets)
- ❌ `{AWS_REGION}` (missing namespace)

## Best Practices

### 1. Use Descriptive Environment Variables

```yaml
environment_variables:
  AWS_REGION: us-east-1
  GLUE_DATABASE_NAME: analytics_db
  DATA_BUCKET_PREFIX: raw-data
```

### 2. Leverage Project Connections

Instead of hardcoding S3 paths, use connection properties:

```yaml
# ✅ Good
input_path: '{proj.connection.default.s3_shared.s3Uri}input/'

# ❌ Bad
input_path: 's3://hardcoded-bucket/input/'
```

### 3. Keep Workflow YAMLs Generic

Write workflows that work for any project:

```yaml
tasks:
  process_data:
    script_location: '{proj.connection.default.s3_shared.s3Uri}scripts/process.py'
    iam_role: '{proj.iam_role}'
    region: '{env.AWS_REGION}'
    output_path: '{proj.connection.default.s3_shared.s3Uri}output/'
```

### 4. Document Required Connections

In your workflow README, document which connections are required:

```markdown
## Required Connections

This workflow requires the following project connections:

- `default.s3_shared` - For script storage and output
- `default.spark` - For Glue job configuration
- `project.mlflow-server.mlflow` - For experiment tracking
```

## Implementation Details

### Context Resolver Class

Located in: `src/smus_cicd/helpers/context_resolver.py`

## Pipeline Test Configuration

When running `smus test`, a configuration file `.smus_test_config.json` is created in the test folder with resolved project context:

```json
{
  "region": "us-east-1",
  "project_id": "4pg255jku47vdz",
  "project_name": "test-marketing",
  "domain_id": "dzd-5b6m4h6c1yfch3",
  "domain_name": "BETA_10282025_Domain",
  "target_name": "test",
  "iam_role": "arn:aws:iam::123456789:role/ProjectRole",
  "iam_role_arn": "arn:aws:iam::123456789:role/ProjectRole",
  "iam_role_name": "ProjectRole",
  "kms_key_arn": "arn:aws:kms:us-east-1:123456789:key/abc",
  "connections": {
    "default.s3_shared": {
      "s3Uri": "s3://bucket/shared/",
      "bucket_name": "bucket",
      "environmentUserRole": "arn:aws:iam::123:role/Role"
    },
    "default.spark": {
      "sparkGlueProperties": {...}
    }
  },
  "env": {
    "AWS_REGION": "us-east-1"
  }
}
```

Access in tests via the `smus_config` fixture (provided by `conftest.py`):

```python
def test_example(smus_config):
    region = smus_config['region']
    project_id = smus_config['project_id']
    s3_uri = smus_config['connections']['default.s3_shared']['s3Uri']
```

```python
from sagemaker_studio.project import Project
from smus_cicd.helpers.context_resolver import ContextResolver

# Initialize with project
project = Project(name="test-marketing", domain_id="dzd-123")
resolver = ContextResolver(project, env_vars={"AWS_REGION": "us-east-1"})

# Resolve content
yaml_content = "role: '{proj.iam_role}'"
resolved = resolver.resolve(yaml_content)
# Output: "role: 'arn:aws:iam::123:role/ProjectRole'"
```

### Integration with Deploy Command

The deploy command automatically applies context resolution:

```python
# In deploy.py
from sagemaker_studio.project import Project
from ..helpers.context_resolver import ContextResolver

project = Project(name=project_name, domain_id=domain_id)
resolver = ContextResolver(project, env_vars=target_config.environment_variables)

# Download, resolve, upload workflow YAML
resolved_content = resolver.resolve(original_content)
```

## Testing

Unit tests: `tests/unit/test_context_resolver.py`

```bash
pytest tests/unit/test_context_resolver.py -v
```

## Future Enhancements

Potential additions:

1. **Conditional resolution**: `{proj.connection.optional?.property}`
2. **Default values**: `{env.VAR:default_value}`
3. **Nested references**: `{proj.connection.{env.CONN_NAME}.property}`
4. **Validation mode**: Pre-deployment check for missing variables
5. **Custom functions**: `{upper(proj.name)}`, `{concat(proj.s3.root, '/data')}`

## Troubleshooting

### Variable Not Resolving

1. Check variable syntax matches exactly: `{namespace.property}`
2. Verify connection exists in project: `smus describe --bundle manifest.yaml --connect`
3. Check environment variable is defined in bundle manifest
4. Review deploy logs for resolution errors

### Connection Property Not Found

1. List all connections: `smus describe --bundle manifest.yaml --connect`
2. Check connection type matches expected properties
3. Verify connection is in READY status
4. Check property name spelling (case-sensitive)

### Wrong Value After Resolution

1. Verify you're deploying to correct target
2. Check target configuration in bundle manifest
3. Confirm project has correct connections configured
4. Review resolved YAML in S3 after deployment

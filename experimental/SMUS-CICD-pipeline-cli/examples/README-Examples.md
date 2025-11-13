# SMUS CICD Pipeline Examples

This directory contains two versions of the DemoMarketingPipeline to demonstrate different deployment approaches:

## Examples Overview

### 1. DemoMarketingPipeline-MWAA.yaml
**Traditional MWAA-based pipeline**
- Uses Amazon Managed Workflows for Apache Airflow (MWAA)
- Traditional Python DAG files
- Complex project initialization with environments
- Connection-based workflow execution

**Key Features:**
- `engine: MWAA` in workflows section
- `connectionName: project.workflow_mwaa`
- Full environment configuration
- Traditional Airflow Python DAGs

### 2. DemoMarketingPipeline-Serverless.yaml
**Modern Airflow Serverless pipeline**
- Uses Amazon Airflow Serverless (Overdrive)
- YAML-based DAG definitions with environment variables
- Simplified project initialization
- Serverless workflow execution

**Key Features:**
- `engine: airflow-serverless` in workflows section
- `airflow-serverless: true` in bundle configuration
- Environment variables support (`${ENV_NAME}`, `${S3_PREFIX}`, `${LOG_LEVEL}`)
- YAML DAG definitions with parameter substitution

## File Structure

```
examples/
├── DemoMarketingPipeline-MWAA.yaml      # MWAA bundle manifest
├── DemoMarketingPipeline-Serverless.yaml # Serverless bundle manifest
├── workflows-mwaa/
│   └── dags/
│       └── sample_dag.py                 # Traditional Python DAG
├── workflows-serverless/
│   └── dags/
│       └── marketing_dag.yaml            # YAML DAG with env vars
├── src/
│   └── marketing_utils.py                # Shared utilities
├── run-mwaa-example.sh                   # MWAA example runner
└── run-serverless-example.sh             # Serverless example runner
```

## Running the Examples

### MWAA Example
```bash
./run-mwaa-example.sh
```

### Serverless Example
```bash
./run-serverless-example.sh
```

## Key Differences

| Feature | MWAA | Serverless |
|---------|------|------------|
| Engine | MWAA | airflow-serverless |
| DAG Format | Python (.py) | YAML (.yaml) |
| Environment Variables | Manual | Built-in (`${VAR}`) |
| Project Setup | Complex | Simplified |
| Scaling | Manual | Automatic |
| Cost Model | Always-on | Pay-per-use |

## Environment Variables (Serverless Only)

The serverless version demonstrates environment variable usage:

- `ENV_NAME`: Environment identifier (dev/test/prod)
- `S3_PREFIX`: Environment-specific S3 prefix
- `LOG_LEVEL`: Logging level per environment

These variables are automatically resolved during deployment based on the target configuration.

## Migration Path

To migrate from MWAA to Serverless:

1. Convert Python DAGs to YAML format
2. Add `airflow-serverless: true` to bundle configuration
3. Update workflows section to use `engine: airflow-serverless`
4. Add environment variables to target configurations
5. Simplify project initialization (remove complex environments)
6. Update DAG references to use environment variables

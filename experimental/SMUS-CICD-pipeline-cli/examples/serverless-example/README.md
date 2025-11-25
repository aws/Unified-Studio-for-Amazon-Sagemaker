# Serverless Marketing Pipeline Example

Modern Amazon Airflow Serverless (Overdrive) pipeline example with environment variables.

## Files
- `DemoMarketingPipeline-Serverless.yaml` - Pipeline manifest
- `workflows/dags/marketing_dag.yaml` - YAML DAG with environment variables
- `src/marketing_utils.py` - Shared utilities
- `run-serverless-example.sh` - Quick example runner
- `full-lifecycle-serverless.sh` - Complete lifecycle demo

## Features
- Airflow Serverless engine
- YAML DAG definitions
- Environment variables (`${ENV_NAME}`, `${S3_PREFIX}`, `${LOG_LEVEL}`)
- Simplified project initialization
- Pay-per-use serverless model

## Usage

### Quick Example
```bash
./run-serverless-example.sh
```

### Full Lifecycle Demo
```bash
./full-lifecycle-serverless.sh
```

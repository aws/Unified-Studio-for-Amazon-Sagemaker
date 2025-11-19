# Testing Infrastructure

Deploys core infrastructure for SMUS integration testing.

## What Gets Deployed

- **MLflow Tracking Server** - SageMaker managed MLflow server
- **S3 Artifacts Bucket** - Versioned bucket for MLflow artifacts  
- **SageMaker Execution Role** - IAM role with MLflow permissions

## Usage

```bash
# Deploy to us-east-1 (default)
./deploy.sh

# Deploy to specific region
./deploy.sh us-west-2
```

## CloudFormation Templates

- `shared-resources-template.yaml` - MLflow server and IAM roles
- `testing-resources-template.yaml` - Additional test resources (Redshift, Glue)
- `redshift-serverless-template.yaml` - Standalone Redshift setup

## Outputs

Saved to `/tmp/`:
- `mlflow_arn_{region}.txt` - MLflow tracking server ARN
- `sagemaker_role_arn_{region}.txt` - SageMaker execution role ARN
- `mlflow_bucket_{region}.txt` - S3 bucket name

## Stack Name

`smus-shared-resources` (per region)

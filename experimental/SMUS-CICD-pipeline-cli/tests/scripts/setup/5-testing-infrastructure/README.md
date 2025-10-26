# Stage 5: Testing Infrastructure

Deploys shared testing resources for SMUS integration tests.

## What Gets Deployed

1. **MLflow Tracking Server** - SageMaker MLflow tracking server
2. **SageMaker Execution Role** - IAM role with MLflow permissions
3. **S3 Artifacts Bucket** - Versioned bucket for MLflow artifacts

## Usage

```bash
./deploy.sh [path/to/config.yaml]
```

## Prerequisites

- AWS account with SageMaker permissions
- S3 bucket name must be globally unique (auto-generated: `smus-mlflow-artifacts-{AccountId}-{Region}`)

## CloudFormation Stack Created

- `smus-shared-resources` - MLflow server, role, and bucket (per region)

## Outputs

Saved to `/tmp/`:
- `mlflow_arn_<region>.txt` - MLflow tracking server ARN
- `sagemaker_role_arn_<region>.txt` - SageMaker execution role ARN
- `mlflow_bucket_<region>.txt` - S3 bucket name

## Use in Tests

```python
# Read MLflow ARN
with open('/tmp/mlflow_arn_us-east-1.txt') as f:
    MLFLOW_ARN = f.read().strip()

# Use in your tests
mlflow.set_tracking_uri(f"aws://{MLFLOW_ARN}")
```

## Test Data Setup Scripts

This folder also contains COVID-19 test data setup scripts:
- `download-covid-data.py` - Download COVID-19 dataset
- `setup-covid-data.py` - Set up DataZone data sources
- `publish-covid-assets.py` - Publish assets to catalog
- `publish-all-covid-tables.py` - Publish all tables
- `verify-all-covid-listings.py` - Verify published listings
- `set-covid-assets-no-approval.py` - Configure auto-approval
- `fix-datasource-covid.py` - Fix data source issues
- `update-datasource-covid.py` - Update data source configuration

## MLflow Server Configuration

- **Size:** Small (configurable in template)
- **Automatic Model Registration:** Enabled
- **Artifact Storage:** S3 with versioning

## Independent Usage

This stage can be run independently of other stages for testing purposes.

## Future Enhancements

Planned additions:
- Serverless Redshift cluster
- Lake Formation configuration
- RDS test databases
- DynamoDB tables

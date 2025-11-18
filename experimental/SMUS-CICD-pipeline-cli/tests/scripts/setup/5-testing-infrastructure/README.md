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

### COVID-19 Test Data
- `download-covid-data.py` - Download COVID-19 dataset
- `setup-covid-data.py` - Set up DataZone data sources
- `publish-covid-assets.py` - Publish assets to catalog
- `publish-all-covid-tables.py` - Publish all tables
- `verify-all-covid-listings.py` - Verify published listings
- `set-covid-assets-no-approval.py` - Configure auto-approval
- `fix-datasource-covid.py` - Fix data source issues
- `update-datasource-covid.py` - Update data source configuration

### ML Workflow Test Data
- `setup-ml-resources.py` - Setup ML workflow testing resources

**Usage:**
```bash
# Setup ML resources in us-east-1
./setup-ml-resources.py --region us-east-1

# Setup ML resources in us-west-2
./setup-ml-resources.py --region us-west-2

# Custom bucket name
./setup-ml-resources.py --region us-east-1 --bucket my-custom-bucket
```

**What it creates:**
- S3 bucket: `demo-bucket-smus-ml-{region}`
- Training data: `s3://{bucket}/training-data/training_data.csv` (1000 samples, 20 features)
- Inference data: `s3://{bucket}/inference-data/inference_data.csv` (100 samples, 20 features)
- Training code: `s3://{bucket}/training_code.tar.gz` (packaged SageMaker training script)

**Output:**
- `/tmp/ml_bucket_{region}.txt` - Bucket name for use in tests

## MLflow Server Configuration

- **Size:** Small (configurable in template)
- **Automatic Model Registration:** Enabled
- **Artifact Storage:** S3 with versioning

## Independent Usage

This stage can be run independently of other stages for testing purposes.

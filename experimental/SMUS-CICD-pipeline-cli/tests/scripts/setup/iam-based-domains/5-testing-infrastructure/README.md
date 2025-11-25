# Stage 5: Testing Infrastructure and Data

Deploys infrastructure and test data for SMUS integration testing.

## Structure

### testing-infrastructure/
Core infrastructure (MLflow, IAM roles, S3 buckets)

```bash
cd testing-infrastructure
./deploy.sh [region]
```

### testing-data/
Test datasets (ML training/inference data, COVID-19 catalog data)

```bash
cd testing-data
./deploy.sh [region]
```

## Quick Start

```bash
# Deploy infrastructure first
cd testing-infrastructure && ./deploy.sh us-east-1

# Then deploy test data
cd ../testing-data && ./deploy.sh us-east-1
```

## What Gets Deployed

**Infrastructure:**
- MLflow tracking server
- SageMaker execution role
- S3 artifacts bucket

**Data:**
- ML training/inference datasets
- COVID-19 test data (optional)

## Outputs

All outputs saved to `/tmp/` for use in integration tests.

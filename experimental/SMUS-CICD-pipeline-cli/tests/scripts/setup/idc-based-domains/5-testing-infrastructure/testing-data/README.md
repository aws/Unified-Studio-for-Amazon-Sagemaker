# Testing Data

Deploys test datasets for SMUS integration testing.

## What Gets Deployed

### ML Test Data (Always)
- S3 bucket: `demo-bucket-smus-ml-{region}`
- Training data: 1000 samples, 20 features (CSV)
- Inference data: 100 samples, 20 features (CSV)
- Training code: Packaged SageMaker script (tar.gz)

### COVID-19 Test Data (Optional)
- COVID-19 dataset (8 CSV files)
- DataZone data sources and connections
- Published catalog assets

## Usage

```bash
# Deploy to us-east-1 (default)
./deploy.sh

# Deploy to specific region
./deploy.sh us-west-2
```

The script will:
1. Always deploy ML test data
2. Prompt for COVID-19 data setup (requires DataZone domain)

## Manual Setup

### ML Data Only
```bash
python3 setup-ml-resources.py --region us-east-1
```

### COVID Data (requires DataZone)
```bash
# Download dataset
python3 download-covid-data.py

# Setup data sources
python3 setup-covid-data.py

# Publish to catalog
python3 publish-all-covid-tables.py

# Verify
python3 verify-all-covid-listings.py
```

## Outputs

Saved to `/tmp/`:
- `ml_bucket_{region}.txt` - ML test data bucket name

## COVID Data Management Scripts

- `download-covid-data.py` - Download COVID-19 dataset
- `setup-covid-data.py` - Create DataZone data sources
- `publish-covid-assets.py` - Publish individual assets
- `publish-all-covid-tables.py` - Batch publish all tables
- `verify-all-covid-listings.py` - Verify published listings
- `set-covid-assets-no-approval.py` - Configure auto-approval
- `update-datasource-covid.py` - Update data source config
- `fix-datasource-covid.py` - Fix data source issues

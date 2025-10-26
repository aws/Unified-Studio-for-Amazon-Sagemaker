#!/bin/bash

# Package deployment orchestrator code for SageMaker training job
# Usage: ./package_deploy_orchestrator_code.sh [region]

REGION=${1:-us-west-2}
BUCKET="demo-bucket-smus-ml-${REGION}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📦 Packaging deployment orchestrator code for SageMaker training job..."

# Create temporary directory
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# Copy orchestrator script
cp "$SCRIPT_DIR/sagemaker_deploy_orchestrator.py" "$TEMP_DIR/"

# Create tar.gz package
tar -czf deploy_orchestrator_code.tar.gz sagemaker_deploy_orchestrator.py

# Upload to S3
echo "⬆️ Uploading deploy_orchestrator_code.tar.gz to s3://$BUCKET/"
aws s3 cp deploy_orchestrator_code.tar.gz "s3://$BUCKET/deploy_orchestrator_code.tar.gz" --region "$REGION"

# Cleanup
cd "$SCRIPT_DIR"
rm -rf "$TEMP_DIR"

echo "✅ Deployment orchestrator code packaged and uploaded successfully!"
echo "📍 Location: s3://$BUCKET/deploy_orchestrator_code.tar.gz"

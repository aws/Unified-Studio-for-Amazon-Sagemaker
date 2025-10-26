#!/bin/bash

# Package orchestrator code for SageMaker training job
# Usage: ./package_orchestrator_code.sh [region]

REGION=${1:-us-west-2}
BUCKET="demo-bucket-smus-ml-${REGION}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMP_DIR="/tmp/sagemaker_orchestrator_package"

echo "📦 Packaging orchestrator code for SageMaker training job..."

# Clean and create temp directory
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

# Copy orchestrator script to temp directory
cp "$SCRIPT_DIR/sagemaker_ml_orchestrator.py" "$TEMP_DIR/"

# Create tar.gz package
cd "$TEMP_DIR"
tar -czf orchestrator_code.tar.gz sagemaker_ml_orchestrator.py

# Upload to S3
echo "⬆️ Uploading orchestrator_code.tar.gz to s3://$BUCKET/"
aws s3 cp orchestrator_code.tar.gz "s3://$BUCKET/orchestrator_code.tar.gz" --region "$REGION"

if [ $? -eq 0 ]; then
    echo "✅ Orchestrator code packaged and uploaded successfully!"
    echo "📍 Location: s3://$BUCKET/orchestrator_code.tar.gz"
else
    echo "❌ Failed to upload orchestrator code"
    exit 1
fi

# Cleanup
rm -rf "$TEMP_DIR"

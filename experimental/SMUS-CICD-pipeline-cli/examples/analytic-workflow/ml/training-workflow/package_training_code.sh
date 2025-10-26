#!/bin/bash

# Package and upload training code for SageMaker workflows
# Usage: ./package_training_code.sh [region]

REGION=${1:-us-west-2}
BUCKET="demo-bucket-smus-ml-${REGION}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMP_DIR="/tmp/sagemaker_training_package"

echo "📦 Packaging training code for SageMaker workflow..."

# Clean and create temp directory
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

# Copy training script to temp directory
cp "$SCRIPT_DIR/sagemaker_training_script.py" "$TEMP_DIR/"

# Create tar.gz package
cd "$TEMP_DIR"
tar -czf training_code.tar.gz sagemaker_training_script.py

# Upload to S3
echo "⬆️ Uploading training_code.tar.gz to s3://$BUCKET/"
aws s3 cp training_code.tar.gz "s3://$BUCKET/training_code.tar.gz" --region "$REGION"

if [ $? -eq 0 ]; then
    echo "✅ Training code packaged and uploaded successfully!"
    echo "📍 Location: s3://$BUCKET/training_code.tar.gz"
else
    echo "❌ Failed to upload training code"
    exit 1
fi

# Cleanup
rm -rf "$TEMP_DIR"

#!/bin/bash

echo "=== MLflow Tracking Server URL Generator ==="
echo

# Generate presigned URL for MLflow UI
echo "Generating MLflow UI presigned URL (valid for 5 minutes)..."
MLFLOW_URL=$(aws sagemaker create-presigned-mlflow-tracking-server-url \
    --tracking-server-name wine-classification-mlflow-v2 \
    --expires-in-seconds 300 \
    --region us-east-1 \
    --query 'AuthorizedUrl' \
    --output text)

if [ $? -eq 0 ]; then
    echo "✅ MLflow UI URL: $MLFLOW_URL"
    echo "Note: This URL expires in 5 minutes. Re-run this script to generate a new one."
else
    echo "❌ Failed to generate MLflow URL. Check your AWS credentials and tracking server name."
fi

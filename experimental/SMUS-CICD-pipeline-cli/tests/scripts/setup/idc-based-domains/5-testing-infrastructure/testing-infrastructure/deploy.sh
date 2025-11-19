#!/bin/bash

# Deploy MLflow and testing infrastructure
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${1:-us-east-1}"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
STACK_NAME="smus-shared-resources"
S3_BUCKET_NAME="smus-mlflow-artifacts-${ACCOUNT_ID}-${REGION}"
TRACKING_SERVER_NAME="smus-integration-mlflow"

echo "=== Deploying Testing Infrastructure ==="
echo "Account: $ACCOUNT_ID"
echo "Region: $REGION"
echo "Stack: $STACK_NAME"

# Deploy MLflow stack
aws cloudformation deploy \
    --template-file "$SCRIPT_DIR/shared-resources-template.yaml" \
    --stack-name "$STACK_NAME" \
    --parameter-overrides \
        S3BucketName="$S3_BUCKET_NAME" \
        TrackingServerName="$TRACKING_SERVER_NAME" \
        TrackingServerSize="Small" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION"

# Get outputs
MLFLOW_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`MLflowTrackingServerArn`].OutputValue' \
    --output text)

EXECUTION_ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`SageMakerExecutionRoleArn`].OutputValue' \
    --output text)

echo "✅ Deployment complete!"
echo "MLflow ARN: $MLFLOW_ARN"
echo "SageMaker Role: $EXECUTION_ROLE_ARN"
echo "S3 Bucket: $S3_BUCKET_NAME"

# Save outputs
mkdir -p /tmp
echo "$MLFLOW_ARN" > "/tmp/mlflow_arn_${REGION}.txt"
echo "$EXECUTION_ROLE_ARN" > "/tmp/sagemaker_role_arn_${REGION}.txt"
echo "$S3_BUCKET_NAME" > "/tmp/mlflow_bucket_${REGION}.txt"

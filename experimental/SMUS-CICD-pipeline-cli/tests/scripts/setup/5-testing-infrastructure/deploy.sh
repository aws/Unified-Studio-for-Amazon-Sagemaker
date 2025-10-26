#!/bin/bash

# Deploy shared resources for SMUS integration testing
# This includes MLflow tracking server and associated IAM roles

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${1:-$SCRIPT_DIR/config.yaml}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.yaml not found at $CONFIG_FILE"
    exit 1
fi

# Function to deploy shared resources in a specific region
deploy_shared_resources_in_region() {
    local region=$1
    local stack_suffix=$2
    
    echo "=== Deploying Shared Resources in region: $region ==="
    
    # Stack name for this region
    STACK_NAME="smus-shared-resources${stack_suffix}"
    
    # Generate unique S3 bucket name
    S3_BUCKET_NAME="smus-mlflow-artifacts-${ACCOUNT_ID}-${region}"
    TRACKING_SERVER_NAME="smus-integration-mlflow${stack_suffix}"
    
    # Check if stack exists
    STACK_STATUS=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$region" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "DOES_NOT_EXIST")
    
    if [ "$STACK_STATUS" = "ROLLBACK_COMPLETE" ]; then
        echo "Stack $STACK_NAME is in ROLLBACK_COMPLETE state. Deleting..."
        aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$region"
        echo "Waiting for stack deletion to complete..."
        aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$region"
        echo "Stack deleted successfully."
    elif [ "$STACK_STATUS" != "DOES_NOT_EXIST" ]; then
        echo "Stack $STACK_NAME already exists with status: $STACK_STATUS"
        echo "Updating stack..."
    fi
    
    # Deploy shared resources stack
    echo "Deploying shared resources stack: $STACK_NAME in $region..."
    if aws cloudformation deploy \
        --template-file "$SCRIPT_DIR/shared-resources-template.yaml" \
        --stack-name "$STACK_NAME" \
        --parameter-overrides \
            S3BucketName="$S3_BUCKET_NAME" \
            TrackingServerName="$TRACKING_SERVER_NAME" \
            TrackingServerSize="Small" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$region"; then
        
        echo "✅ Shared resources stack deployment complete in $region!"
        
        # Get stack outputs
        MLFLOW_ARN=$(aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --region "$region" \
            --query 'Stacks[0].Outputs[?OutputKey==`MLflowTrackingServerArn`].OutputValue' \
            --output text)
        
        EXECUTION_ROLE_ARN=$(aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --region "$region" \
            --query 'Stacks[0].Outputs[?OutputKey==`SageMakerExecutionRoleArn`].OutputValue' \
            --output text)
        
        echo "MLflow Tracking Server ARN: $MLFLOW_ARN"
        echo "SageMaker Execution Role ARN: $EXECUTION_ROLE_ARN"
        echo "S3 Artifacts Bucket: $S3_BUCKET_NAME"
        
        # Store outputs for later use
        echo "$MLFLOW_ARN" > "/tmp/mlflow_arn_${region}.txt"
        echo "$EXECUTION_ROLE_ARN" > "/tmp/sagemaker_role_arn_${region}.txt"
        echo "$S3_BUCKET_NAME" > "/tmp/mlflow_bucket_${region}.txt"
        
    else
        echo "❌ Shared resources stack deployment failed in $region!"
        exit 1
    fi
}

# Parse config
ACCOUNT_ID=$(yq '.account_id' "$CONFIG_FILE")
PRIMARY_REGION=$(yq '.regions.primary.name' "$CONFIG_FILE")
PRIMARY_ENABLED=$(yq '.regions.primary.enabled' "$CONFIG_FILE")
SECONDARY_REGION=$(yq '.regions.secondary.name // ""' "$CONFIG_FILE")
SECONDARY_ENABLED=$(yq '.regions.secondary.enabled // false' "$CONFIG_FILE")
TERTIARY_REGION=$(yq '.regions.tertiary.name // ""' "$CONFIG_FILE")
TERTIARY_ENABLED=$(yq '.regions.tertiary.enabled // false' "$CONFIG_FILE")

echo "=== Shared Resources Deployment for SMUS Integration Testing ==="
echo "Account ID: $ACCOUNT_ID"
echo "Primary Region: $PRIMARY_REGION (enabled: $PRIMARY_ENABLED)"
echo "Secondary Region: ${SECONDARY_REGION:-'Not configured'} (enabled: $SECONDARY_ENABLED)"
echo "Tertiary Region: ${TERTIARY_REGION:-'Not configured'} (enabled: $TERTIARY_ENABLED)"
echo

# Deploy shared resources in primary region if enabled
if [ "$PRIMARY_ENABLED" = "true" ]; then
    deploy_shared_resources_in_region "$PRIMARY_REGION" ""
fi

# Deploy shared resources in secondary region if enabled
if [ "$SECONDARY_ENABLED" = "true" ] && [ -n "$SECONDARY_REGION" ]; then
    deploy_shared_resources_in_region "$SECONDARY_REGION" "-region2"
fi

# Deploy shared resources in tertiary region if enabled
if [ "$TERTIARY_ENABLED" = "true" ] && [ -n "$TERTIARY_REGION" ]; then
    deploy_shared_resources_in_region "$TERTIARY_REGION" "-region3"
fi

echo
echo "=== Shared Resources Deployment Complete! ==="
echo "MLflow tracking servers and SageMaker execution roles are now available."
echo
echo "Next steps:"
echo "1. Update your test configurations with the MLflow ARNs"
echo "2. Use the SageMaker execution role ARNs for SageMaker jobs"
echo "3. Reference the S3 buckets for MLflow artifacts"

#!/bin/bash

set -e

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${1:-$SCRIPT_DIR/config.yaml}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config file not found at $CONFIG_FILE"
    exit 1
fi

# Parse config - use domain region for GitHub role deployment
ACCOUNT_ID=$(yq '.account_id' "$CONFIG_FILE")
REGION=$(yq '.regions.primary.name' "$CONFIG_FILE")
STACK_NAME="smus-cli-github-integration"
TEMPLATE_FILE="$SCRIPT_DIR/github-oidc-role.yaml"

echo "Deploying GitHub OIDC integration stack..."
echo "Account ID: $ACCOUNT_ID"
echo "Region: $REGION"

# Check if stack exists and is in ROLLBACK_COMPLETE state
STACK_STATUS=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DOES_NOT_EXIST")

if [ "$STACK_STATUS" = "ROLLBACK_COMPLETE" ]; then
    echo "Stack $STACK_NAME is in ROLLBACK_COMPLETE state. Deleting..."
    aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"
    echo "Waiting for stack deletion to complete..."
    aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$REGION"
    echo "Stack cleanup completed."
fi

aws cloudformation deploy \
    --template-file "$TEMPLATE_FILE" \
    --stack-name "$STACK_NAME" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    --parameter-overrides \
        GitHubOrg="${GITHUB_ORG:-aws}" \
        GitHubRepo="${GITHUB_REPO:-Unified-Studio-for-Amazon-Sagemaker}" \
        GitHubEnvironment="${GITHUB_ENVIRONMENT:-aws-env}"

echo "✅ GitHub OIDC integration stack deployment complete!"

# Get the role ARN
ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`RoleArn`].OutputValue' \
    --output text)

echo "GitHub Actions Role ARN: $ROLE_ARN"
echo "Add this to your GitHub repository secrets as AWS_ROLE_ARN"

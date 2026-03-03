#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

TARGET_ACCOUNT="004878717744"
REGION="us-east-2"
STACK_NAME="DataZone-IAM-Roles"

echo "=== Deploying IAM Roles directly to account $TARGET_ACCOUNT ==="

# Assume role in target account
CREDS=$(aws sts assume-role \
  --role-arn "arn:aws:iam::$TARGET_ACCOUNT:role/OrganizationAccountAccessRole" \
  --role-session-name "DeployIAMRoles" \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text)

export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | awk '{print $1}')
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | awk '{print $2}')
export AWS_SESSION_TOKEN=$(echo "$CREDS" | awk '{print $3}')

# Deploy IAM roles stack
aws cloudformation create-stack \
  --stack-name "$STACK_NAME" \
  --template-body file://"$PROJECT_ROOT/templates/cloudformation/03-project-account/iam-roles.yaml" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION"

echo "Waiting for stack creation..."
aws cloudformation wait stack-create-complete \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

echo "✅ IAM Roles deployed successfully!"

# Get outputs
OUTPUTS=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs' \
  --output json)

echo ""
echo "Outputs:"
echo "$OUTPUTS" | jq -r '.[] | "\(.OutputKey): \(.OutputValue)"'

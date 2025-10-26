#!/bin/bash

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${1:-$SCRIPT_DIR/config.yaml}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.yaml not found at $CONFIG_FILE"
    exit 1
fi

# Parse config using yq (install with: brew install yq)
ACCOUNT_ID=$(yq '.account_id' "$CONFIG_FILE")
REGION=$(yq '.regions.primary.name' "$CONFIG_FILE")
DOMAIN_STACK_NAME=$(yq '.stacks.domain' "$CONFIG_FILE")
DOMAIN_NAME=$(yq '.domain_name' "$CONFIG_FILE")

# Check if stack exists and is in ROLLBACK_COMPLETE state
STACK_STATUS=$(aws cloudformation describe-stacks --stack-name "$DOMAIN_STACK_NAME" --region "$REGION" --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DOES_NOT_EXIST")

if [ "$STACK_STATUS" = "ROLLBACK_COMPLETE" ]; then
    echo "Stack $DOMAIN_STACK_NAME is in ROLLBACK_COMPLETE state. Deleting..."
    aws cloudformation delete-stack --stack-name "$DOMAIN_STACK_NAME" --region "$REGION"
    echo "Waiting for stack deletion to complete..."
    aws cloudformation wait stack-delete-complete --stack-name "$DOMAIN_STACK_NAME" --region "$REGION"
    echo "Stack deleted successfully."
fi

# Deploy DataZone Domain Stack
echo "Deploying DataZone Domain Stack..."
if aws cloudformation deploy \
  --template-file "$SCRIPT_DIR/sagemaker-domain.yaml" \
  --stack-name "$DOMAIN_STACK_NAME" \
  --parameter-overrides \
    DomainName="$DOMAIN_NAME" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION"; then
  echo "✅ DataZone domain stack deployment complete!"
else
  echo "❌ DataZone domain stack deployment failed!"
  exit 1
fi

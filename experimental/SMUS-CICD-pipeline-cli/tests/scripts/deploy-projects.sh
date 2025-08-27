#!/bin/bash

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.yaml not found at $CONFIG_FILE"
    exit 1
fi

# Parse config
REGION=$(yq '.region' "$CONFIG_FILE")
DOMAIN_STACK_NAME=$(yq '.stacks.domain' "$CONFIG_FILE")
BLUEPRINTS_STACK_NAME=$(yq '.stacks.blueprints_profiles' "$CONFIG_FILE")

DEV_PROJECT_NAME=$(yq '.projects.dev.name' "$CONFIG_FILE")
DEV_PROJECT_DESC=$(yq '.projects.dev.description' "$CONFIG_FILE")

echo "Deploying DataZone Dev Project..."
echo "Region: $REGION"
echo "Domain Stack: $DOMAIN_STACK_NAME"
echo "Blueprints Stack: $BLUEPRINTS_STACK_NAME"

# Check if stack exists and is in ROLLBACK_COMPLETE state
PROJECT_STACK_NAME="datazone-project-dev"
STACK_STATUS=$(aws cloudformation describe-stacks --stack-name "$PROJECT_STACK_NAME" --region "$REGION" --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DOES_NOT_EXIST")

if [ "$STACK_STATUS" = "ROLLBACK_COMPLETE" ]; then
    echo "Stack $PROJECT_STACK_NAME is in ROLLBACK_COMPLETE state. Deleting..."
    aws cloudformation delete-stack --stack-name "$PROJECT_STACK_NAME" --region "$REGION"
    echo "Waiting for stack deletion to complete..."
    aws cloudformation wait stack-delete-complete --stack-name "$PROJECT_STACK_NAME" --region "$REGION"
    echo "Stack deleted successfully."
fi

# Deploy Dev Project Only
echo ""
echo "=== Deploying Dev Project: $DEV_PROJECT_NAME ==="
aws cloudformation deploy \
  --template-file ../../cloudformation/single-project.yaml \
  --stack-name "datazone-project-dev" \
  --parameter-overrides \
    DomainStackName="$DOMAIN_STACK_NAME" \
    BlueprintsProfilesStackName="$BLUEPRINTS_STACK_NAME" \
    ProjectName="$DEV_PROJECT_NAME" \
    ProjectDescription="$DEV_PROJECT_DESC" \
  --capabilities CAPABILITY_IAM \
  --region "$REGION"

if [ $? -eq 0 ]; then
    echo "✅ Dev project stack deployed successfully"
    echo ""
    echo "🎉 Dev project deployment complete!"
    echo ""
    echo "Stack Name: datazone-project-dev"
    echo ""
    echo "Note: Test and Prod projects will be created by the CLI when needed."
else
    echo "❌ Dev project stack deployment failed"
    exit 1
fi

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
BLUEPRINTS_STACK_NAME=$(yq '.stacks.blueprints_profiles' "$CONFIG_FILE")
DOMAIN_STACK_NAME=$(yq '.stacks.domain' "$CONFIG_FILE")

# Get VPC information from config
VPC_ID=$(yq '.VPC.VpcId' "$CONFIG_FILE")

# Dynamically retrieve subnets and AZs for the VPC
echo "Retrieving subnets and AZs for VPC: $VPC_ID"
SUBNETS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --region "$REGION" --query 'Subnets[].SubnetId' --output text | tr '\t' ',')
AVAILABILITY_ZONES=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --region "$REGION" --query 'Subnets[].AvailabilityZone' --output text | tr '\t' ',')

echo "VPC ID: $VPC_ID"
echo "Subnets: $SUBNETS"
echo "Availability Zones: $AVAILABILITY_ZONES"

# Check if stack exists and is in ROLLBACK_COMPLETE or ROLLBACK_FAILED state
STACK_STATUS=$(aws cloudformation describe-stacks --stack-name "$BLUEPRINTS_STACK_NAME" --region "$REGION" --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DOES_NOT_EXIST")

if [ "$STACK_STATUS" = "ROLLBACK_COMPLETE" ] || [ "$STACK_STATUS" = "ROLLBACK_FAILED" ]; then
    echo "Stack $BLUEPRINTS_STACK_NAME is in $STACK_STATUS state. Deleting..."
    aws cloudformation delete-stack --stack-name "$BLUEPRINTS_STACK_NAME" --region "$REGION"
    echo "Waiting for stack deletion to complete..."
    aws cloudformation wait stack-delete-complete --stack-name "$BLUEPRINTS_STACK_NAME" --region "$REGION" || echo "Stack deletion completed with warnings"
    echo "Stack cleanup completed."
fi

# Get Domain ID from the domain stack
DOMAIN_ID=$(aws cloudformation describe-stacks --stack-name "$DOMAIN_STACK_NAME" --region "$REGION" --query 'Stacks[0].Outputs[?OutputKey==`DomainId`].OutputValue' --output text)
DOMAIN_NAME=$(aws cloudformation describe-stacks --stack-name "$DOMAIN_STACK_NAME" --region "$REGION" --query 'Stacks[0].Parameters[?ParameterKey==`DomainName`].ParameterValue' --output text)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create S3 bucket if it doesn't exist
S3_BUCKET_NAME="datazone-${ACCOUNT_ID}-${REGION}-${DOMAIN_NAME}"
echo "S3 Bucket Name: $S3_BUCKET_NAME"

if ! aws s3api head-bucket --bucket "$S3_BUCKET_NAME" --region "$REGION" 2>/dev/null; then
    echo "Creating S3 bucket $S3_BUCKET_NAME..."
    aws s3api create-bucket --bucket "$S3_BUCKET_NAME" --region "$REGION"
    aws s3api put-public-access-block --bucket "$S3_BUCKET_NAME" --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
    echo "S3 bucket created successfully."
else
    echo "S3 bucket $S3_BUCKET_NAME already exists."
fi

if [ -z "$DOMAIN_ID" ]; then
    echo "❌ Failed to get Domain ID from stack $DOMAIN_STACK_NAME"
    exit 1
fi

echo "Domain ID: $DOMAIN_ID"

# Get Environment Blueprint IDs dynamically using managed blueprints
echo "Retrieving managed environment blueprint IDs..."
LAKEHOUSE_CATALOG_BLUEPRINT_ID=$(aws datazone list-environment-blueprints --domain-identifier "$DOMAIN_ID" --region "$REGION" --managed --query 'items[?name==`LakehouseCatalog`].id' --output text)
DATA_LAKE_BLUEPRINT_ID=$(aws datazone list-environment-blueprints --domain-identifier "$DOMAIN_ID" --region "$REGION" --managed --query 'items[?name==`DataLake`].id' --output text)
TOOLING_BLUEPRINT_ID=$(aws datazone list-environment-blueprints --domain-identifier "$DOMAIN_ID" --region "$REGION" --managed --query 'items[?name==`Tooling`].id' --output text)
WORKFLOW_BLUEPRINT_ID=$(aws datazone list-environment-blueprints --domain-identifier "$DOMAIN_ID" --region "$REGION" --managed --query 'items[?name==`Workflows`].id' --output text)

# Use first available blueprints as fallbacks
AVAILABLE_BLUEPRINTS=($(aws datazone list-environment-blueprints --domain-identifier "$DOMAIN_ID" --region "$REGION" --managed --query 'items[].id' --output text))

if [ -z "$LAKEHOUSE_CATALOG_BLUEPRINT_ID" ] || [ "$LAKEHOUSE_CATALOG_BLUEPRINT_ID" = "None" ]; then
    LAKEHOUSE_CATALOG_BLUEPRINT_ID=${AVAILABLE_BLUEPRINTS[0]}
fi

if [ -z "$DATA_LAKE_BLUEPRINT_ID" ] || [ "$DATA_LAKE_BLUEPRINT_ID" = "None" ]; then
    DATA_LAKE_BLUEPRINT_ID=${AVAILABLE_BLUEPRINTS[1]:-${AVAILABLE_BLUEPRINTS[0]}}
fi

if [ -z "$TOOLING_BLUEPRINT_ID" ] || [ "$TOOLING_BLUEPRINT_ID" = "None" ]; then
    TOOLING_BLUEPRINT_ID=${AVAILABLE_BLUEPRINTS[2]:-${AVAILABLE_BLUEPRINTS[0]}}
fi

if [ -z "$WORKFLOW_BLUEPRINT_ID" ] || [ "$WORKFLOW_BLUEPRINT_ID" = "None" ]; then
    WORKFLOW_BLUEPRINT_ID=${AVAILABLE_BLUEPRINTS[3]:-${AVAILABLE_BLUEPRINTS[0]}}
fi

echo "LakehouseCatalog Blueprint ID: $LAKEHOUSE_CATALOG_BLUEPRINT_ID"
echo "DataLake Blueprint ID: $DATA_LAKE_BLUEPRINT_ID"
echo "Tooling Blueprint ID: $TOOLING_BLUEPRINT_ID"
echo "Workflow Blueprint ID: $WORKFLOW_BLUEPRINT_ID"

# Deploy DataZone Blueprints and Profiles Stack
echo "Deploying DataZone Blueprints and Profiles Stack..."
if aws cloudformation deploy \
  --template-file blueprints-profiles.yaml \
  --stack-name "$BLUEPRINTS_STACK_NAME" \
  --parameter-overrides \
    DomainStackName="$DOMAIN_STACK_NAME" \
    VpcId="$VPC_ID" \
    Subnets="$SUBNETS" \
    AvailabilityZones="$AVAILABILITY_ZONES" \
    S3BucketName="$S3_BUCKET_NAME" \
    LakehouseCatalogBlueprintId="$LAKEHOUSE_CATALOG_BLUEPRINT_ID" \
    DataLakeBlueprintId="$DATA_LAKE_BLUEPRINT_ID" \
    ToolingBlueprintId="$TOOLING_BLUEPRINT_ID" \
    WorkflowBlueprintId="$WORKFLOW_BLUEPRINT_ID" \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --region "$REGION"; then
  echo "✅ DataZone blueprints and profiles stack deployment complete!"
else
  echo "❌ DataZone blueprints and profiles stack deployment failed!"
  exit 1
fi

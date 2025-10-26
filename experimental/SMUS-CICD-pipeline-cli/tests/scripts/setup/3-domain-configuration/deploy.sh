#!/bin/bash

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${1:-$SCRIPT_DIR/config.yaml}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.yaml not found at $CONFIG_FILE"
    exit 1
fi

# Parse config
ACCOUNT_ID=$(yq '.account_id' "$CONFIG_FILE")
REGION=$(yq '.regions.primary.name' "$CONFIG_FILE")
REGION2=$(yq '.regions.secondary.name // ""' "$CONFIG_FILE")
REGION3=$(yq '.regions.tertiary.name // ""' "$CONFIG_FILE")
SECONDARY_ENABLED=$(yq '.regions.secondary.enabled // false' "$CONFIG_FILE")
TERTIARY_ENABLED=$(yq '.regions.tertiary.enabled // false' "$CONFIG_FILE")
BLUEPRINTS_STACK_NAME=$(yq '.stacks.blueprints_profiles' "$CONFIG_FILE")
DOMAIN_STACK_NAME=$(yq '.stacks.domain' "$CONFIG_FILE")

echo "Deploying Blueprints and Profiles..."
echo "Account ID: $ACCOUNT_ID"
echo "Primary Region: $REGION"
if [ "$SECONDARY_ENABLED" = "true" ] && [ -n "$REGION2" ]; then
    echo "Secondary Region: $REGION2 (enabled)"
fi
if [ "$TERTIARY_ENABLED" = "true" ] && [ -n "$REGION3" ]; then
    echo "Tertiary Region: $REGION3 (enabled)"
fi

# Get VPC information from config or temporary files
VPC_ID=$(yq '.VPC.VpcId // ""' "$CONFIG_FILE")
VPC_NAME=$(yq '.VPC.Name // ""' "$CONFIG_FILE")

# If VPC_ID is not in config, try VPC_NAME lookup or VPC deployment files
if [ -z "$VPC_ID" ] || [ "$VPC_ID" = "null" ]; then
    if [ -n "$VPC_NAME" ] && [ "$VPC_NAME" != "null" ]; then
        echo "Looking up VPC by name: $VPC_NAME"
        VPC_ID=$(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=$VPC_NAME" --region "$REGION" --query 'Vpcs[0].VpcId' --output text)
        if [ "$VPC_ID" = "None" ] || [ "$VPC_ID" = "null" ]; then
            echo "VPC with name '$VPC_NAME' not found, checking VPC deployment files..."
            VPC_ID=""
        fi
    fi
    
    # If still no VPC_ID, try to get it from VPC deployment
    if [ -z "$VPC_ID" ] && [ -f "/tmp/vpc_id_${REGION}.txt" ]; then
        VPC_ID=$(cat "/tmp/vpc_id_${REGION}.txt")
        SUBNETS=$(cat "/tmp/subnets_${REGION}.txt")
        AVAILABILITY_ZONES=$(cat "/tmp/azs_${REGION}.txt")
    elif [ -z "$VPC_ID" ]; then
        echo "Error: No VPC information found for region $REGION"
        exit 1
    fi
fi

# If we have VPC_ID but no subnets, retrieve them
if [ -n "$VPC_ID" ] && [ -z "$SUBNETS" ]; then
    echo "Retrieving subnets and AZs for VPC: $VPC_ID"
    SUBNETS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --region "$REGION" --query 'Subnets[].SubnetId' --output text | tr '\t' ',')
    AVAILABILITY_ZONES=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --region "$REGION" --query 'Subnets[].AvailabilityZone' --output text | tr '\t' ',')
fi

# Get VPC information for additional regions
REGION2_VPC_ID=""
REGION2_SUBNETS=""
REGION2_AZS=""
if [ "$SECONDARY_ENABLED" = "true" ] && [ -n "$REGION2" ] && [ -f "/tmp/vpc_id_${REGION2}.txt" ]; then
    REGION2_VPC_ID=$(cat "/tmp/vpc_id_${REGION2}.txt")
    REGION2_SUBNETS=$(cat "/tmp/subnets_${REGION2}.txt")
    REGION2_AZS=$(cat "/tmp/azs_${REGION2}.txt")
fi

REGION3_VPC_ID=""
REGION3_SUBNETS=""
REGION3_AZS=""
if [ "$TERTIARY_ENABLED" = "true" ] && [ -n "$REGION3" ] && [ -f "/tmp/vpc_id_${REGION3}.txt" ]; then
    REGION3_VPC_ID=$(cat "/tmp/vpc_id_${REGION3}.txt")
    REGION3_SUBNETS=$(cat "/tmp/subnets_${REGION3}.txt")
    REGION3_AZS=$(cat "/tmp/azs_${REGION3}.txt")
fi

echo "Primary Region: $REGION"
echo "Additional Region 2: ${REGION2:-'Not configured'}"
echo "Additional Region 3: ${REGION3:-'Not configured'}"
echo "Primary VPC ID: $VPC_ID"
echo "Primary Subnets: $SUBNETS"
echo "Primary Availability Zones: $AVAILABILITY_ZONES"
if [ -n "$REGION2_VPC_ID" ]; then
    echo "Region2 VPC ID: $REGION2_VPC_ID"
    echo "Region2 Subnets: $REGION2_SUBNETS"
    echo "Region2 Availability Zones: $REGION2_AZS"
fi
if [ -n "$REGION3_VPC_ID" ]; then
    echo "Region3 VPC ID: $REGION3_VPC_ID"
    echo "Region3 Subnets: $REGION3_SUBNETS"
    echo "Region3 Availability Zones: $REGION3_AZS"
fi

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
    if [ "$REGION" = "us-east-1" ]; then
        aws s3api create-bucket --bucket "$S3_BUCKET_NAME" --region "$REGION"
    else
        aws s3api create-bucket --bucket "$S3_BUCKET_NAME" --region "$REGION" --create-bucket-configuration LocationConstraint="$REGION"
    fi
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

# Build parameter overrides
PARAMETER_OVERRIDES="DomainStackName=$DOMAIN_STACK_NAME VpcId=$VPC_ID Subnets=$SUBNETS AvailabilityZones=$AVAILABILITY_ZONES S3BucketName=$S3_BUCKET_NAME LakehouseCatalogBlueprintId=$LAKEHOUSE_CATALOG_BLUEPRINT_ID DataLakeBlueprintId=$DATA_LAKE_BLUEPRINT_ID ToolingBlueprintId=$TOOLING_BLUEPRINT_ID WorkflowBlueprintId=$WORKFLOW_BLUEPRINT_ID"

# Add optional region parameters if they exist
if [ "$SECONDARY_ENABLED" = "true" ] && [ -n "$REGION2" ]; then
    PARAMETER_OVERRIDES="$PARAMETER_OVERRIDES Region2=$REGION2"
    if [ -n "$REGION2_VPC_ID" ]; then
        PARAMETER_OVERRIDES="$PARAMETER_OVERRIDES Region2VpcId=$REGION2_VPC_ID Region2Subnets=$REGION2_SUBNETS Region2AvailabilityZones=$REGION2_AZS"
    fi
fi

if [ "$TERTIARY_ENABLED" = "true" ] && [ -n "$REGION3" ]; then
    PARAMETER_OVERRIDES="$PARAMETER_OVERRIDES Region3=$REGION3"
    if [ -n "$REGION3_VPC_ID" ]; then
        PARAMETER_OVERRIDES="$PARAMETER_OVERRIDES Region3VpcId=$REGION3_VPC_ID Region3Subnets=$REGION3_SUBNETS Region3AvailabilityZones=$REGION3_AZS"
    fi
fi

# Deploy DataZone Blueprints and Profiles Stack
echo "Deploying DataZone Blueprints and Profiles Stack..."
if aws cloudformation deploy \
  --template-file "$SCRIPT_DIR/blueprints-profiles.yaml" \
  --stack-name "$BLUEPRINTS_STACK_NAME" \
  --parameter-overrides $PARAMETER_OVERRIDES \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --region "$REGION"; then
  echo "✅ DataZone blueprints and profiles stack deployment complete!"
else
  echo "❌ DataZone blueprints and profiles stack deployment failed!"
  exit 1
fi

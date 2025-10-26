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
#!/bin/bash

# Deploy VPC for SageMaker Unified Studio in specified region
# This script checks for existing VPCs with the required tag before creating new ones

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${1:-$SCRIPT_DIR/config.yaml}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.yaml not found at $CONFIG_FILE"
    exit 1
fi

# Function to deploy VPC in a specific region
deploy_vpc_in_region() {
    local region=$1
    local stack_suffix=$2
    
    echo "=== Deploying VPC in region: $region ==="
    
    # Check for existing VPC with the required tag
    echo "Checking for existing VPC with CreatedForUseWithSageMakerUnifiedStudio=true in $region..."
    EXISTING_VPC=$(aws ec2 describe-vpcs \
        --region "$region" \
        --filters "Name=tag:CreatedForUseWithSageMakerUnifiedStudio,Values=true" \
        --query 'Vpcs[0].VpcId' \
        --output text 2>/dev/null || echo "None")
    
    if [ "$EXISTING_VPC" != "None" ] && [ "$EXISTING_VPC" != "null" ]; then
        echo "✅ Found existing VPC: $EXISTING_VPC in $region"
        echo "Skipping VPC creation and using existing VPC"
        
        # Get subnets and AZs from existing VPC
        SUBNETS=$(aws ec2 describe-subnets \
            --region "$region" \
            --filters "Name=vpc-id,Values=$EXISTING_VPC" "Name=tag:CreatedForUseWithSageMakerUnifiedStudio,Values=true" \
            --query 'Subnets[?contains(Tags[?Key==`Name`].Value, `Private`)].SubnetId' \
            --output text | tr '\t' ',')
        
        AZS=$(aws ec2 describe-subnets \
            --region "$region" \
            --filters "Name=vpc-id,Values=$EXISTING_VPC" "Name=tag:CreatedForUseWithSageMakerUnifiedStudio,Values=true" \
            --query 'Subnets[?contains(Tags[?Key==`Name`].Value, `Private`)].AvailabilityZone' \
            --output text | tr '\t' ',')
        
        echo "VPC ID: $EXISTING_VPC"
        echo "Private Subnets: $SUBNETS"
        echo "Availability Zones: $AZS"
        
        # Store VPC info for later use
        echo "$EXISTING_VPC" > "/tmp/vpc_id_${region}.txt"
        echo "$SUBNETS" > "/tmp/subnets_${region}.txt"
        echo "$AZS" > "/tmp/azs_${region}.txt"
        
        return 0
    fi
    
    echo "No existing VPC found. Creating new VPC in $region..."
    
    # Stack name for this region
    VPC_STACK_NAME="sagemaker-unified-studio-vpc${stack_suffix}"
    
    # Check if stack exists and is in ROLLBACK_COMPLETE state
    STACK_STATUS=$(aws cloudformation describe-stacks \
        --stack-name "$VPC_STACK_NAME" \
        --region "$region" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "DOES_NOT_EXIST")
    
    if [ "$STACK_STATUS" = "ROLLBACK_COMPLETE" ]; then
        echo "Stack $VPC_STACK_NAME is in ROLLBACK_COMPLETE state. Deleting..."
        aws cloudformation delete-stack --stack-name "$VPC_STACK_NAME" --region "$region"
        echo "Waiting for stack deletion to complete..."
        aws cloudformation wait stack-delete-complete --stack-name "$VPC_STACK_NAME" --region "$region"
        echo "Stack deleted successfully."
    fi
    
    # Deploy VPC stack
    echo "Deploying VPC stack: $VPC_STACK_NAME in $region..."
    if aws cloudformation deploy \
        --template-file "$SCRIPT_DIR/vpc-template.yaml" \
        --stack-name "$VPC_STACK_NAME" \
        --parameter-overrides useVpcEndpoints=false \
        --region "$region"; then
        
        echo "✅ VPC stack deployment complete in $region!"
        
        # Get VPC details from stack outputs
        VPC_ID=$(aws cloudformation describe-stacks \
            --stack-name "$VPC_STACK_NAME" \
            --region "$region" \
            --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
            --output text)
        
        SUBNETS=$(aws cloudformation describe-stacks \
            --stack-name "$VPC_STACK_NAME" \
            --region "$region" \
            --query 'Stacks[0].Outputs[?OutputKey==`PrivateSubnets`].OutputValue' \
            --output text)
        
        AZS=$(aws cloudformation describe-stacks \
            --stack-name "$VPC_STACK_NAME" \
            --region "$region" \
            --query 'Stacks[0].Outputs[?OutputKey==`AvailabilityZones`].OutputValue' \
            --output text)
        
        echo "VPC ID: $VPC_ID"
        echo "Private Subnets: $SUBNETS"
        echo "Availability Zones: $AZS"
        
        # Store VPC info for later use
        echo "$VPC_ID" > "/tmp/vpc_id_${region}.txt"
        echo "$SUBNETS" > "/tmp/subnets_${region}.txt"
        echo "$AZS" > "/tmp/azs_${region}.txt"
        
    else
        echo "❌ VPC stack deployment failed in $region!"
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

echo "=== VPC Deployment for SageMaker Unified Studio ==="
echo "Account ID: $ACCOUNT_ID"
echo "Primary Region: $PRIMARY_REGION (enabled: $PRIMARY_ENABLED)"
echo "Secondary Region: ${SECONDARY_REGION:-'Not configured'} (enabled: $SECONDARY_ENABLED)"
echo "Tertiary Region: ${TERTIARY_REGION:-'Not configured'} (enabled: $TERTIARY_ENABLED)"
echo

# Deploy VPC in primary region if enabled
if [ "$PRIMARY_ENABLED" = "true" ]; then
    deploy_vpc_in_region "$PRIMARY_REGION" ""
fi

# Deploy VPC in secondary region if enabled
if [ "$SECONDARY_ENABLED" = "true" ] && [ -n "$SECONDARY_REGION" ]; then
    deploy_vpc_in_region "$SECONDARY_REGION" "-region2"
fi

# Deploy VPC in tertiary region if enabled
if [ "$TERTIARY_ENABLED" = "true" ] && [ -n "$TERTIARY_REGION" ]; then
    deploy_vpc_in_region "$TERTIARY_REGION" "-region3"
fi

echo
echo "=== VPC Deployment Complete! ==="
echo "All required VPCs are now available for SageMaker Unified Studio deployment."

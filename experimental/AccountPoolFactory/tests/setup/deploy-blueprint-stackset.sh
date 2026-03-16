#!/bin/bash

# Deploy Blueprint Enablement StackSet Only
# This script creates the Blueprint Enablement StackSet for approved templates

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
CONFIG_FILE="$PROJECT_ROOT/config.yaml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deploy Blueprint Enablement StackSet${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: Configuration file not found: $CONFIG_FILE${NC}"
    echo "Please create config.yaml from config.yaml.template"
    exit 1
fi

# Function to read config value
get_config_value() {
    local key=$1
    if command -v yq &> /dev/null; then
        yq eval "$key" "$CONFIG_FILE"
    else
        grep "^${key##*.}:" "$CONFIG_FILE" | sed 's/.*: //' | tr -d '"' | tr -d "'"
    fi
}

# Read configuration
REGION=$(get_config_value '.aws.region')
ACCOUNT_ID=$(get_config_value '.aws.account_id')
CF1_STACK_NAME="${CF1_STACK_NAME:-AccountPoolFactory-ControlTower-Test}"
PROJECT_TAG=$(get_config_value '.tags.Project')
ENVIRONMENT_TAG=$(get_config_value '.tags.Environment')

echo "Configuration:"
echo "  Region: $REGION"
echo "  Account ID: $ACCOUNT_ID"
echo "  CF1 Stack Name: $CF1_STACK_NAME"
echo ""

# Check if CF1 stack exists
echo -e "${YELLOW}Checking if CF1 stack exists...${NC}"
if ! aws cloudformation describe-stacks \
    --stack-name "$CF1_STACK_NAME" \
    --region "$REGION" &> /dev/null; then
    echo -e "${RED}Error: CF1 stack not found: $CF1_STACK_NAME${NC}"
    exit 1
fi
echo -e "${GREEN}✓ CF1 stack exists${NC}"
echo ""

# Get CF1 stack outputs
echo -e "${YELLOW}Getting CF1 stack outputs...${NC}"
ADMIN_ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$CF1_STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`StackSetAdministrationRoleArn`].OutputValue' \
    --output text)

if [ -z "$ADMIN_ROLE_ARN" ]; then
    echo -e "${RED}Error: Could not get StackSetAdministrationRoleArn from CF1 stack${NC}"
    exit 1
fi

echo "  Admin Role ARN: $ADMIN_ROLE_ARN"
echo ""

# Create S3 bucket for templates if it doesn't exist
BUCKET_NAME="apf-stacksets-${ACCOUNT_ID}"
echo -e "${YELLOW}Checking S3 bucket for templates...${NC}"
if ! aws s3 ls "s3://$BUCKET_NAME" --region "$REGION" &> /dev/null; then
    echo "Creating S3 bucket: $BUCKET_NAME"
    if [ "$REGION" = "us-east-1" ]; then
        aws s3api create-bucket \
            --bucket "$BUCKET_NAME" \
            --region "$REGION"
    else
        aws s3api create-bucket \
            --bucket "$BUCKET_NAME" \
            --region "$REGION" \
            --create-bucket-configuration LocationConstraint="$REGION"
    fi
    
    aws s3api put-bucket-versioning \
        --bucket "$BUCKET_NAME" \
        --versioning-configuration Status=Enabled \
        --region "$REGION"
    
    aws s3api put-bucket-encryption \
        --bucket "$BUCKET_NAME" \
        --server-side-encryption-configuration '{
            "Rules": [{
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "AES256"
                }
            }]
        }' \
        --region "$REGION"
    
    echo -e "${GREEN}✓ S3 bucket created${NC}"
else
    echo -e "${GREEN}✓ S3 bucket already exists${NC}"
fi
echo ""

# Upload Blueprint Enablement template to S3
echo -e "${YELLOW}Uploading Blueprint Enablement template to S3...${NC}"
TEMPLATES_DIR="$PROJECT_ROOT/approved-stacksets/cloudformation/idc"
TEMPLATE_FILE="blueprint-enablement.yaml"

if [ ! -f "$TEMPLATES_DIR/$TEMPLATE_FILE" ]; then
    echo -e "${RED}Error: Template not found: $TEMPLATES_DIR/$TEMPLATE_FILE${NC}"
    exit 1
fi

aws s3 cp "$TEMPLATES_DIR/$TEMPLATE_FILE" "s3://$BUCKET_NAME/$TEMPLATE_FILE" --region "$REGION"
echo -e "${GREEN}✓ Uploaded $TEMPLATE_FILE${NC}"
echo ""

# Create or update Blueprint Enablement StackSet
STACKSET_NAME="${CF1_STACK_NAME}-BlueprintEnablement"
echo -e "${YELLOW}Processing StackSet: $STACKSET_NAME${NC}"

if aws cloudformation describe-stack-set \
    --stack-set-name "$STACKSET_NAME" \
    --region "$REGION" &> /dev/null; then
    
    echo "  StackSet exists, updating..."
    aws cloudformation update-stack-set \
        --stack-set-name "$STACKSET_NAME" \
        --template-url "https://s3.${REGION}.amazonaws.com/${BUCKET_NAME}/${TEMPLATE_FILE}" \
        --description "Enable all DataZone environment blueprints" \
        --capabilities CAPABILITY_NAMED_IAM \
        --administration-role-arn "$ADMIN_ROLE_ARN" \
        --execution-role-name AWSControlTowerExecution \
        --region "$REGION" || true
    
    echo -e "${GREEN}✓ StackSet updated${NC}"
else
    echo "  Creating new StackSet..."
    aws cloudformation create-stack-set \
        --stack-set-name "$STACKSET_NAME" \
        --template-url "https://s3.${REGION}.amazonaws.com/${BUCKET_NAME}/${TEMPLATE_FILE}" \
        --description "Enable all DataZone environment blueprints" \
        --capabilities CAPABILITY_NAMED_IAM \
        --administration-role-arn "$ADMIN_ROLE_ARN" \
        --execution-role-name AWSControlTowerExecution \
        --permission-model SELF_MANAGED \
        --tags \
            Key=Project,Value="$PROJECT_TAG" \
            Key=Environment,Value="$ENVIRONMENT_TAG" \
            Key=ManagedBy,Value=CloudFormation \
            Key=StackSetType,Value=Approved \
        --region "$REGION"
    
    echo -e "${GREEN}✓ StackSet created${NC}"
fi
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Blueprint Enablement StackSet Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "StackSet Name: $STACKSET_NAME"
echo "S3 Bucket: s3://$BUCKET_NAME"
echo ""
echo "Note: This StackSet requires parameters when deploying instances:"
echo "  - DomainId: DataZone domain ID"
echo "  - ManageAccessRoleArn: From IAM Roles stack"
echo "  - ProvisioningRoleArn: From IAM Roles stack"
echo "  - S3Location: S3 bucket for DataZone"
echo "  - Subnets: From VPC stack"
echo "  - VpcId: From VPC stack"
echo ""
echo "To deploy to an account:"
echo "  aws cloudformation create-stack-instances \\"
echo "    --stack-set-name $STACKSET_NAME \\"
echo "    --accounts ACCOUNT_ID \\"
echo "    --regions $REGION \\"
echo "    --parameter-overrides \\"
echo "      ParameterKey=DomainId,ParameterValue=YOUR_DOMAIN_ID \\"
echo "      ParameterKey=ManageAccessRoleArn,ParameterValue=ROLE_ARN \\"
echo "      ParameterKey=ProvisioningRoleArn,ParameterValue=ROLE_ARN \\"
echo "      ParameterKey=S3Location,ParameterValue=s3://YOUR_BUCKET \\"
echo "      ParameterKey=Subnets,ParameterValue=subnet-xxx,subnet-yyy \\"
echo "      ParameterKey=VpcId,ParameterValue=vpc-xxx"
echo ""

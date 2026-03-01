#!/bin/bash

# Deploy Approved StackSets for Account Pool Factory
# This script creates CloudFormation StackSets for approved templates that will be deployed to new accounts

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
echo -e "${GREEN}Deploy Approved StackSets${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: Configuration file not found: $CONFIG_FILE${NC}"
    echo "Please create config.yaml from config.yaml.template"
    exit 1
fi

# Function to read config value (with fallback to grep/sed if yq not available)
get_config_value() {
    local key=$1
    if command -v yq &> /dev/null; then
        yq eval "$key" "$CONFIG_FILE"
    else
        # Fallback: use grep and sed
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
echo "  Project Tag: $PROJECT_TAG"
echo "  Environment Tag: $ENVIRONMENT_TAG"
echo ""

# Check if CF1 stack exists
echo -e "${YELLOW}Checking if CF1 stack exists...${NC}"
if ! aws cloudformation describe-stacks \
    --stack-name "$CF1_STACK_NAME" \
    --region "$REGION" &> /dev/null; then
    echo -e "${RED}Error: CF1 stack not found: $CF1_STACK_NAME${NC}"
    echo "Please deploy CF1 first using: ./tests/setup/scripts/deploy-account-factory.sh"
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
BUCKET_NAME="${CF1_STACK_NAME}-stackset-templates-${ACCOUNT_ID}"
echo -e "${YELLOW}Checking S3 bucket for templates...${NC}"
if ! aws s3 ls "s3://$BUCKET_NAME" --region "$REGION" &> /dev/null; then
    echo "Creating S3 bucket: $BUCKET_NAME"
    if [ "$REGION" = "us-east-1" ]; then
        aws s3 mb "s3://$BUCKET_NAME" --region "$REGION"
    else
        aws s3 mb "s3://$BUCKET_NAME" --region "$REGION" --create-bucket-configuration LocationConstraint="$REGION"
    fi
    
    # Enable versioning
    aws s3api put-bucket-versioning \
        --bucket "$BUCKET_NAME" \
        --versioning-configuration Status=Enabled \
        --region "$REGION"
    
    # Enable encryption
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

# Upload templates to S3
echo -e "${YELLOW}Uploading templates to S3...${NC}"
TEMPLATES_DIR="$PROJECT_ROOT/templates/cloudformation/03-project-account"

for template in vpc-setup.yaml blueprint-enablement.yaml iam-roles.yaml; do
    if [ -f "$TEMPLATES_DIR/$template" ]; then
        echo "  Uploading $template..."
        aws s3 cp "$TEMPLATES_DIR/$template" "s3://$BUCKET_NAME/$template" --region "$REGION"
        echo -e "${GREEN}  ✓ Uploaded $template${NC}"
    else
        echo -e "${RED}  Error: Template not found: $TEMPLATES_DIR/$template${NC}"
        exit 1
    fi
done
echo ""

# Function to create or update StackSet
create_or_update_stackset() {
    local stackset_name=$1
    local template_file=$2
    local description=$3
    
    echo -e "${YELLOW}Processing StackSet: $stackset_name${NC}"
    
    # Check if StackSet exists
    if aws cloudformation describe-stack-set \
        --stack-set-name "$stackset_name" \
        --region "$REGION" &> /dev/null; then
        
        echo "  StackSet exists, updating..."
        aws cloudformation update-stack-set \
            --stack-set-name "$stackset_name" \
            --template-url "https://s3.${REGION}.amazonaws.com/${BUCKET_NAME}/${template_file}" \
            --description "$description" \
            --capabilities CAPABILITY_NAMED_IAM \
            --parameters \
                ParameterKey=ProjectTag,ParameterValue="$PROJECT_TAG" \
                ParameterKey=EnvironmentTag,ParameterValue="$ENVIRONMENT_TAG" \
            --administration-role-arn "$ADMIN_ROLE_ARN" \
            --execution-role-name AWSControlTowerExecution \
            --region "$REGION" || true
        
        echo -e "${GREEN}  ✓ StackSet updated${NC}"
    else
        echo "  Creating new StackSet..."
        aws cloudformation create-stack-set \
            --stack-set-name "$stackset_name" \
            --template-url "https://s3.${REGION}.amazonaws.com/${BUCKET_NAME}/${template_file}" \
            --description "$description" \
            --capabilities CAPABILITY_NAMED_IAM \
            --parameters \
                ParameterKey=ProjectTag,ParameterValue="$PROJECT_TAG" \
                ParameterKey=EnvironmentTag,ParameterValue="$ENVIRONMENT_TAG" \
            --administration-role-arn "$ADMIN_ROLE_ARN" \
            --execution-role-name AWSControlTowerExecution \
            --permission-model SELF_MANAGED \
            --tags \
                Key=Project,Value="$PROJECT_TAG" \
                Key=Environment,Value="$ENVIRONMENT_TAG" \
                Key=ManagedBy,Value=CloudFormation \
                Key=StackSetType,Value=Approved \
            --region "$REGION"
        
        echo -e "${GREEN}  ✓ StackSet created${NC}"
    fi
    echo ""
}

# Create StackSets
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Creating StackSets${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

create_or_update_stackset \
    "${CF1_STACK_NAME}-IAMRoles" \
    "iam-roles.yaml" \
    "IAM roles for DataZone blueprint management and provisioning"

create_or_update_stackset \
    "${CF1_STACK_NAME}-VPCSetup" \
    "vpc-setup.yaml" \
    "VPC and networking configuration for project accounts"

create_or_update_stackset \
    "${CF1_STACK_NAME}-BlueprintEnablement" \
    "blueprint-enablement.yaml" \
    "DataZone blueprint enablement for project accounts"

# List all StackSets
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}StackSets Summary${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

aws cloudformation list-stack-sets \
    --region "$REGION" \
    --query "Summaries[?starts_with(StackSetName, '${CF1_STACK_NAME}-')].{Name:StackSetName,Status:Status}" \
    --output table

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Review StackSets in AWS Console"
echo "2. Deploy StackSet instances to new accounts using:"
echo "   aws cloudformation create-stack-instances \\"
echo "     --stack-set-name ${CF1_STACK_NAME}-IAMRoles \\"
echo "     --accounts NEW_ACCOUNT_ID \\"
echo "     --regions $REGION"
echo ""
echo "S3 Bucket: s3://$BUCKET_NAME"
echo "StackSets:"
echo "  - ${CF1_STACK_NAME}-IAMRoles"
echo "  - ${CF1_STACK_NAME}-VPCSetup"
echo "  - ${CF1_STACK_NAME}-BlueprintEnablement"
echo ""

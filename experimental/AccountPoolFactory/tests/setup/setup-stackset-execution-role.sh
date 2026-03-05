#!/bin/bash

# Setup StackSet Execution Role in Target Account
# This script creates the AWSControlTowerExecution role in accounts created via Organizations API
# so they can receive StackSet deployments

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Setup StackSet Execution Role ===${NC}"
echo ""

# Get target account ID from argument or provision file
TARGET_ACCOUNT_ID="$1"

if [ -z "$TARGET_ACCOUNT_ID" ]; then
    # Try to get from latest provision file
    PROVISION_DIR="$PROJECT_ROOT/tests/setup/test-accounts"
    if ls "$PROVISION_DIR"/test-account-provision-*.json 1> /dev/null 2>&1; then
        LATEST_FILE=$(ls -t "$PROVISION_DIR"/test-account-provision-*.json | head -1)
        TARGET_ACCOUNT_ID=$(jq -r '.accountId' "$LATEST_FILE")
        echo "Using account from latest provision file: $TARGET_ACCOUNT_ID"
    else
        echo -e "${RED}Error: No account ID provided and no provision files found${NC}"
        echo "Usage: $0 <ACCOUNT_ID>"
        exit 1
    fi
fi

# Load configuration
if [ -f "$PROJECT_ROOT/config.yaml" ]; then
    REGION=$(grep 'region:' "$PROJECT_ROOT/config.yaml" | awk '{print $2}' | tr -d '"')
    ACCOUNT_ID=$(grep 'account_id:' "$PROJECT_ROOT/config.yaml" | awk '{print $2}' | tr -d '"')
else
    echo -e "${RED}Error: config.yaml not found${NC}"
    exit 1
fi

CF1_STACK_NAME="AccountPoolFactory-ControlTower-Test"

echo "Configuration:"
echo "  Target Account: $TARGET_ACCOUNT_ID"
echo "  Org Admin Account: $ACCOUNT_ID"
echo "  Region: $REGION"
echo "  CF1 Stack: $CF1_STACK_NAME"
echo ""

# Get StackSet Admin Role ARN from CF1 stack
echo -e "${YELLOW}Getting StackSet Admin Role ARN...${NC}"
ADMIN_ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$CF1_STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`StackSetAdministrationRoleArn`].OutputValue' \
    --output text)

if [ -z "$ADMIN_ROLE_ARN" ]; then
    echo -e "${RED}Error: Could not get StackSetAdministrationRoleArn${NC}"
    exit 1
fi

echo "  Admin Role ARN: $ADMIN_ROLE_ARN"
echo ""

# Create CloudFormation template for execution role
TEMPLATE_FILE="/tmp/stackset-execution-role.yaml"
cat > "$TEMPLATE_FILE" <<EOF
AWSTemplateFormatVersion: '2010-09-09'
Description: 'StackSet Execution Role for Organizations API accounts'

Parameters:
  AdministratorAccountId:
    Type: String
    Description: AWS Account ID of the administrator account
    Default: '$ACCOUNT_ID'

Resources:
  ExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: AWSControlTowerExecution
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              AWS: !Sub 'arn:aws:iam::\${AdministratorAccountId}:role/$CF1_STACK_NAME-SSAdmin'
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/AdministratorAccess
      Tags:
        - Key: Purpose
          Value: StackSetExecution
        - Key: ManagedBy
          Value: AccountPoolFactory

Outputs:
  ExecutionRoleArn:
    Description: ARN of the execution role
    Value: !GetAtt ExecutionRole.Arn
EOF

echo -e "${YELLOW}Creating execution role in target account...${NC}"
echo "Note: This requires you to have credentials for account $TARGET_ACCOUNT_ID"
echo ""

# Check if we can assume OrganizationAccountAccessRole
echo "Attempting to assume OrganizationAccountAccessRole in target account..."

TEMP_CREDS=$(aws sts assume-role \
    --role-arn "arn:aws:iam::${TARGET_ACCOUNT_ID}:role/OrganizationAccountAccessRole" \
    --role-session-name "StackSetSetup" \
    --region "$REGION" \
    --query 'Credentials' \
    --output json 2>/dev/null || echo "")

if [ -z "$TEMP_CREDS" ]; then
    echo -e "${RED}Error: Cannot assume OrganizationAccountAccessRole in target account${NC}"
    echo "This role should exist in accounts created via Organizations API"
    exit 1
fi

echo -e "${GREEN}✓ Successfully assumed role in target account${NC}"
echo ""

# Export temporary credentials
export AWS_ACCESS_KEY_ID=$(echo "$TEMP_CREDS" | jq -r '.AccessKeyId')
export AWS_SECRET_ACCESS_KEY=$(echo "$TEMP_CREDS" | jq -r '.SecretAccessKey')
export AWS_SESSION_TOKEN=$(echo "$TEMP_CREDS" | jq -r '.SessionToken')

# Deploy the execution role
echo -e "${YELLOW}Deploying execution role stack...${NC}"

# Check if stack exists and delete if in failed state
if aws cloudformation describe-stacks \
    --stack-name StackSetExecutionRole \
    --region "$REGION" &> /dev/null; then
    
    STACK_STATUS=$(aws cloudformation describe-stacks \
        --stack-name StackSetExecutionRole \
        --region "$REGION" \
        --query 'Stacks[0].StackStatus' \
        --output text)
    
    if [[ "$STACK_STATUS" == "ROLLBACK_COMPLETE" ]] || [[ "$STACK_STATUS" == *"FAILED"* ]]; then
        echo "Deleting failed stack..."
        aws cloudformation delete-stack \
            --stack-name StackSetExecutionRole \
            --region "$REGION"
        
        echo "Waiting for stack deletion..."
        aws cloudformation wait stack-delete-complete \
            --stack-name StackSetExecutionRole \
            --region "$REGION"
        
        echo -e "${GREEN}✓ Failed stack deleted${NC}"
    else
        echo -e "${GREEN}✓ Stack already exists with status: $STACK_STATUS${NC}"
        echo "Skipping creation..."
        
        # Get role ARN from existing stack
        EXECUTION_ROLE_ARN=$(aws cloudformation describe-stacks \
            --stack-name StackSetExecutionRole \
            --region "$REGION" \
            --query 'Stacks[0].Outputs[?OutputKey==`ExecutionRoleArn`].OutputValue' \
            --output text)
        
        echo ""
        echo -e "${GREEN}=== Setup Complete ===${NC}"
        echo ""
        echo "Execution Role ARN: $EXECUTION_ROLE_ARN"
        echo ""
        echo "The account is already ready to receive StackSet deployments!"
        echo ""
        
        # Clean up
        rm -f "$TEMPLATE_FILE"
        exit 0
    fi
fi

aws cloudformation create-stack \
    --stack-name StackSetExecutionRole \
    --template-body "file://$TEMPLATE_FILE" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION"

echo "Waiting for stack creation..."
aws cloudformation wait stack-create-complete \
    --stack-name StackSetExecutionRole \
    --region "$REGION"

echo -e "${GREEN}✓ Execution role created successfully${NC}"
echo ""

# Get role ARN
EXECUTION_ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name StackSetExecutionRole \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`ExecutionRoleArn`].OutputValue' \
    --output text)

echo -e "${GREEN}=== Setup Complete ===${NC}"
echo ""
echo "Execution Role ARN: $EXECUTION_ROLE_ARN"
echo ""
echo "The account is now ready to receive StackSet deployments!"
echo ""
echo "Next steps:"
echo "1. Deploy StackSet instances to this account"
echo "2. Verify resources are created"
echo ""

# Clean up
rm -f "$TEMPLATE_FILE"

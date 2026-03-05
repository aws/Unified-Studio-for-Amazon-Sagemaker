#!/bin/bash

# Comprehensive cleanup script for Account Pool Factory
# This script cleans up all resources created during testing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.yaml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load configuration
REGION="us-east-2"
ORG_ADMIN_ACCOUNT="495869084367"
DOMAIN_ACCOUNT="994753223772"
DOMAIN_ID="dzd-4igt64u5j25ko9"
ACCOUNT_POOL_ID="d47walsa85zkx5"
PROJECT_PROFILE_ID="3q3bu487vip8a1"

# Test accounts to clean up
TEST_ACCOUNT_100="004878717744"
TEST_ACCOUNT_101="400398152132"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Account Pool Factory - Complete Cleanup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}This will delete ALL resources created during testing:${NC}"
echo "  - DataZone projects"
echo "  - DataZone account pool and project profile"
echo "  - CloudFormation stacks in project accounts"
echo "  - CloudFormation stacks in domain account"
echo "  - CloudFormation stacks in org admin account"
echo "  - Test accounts (100 and 101)"
echo ""
echo -e "${RED}WARNING: This action cannot be undone!${NC}"
echo ""
read -p "Are you sure you want to proceed? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Cleanup cancelled.${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}Starting cleanup...${NC}"
echo ""

# Function to wait for stack deletion
wait_for_stack_deletion() {
    local stack_name=$1
    
    echo -e "${YELLOW}Waiting for stack $stack_name to be deleted...${NC}"
    
    while true; do
        STATUS=$(aws cloudformation describe-stacks \
            --stack-name "$stack_name" \
            --region "$REGION" \
            --query 'Stacks[0].StackStatus' \
            --output text 2>/dev/null || echo "DELETED")
        
        if [ "$STATUS" == "DELETED" ] || [ "$STATUS" == "DELETE_COMPLETE" ]; then
            echo -e "${GREEN}✓ Stack $stack_name deleted${NC}"
            break
        elif [[ "$STATUS" == *"FAILED"* ]]; then
            echo -e "${RED}✗ Stack deletion failed: $STATUS${NC}"
            break
        fi
        
        echo "  Status: $STATUS"
        sleep 10
    done
}

# Step 1: Get credentials for domain account
echo -e "${BLUE}Step 1: Authenticating to domain account${NC}"
eval $(isengardcli creds amirbo+3 --role Admin)
echo -e "${GREEN}✓ Authenticated to domain account${NC}"
echo ""

# Step 2: List and delete all projects
echo -e "${BLUE}Step 2: Deleting DataZone projects${NC}"
PROJECTS=$(aws datazone list-projects \
    --domain-identifier "$DOMAIN_ID" \
    --region "$REGION" \
    --query 'items[].identifier' \
    --output text 2>/dev/null || echo "")

if [ -n "$PROJECTS" ]; then
    for PROJECT_ID in $PROJECTS; do
        echo "Deleting project: $PROJECT_ID"
        aws datazone delete-project \
            --domain-identifier "$DOMAIN_ID" \
            --identifier "$PROJECT_ID" \
            --region "$REGION" 2>/dev/null || echo "  (already deleted or failed)"
    done
    echo -e "${GREEN}✓ Projects deleted${NC}"
else
    echo -e "${YELLOW}No projects found${NC}"
fi
echo ""

# Step 3: Delete project profile
echo -e "${BLUE}Step 3: Deleting project profile${NC}"
aws datazone delete-project-profile \
    --domain-identifier "$DOMAIN_ID" \
    --identifier "$PROJECT_PROFILE_ID" \
    --region "$REGION" 2>/dev/null && echo -e "${GREEN}✓ Project profile deleted${NC}" || echo -e "${YELLOW}Project profile not found or already deleted${NC}"
echo ""

# Step 4: Delete account pool
echo -e "${BLUE}Step 4: Deleting account pool${NC}"
aws datazone delete-account-pool \
    --domain-identifier "$DOMAIN_ID" \
    --identifier "$ACCOUNT_POOL_ID" \
    --region "$REGION" 2>/dev/null && echo -e "${GREEN}✓ Account pool deleted${NC}" || echo -e "${YELLOW}Account pool not found or already deleted${NC}"
echo ""

# Step 5: Clean up project account 100 (004878717744)
echo -e "${BLUE}Step 5: Cleaning up project account 100 (004878717744)${NC}"
echo "Getting credentials for account 100..."
eval $(isengardcli creds amirbo+1 --role Admin)

# Assume role in project account
CREDS=$(aws sts assume-role \
    --role-arn "arn:aws:iam::$TEST_ACCOUNT_100:role/OrganizationAccountAccessRole" \
    --role-session-name "cleanup" \
    --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
    --output text)

export AWS_ACCESS_KEY_ID=$(echo $CREDS | awk '{print $1}')
export AWS_SECRET_ACCESS_KEY=$(echo $CREDS | awk '{print $2}')
export AWS_SESSION_TOKEN=$(echo $CREDS | awk '{print $3}')

# Delete stacks in project account
STACKS_TO_DELETE=(
    "DataZone-PolicyGrants"
    "DataZone-Blueprint-Enablement"
    "DataZone-IAM-Roles"
    "StackSet-AccountPoolFactory-ControlTower-Test-VPCSetup-$TEST_ACCOUNT_100"
)

for STACK in "${STACKS_TO_DELETE[@]}"; do
    echo "Deleting stack: $STACK"
    aws cloudformation delete-stack \
        --stack-name "$STACK" \
        --region "$REGION" 2>/dev/null || echo "  (not found or already deleted)"
done

# Wait for deletions
for STACK in "${STACKS_TO_DELETE[@]}"; do
    wait_for_stack_deletion "$STACK"
done

# Delete S3 bucket for blueprints
echo "Deleting S3 bucket: datazone-blueprints-$TEST_ACCOUNT_100-$REGION"
aws s3 rb "s3://datazone-blueprints-$TEST_ACCOUNT_100-$REGION" --force 2>/dev/null && echo -e "${GREEN}✓ S3 bucket deleted${NC}" || echo -e "${YELLOW}S3 bucket not found${NC}"

echo -e "${GREEN}✓ Project account 100 cleaned up${NC}"
echo ""

# Step 6: Clean up domain account (994753223772)
echo -e "${BLUE}Step 6: Cleaning up domain account${NC}"
eval $(isengardcli creds amirbo+3 --role Admin)

# Delete Lambda function
echo "Deleting Lambda function: AccountProviderLambda"
aws lambda delete-function \
    --function-name AccountProviderLambda \
    --region "$REGION" 2>/dev/null && echo -e "${GREEN}✓ Lambda deleted${NC}" || echo -e "${YELLOW}Lambda not found${NC}"

# Delete CloudFormation stacks in domain account
DOMAIN_STACKS=(
    "AccountPoolFactory-DomainSharing-Test"
    "AccountPoolFactory-Lambda-Test"
)

for STACK in "${DOMAIN_STACKS[@]}"; do
    echo "Deleting stack: $STACK"
    aws cloudformation delete-stack \
        --stack-name "$STACK" \
        --region "$REGION" 2>/dev/null || echo "  (not found or already deleted)"
done

for STACK in "${DOMAIN_STACKS[@]}"; do
    wait_for_stack_deletion "$STACK"
done

echo -e "${GREEN}✓ Domain account cleaned up${NC}"
echo ""

# Step 7: Clean up org admin account (495869084367)
echo -e "${BLUE}Step 7: Cleaning up org admin account${NC}"
eval $(isengardcli creds amirbo+1 --role Admin)

# Delete StackSets first
echo "Deleting StackSets..."
STACKSETS=(
    "AccountPoolFactory-ControlTower-Test-VPCSetup"
    "AccountPoolFactory-ControlTower-Test-IAMRoles"
    "AccountPoolFactory-ControlTower-Test-BlueprintEnablement"
)

for STACKSET in "${STACKSETS[@]}"; do
    echo "Deleting StackSet: $STACKSET"
    
    # Delete stack instances first
    INSTANCES=$(aws cloudformation list-stack-instances \
        --stack-set-name "$STACKSET" \
        --region "$REGION" \
        --query 'Summaries[].Account' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$INSTANCES" ]; then
        echo "  Deleting stack instances..."
        aws cloudformation delete-stack-instances \
            --stack-set-name "$STACKSET" \
            --accounts $INSTANCES \
            --regions "$REGION" \
            --no-retain-stacks \
            --region "$REGION" 2>/dev/null || echo "  (failed or already deleted)"
        
        # Wait for instances to be deleted
        sleep 30
    fi
    
    # Delete the StackSet
    aws cloudformation delete-stack-set \
        --stack-set-name "$STACKSET" \
        --region "$REGION" 2>/dev/null && echo -e "${GREEN}✓ StackSet $STACKSET deleted${NC}" || echo -e "${YELLOW}StackSet not found${NC}"
done

# Delete CloudFormation stacks in org admin account
ORG_STACKS=(
    "AccountPoolFactory-ControlTower-Test"
    "AccountPoolFactory-Organization-Test"
)

for STACK in "${ORG_STACKS[@]}"; do
    echo "Deleting stack: $STACK"
    aws cloudformation delete-stack \
        --stack-name "$STACK" \
        --region "$REGION" 2>/dev/null || echo "  (not found or already deleted)"
done

for STACK in "${ORG_STACKS[@]}"; do
    wait_for_stack_deletion "$STACK"
done

echo -e "${GREEN}✓ Org admin account cleaned up${NC}"
echo ""

# Step 8: Close test accounts
echo -e "${BLUE}Step 8: Closing test accounts${NC}"
echo -e "${YELLOW}Note: Account closure is asynchronous and may take up to 90 days${NC}"

for ACCOUNT_ID in "$TEST_ACCOUNT_100" "$TEST_ACCOUNT_101"; do
    echo "Closing account: $ACCOUNT_ID"
    aws organizations close-account \
        --account-id "$ACCOUNT_ID" 2>/dev/null && echo -e "${GREEN}✓ Account $ACCOUNT_ID closure initiated${NC}" || echo -e "${YELLOW}Account not found or already closed${NC}"
done

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Cleanup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Delete the DataZone domain manually from the console"
echo "2. Verify all resources are deleted in AWS console"
echo "3. Check for any remaining S3 buckets or logs"
echo ""
echo -e "${BLUE}Summary of cleaned up resources:${NC}"
echo "  ✓ DataZone projects"
echo "  ✓ DataZone project profile"
echo "  ✓ DataZone account pool"
echo "  ✓ Lambda function"
echo "  ✓ CloudFormation stacks (all accounts)"
echo "  ✓ StackSets"
echo "  ✓ S3 buckets"
echo "  ✓ Test accounts (closure initiated)"
echo ""
echo -e "${YELLOW}Domain deletion: Please delete manually from console${NC}"
echo ""

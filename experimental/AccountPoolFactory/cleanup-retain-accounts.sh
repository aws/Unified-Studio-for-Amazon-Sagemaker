#!/bin/bash

# Cleanup script that RETAINS accounts for reuse
# This script cleans up all resources EXCEPT the test accounts themselves

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGION="us-east-2"
ORG_ADMIN_ACCOUNT="495869084367"
DOMAIN_ACCOUNT="994753223772"
DOMAIN_ID="dzd-4igt64u5j25ko9"

# Test accounts to clean (but NOT close)
TEST_ACCOUNT_100="004878717744"
TEST_ACCOUNT_101="400398152132"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Account Pool Factory - Cleanup (Retain Accounts)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}This will clean up resources but RETAIN test accounts for reuse:${NC}"
echo "  - DataZone projects"
echo "  - DataZone account pool and project profile"
echo "  - CloudFormation stacks in project accounts"
echo "  - CloudFormation stacks in domain account"
echo "  - S3 buckets and artifacts"
echo ""
echo -e "${GREEN}Test accounts will be RETAINED and cleaned for reuse${NC}"
echo ""
read -p "Proceed with cleanup? (yes/no): " CONFIRM

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

# Step 1: Authenticate to domain account
echo -e "${BLUE}Step 1: Cleaning up DataZone resources${NC}"
eval $(isengardcli creds amirbo+3 --role Admin)

# Delete all projects
echo "Deleting DataZone projects..."
PROJECTS=$(aws datazone list-projects \
    --domain-identifier "$DOMAIN_ID" \
    --region "$REGION" \
    --query 'items[].identifier' \
    --output text 2>/dev/null || echo "")

if [ -n "$PROJECTS" ]; then
    for PROJECT_ID in $PROJECTS; do
        echo "  Deleting project: $PROJECT_ID"
        aws datazone delete-project \
            --domain-identifier "$DOMAIN_ID" \
            --identifier "$PROJECT_ID" \
            --region "$REGION" 2>/dev/null || echo "    (already deleted)"
    done
    echo -e "${GREEN}✓ Projects deleted${NC}"
else
    echo -e "${YELLOW}No projects found${NC}"
fi

# Note: We'll recreate account pool and project profile, so delete them
echo "Deleting project profile..."
PROJECT_PROFILE_ID=$(aws datazone list-project-profiles \
    --domain-identifier "$DOMAIN_ID" \
    --region "$REGION" \
    --query 'items[0].id' \
    --output text 2>/dev/null || echo "")

if [ -n "$PROJECT_PROFILE_ID" ] && [ "$PROJECT_PROFILE_ID" != "None" ]; then
    aws datazone delete-project-profile \
        --domain-identifier "$DOMAIN_ID" \
        --identifier "$PROJECT_PROFILE_ID" \
        --region "$REGION" 2>/dev/null && echo -e "${GREEN}✓ Project profile deleted${NC}" || echo -e "${YELLOW}Already deleted${NC}"
fi

echo "Deleting account pool..."
ACCOUNT_POOL_ID=$(aws datazone list-account-pools \
    --domain-identifier "$DOMAIN_ID" \
    --region "$REGION" \
    --query 'items[0].id' \
    --output text 2>/dev/null || echo "")

if [ -n "$ACCOUNT_POOL_ID" ] && [ "$ACCOUNT_POOL_ID" != "None" ]; then
    aws datazone delete-account-pool \
        --domain-identifier "$DOMAIN_ID" \
        --identifier "$ACCOUNT_POOL_ID" \
        --region "$REGION" 2>/dev/null && echo -e "${GREEN}✓ Account pool deleted${NC}" || echo -e "${YELLOW}Already deleted${NC}"
fi

echo ""

# Step 2: Clean up project account 100
echo -e "${BLUE}Step 2: Cleaning up project account 100 (${TEST_ACCOUNT_100})${NC}"
eval $(isengardcli creds amirbo+1 --role Admin)

CREDS=$(aws sts assume-role \
    --role-arn "arn:aws:iam::$TEST_ACCOUNT_100:role/OrganizationAccountAccessRole" \
    --role-session-name "cleanup" \
    --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
    --output text)

export AWS_ACCESS_KEY_ID=$(echo $CREDS | awk '{print $1}')
export AWS_SECRET_ACCESS_KEY=$(echo $CREDS | awk '{print $2}')
export AWS_SESSION_TOKEN=$(echo $CREDS | awk '{print $3}')

# Delete all CloudFormation stacks
echo "Deleting CloudFormation stacks..."
STACKS=$(aws cloudformation list-stacks \
    --region "$REGION" \
    --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
    --query 'StackSummaries[?starts_with(StackName, `DataZone`) || starts_with(StackName, `StackSet`)].StackName' \
    --output text)

if [ -n "$STACKS" ]; then
    for STACK in $STACKS; do
        echo "  Deleting: $STACK"
        aws cloudformation delete-stack --stack-name "$STACK" --region "$REGION" 2>/dev/null || echo "    (failed)"
    done
    
    # Wait for deletions
    for STACK in $STACKS; do
        wait_for_stack_deletion "$STACK"
    done
else
    echo -e "${YELLOW}No stacks found${NC}"
fi

# Empty and delete S3 buckets
echo "Cleaning S3 buckets..."
BUCKETS=$(aws s3 ls | grep "datazone-blueprints-$TEST_ACCOUNT_100" | awk '{print $3}')
if [ -n "$BUCKETS" ]; then
    for BUCKET in $BUCKETS; do
        echo "  Emptying and deleting: $BUCKET"
        aws s3 rb "s3://$BUCKET" --force 2>/dev/null && echo "    ✓ Deleted" || echo "    (not found)"
    done
else
    echo -e "${YELLOW}No S3 buckets found${NC}"
fi

echo -e "${GREEN}✓ Account 100 cleaned${NC}"
echo ""

# Step 3: Clean up project account 101 (if it has resources)
echo -e "${BLUE}Step 3: Cleaning up project account 101 (${TEST_ACCOUNT_101})${NC}"
eval $(isengardcli creds amirbo+1 --role Admin)

CREDS=$(aws sts assume-role \
    --role-arn "arn:aws:iam::$TEST_ACCOUNT_101:role/OrganizationAccountAccessRole" \
    --role-session-name "cleanup" \
    --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
    --output text 2>/dev/null)

if [ $? -eq 0 ]; then
    export AWS_ACCESS_KEY_ID=$(echo $CREDS | awk '{print $1}')
    export AWS_SECRET_ACCESS_KEY=$(echo $CREDS | awk '{print $2}')
    export AWS_SESSION_TOKEN=$(echo $CREDS | awk '{print $3}')
    
    # Delete stacks
    STACKS=$(aws cloudformation list-stacks \
        --region "$REGION" \
        --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
        --query 'StackSummaries[?starts_with(StackName, `DataZone`) || starts_with(StackName, `StackSet`)].StackName' \
        --output text)
    
    if [ -n "$STACKS" ]; then
        for STACK in $STACKS; do
            echo "  Deleting: $STACK"
            aws cloudformation delete-stack --stack-name "$STACK" --region "$REGION" 2>/dev/null
        done
        
        for STACK in $STACKS; do
            wait_for_stack_deletion "$STACK"
        done
    else
        echo -e "${YELLOW}No stacks found${NC}"
    fi
    
    # Clean S3 buckets
    BUCKETS=$(aws s3 ls | grep "datazone-blueprints-$TEST_ACCOUNT_101" | awk '{print $3}')
    if [ -n "$BUCKETS" ]; then
        for BUCKET in $BUCKETS; do
            echo "  Emptying and deleting: $BUCKET"
            aws s3 rb "s3://$BUCKET" --force 2>/dev/null && echo "    ✓ Deleted" || echo "    (not found)"
        done
    fi
    
    echo -e "${GREEN}✓ Account 101 cleaned${NC}"
else
    echo -e "${YELLOW}Account 101 not accessible or already suspended${NC}"
fi

echo ""

# Step 4: Clean up domain account
echo -e "${BLUE}Step 4: Cleaning up domain account${NC}"
eval $(isengardcli creds amirbo+3 --role Admin)

# Delete Lambda (we'll recreate it)
echo "Deleting Lambda function..."
aws lambda delete-function \
    --function-name AccountProviderLambda \
    --region "$REGION" 2>/dev/null && echo -e "${GREEN}✓ Lambda deleted${NC}" || echo -e "${YELLOW}Lambda not found${NC}"

# Delete domain account stacks
DOMAIN_STACKS=$(aws cloudformation list-stacks \
    --region "$REGION" \
    --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
    --query 'StackSummaries[?starts_with(StackName, `AccountPoolFactory`)].StackName' \
    --output text)

if [ -n "$DOMAIN_STACKS" ]; then
    for STACK in $DOMAIN_STACKS; do
        echo "Deleting stack: $STACK"
        aws cloudformation delete-stack --stack-name "$STACK" --region "$REGION" 2>/dev/null
    done
    
    for STACK in $DOMAIN_STACKS; do
        wait_for_stack_deletion "$STACK"
    done
fi

echo -e "${GREEN}✓ Domain account cleaned${NC}"
echo ""

# Step 5: Clean up org admin account (StackSets only, keep CF1)
echo -e "${BLUE}Step 5: Cleaning up org admin account (StackSets only)${NC}"
eval $(isengardcli creds amirbo+1 --role Admin)

STACKSETS=$(aws cloudformation list-stack-sets \
    --region "$REGION" \
    --query 'Summaries[?starts_with(StackSetName, `AccountPoolFactory`)].StackSetName' \
    --output text)

if [ -n "$STACKSETS" ]; then
    for STACKSET in $STACKSETS; do
        echo "Deleting StackSet: $STACKSET"
        
        # Delete instances first
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
                --region "$REGION" 2>/dev/null || echo "    (failed)"
            sleep 30
        fi
        
        # Delete StackSet
        aws cloudformation delete-stack-set \
            --stack-set-name "$STACKSET" \
            --region "$REGION" 2>/dev/null && echo -e "${GREEN}✓ StackSet deleted${NC}" || echo -e "${YELLOW}Already deleted${NC}"
    done
fi

echo -e "${GREEN}✓ Org admin account cleaned${NC}"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Cleanup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Test accounts retained for reuse:${NC}"
echo "  - Account 100: $TEST_ACCOUNT_100"
echo "  - Account 101: $TEST_ACCOUNT_101"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Accounts are clean and ready for next test cycle"
echo "2. You can now redeploy your infrastructure"
echo "3. Reuse these accounts instead of creating new ones"
echo ""
echo -e "${GREEN}Resources cleaned:${NC}"
echo "  ✓ DataZone projects"
echo "  ✓ DataZone project profile and account pool"
echo "  ✓ CloudFormation stacks (all accounts)"
echo "  ✓ StackSets"
echo "  ✓ S3 buckets and artifacts"
echo "  ✓ Lambda functions"
echo ""
echo -e "${BLUE}Resources retained:${NC}"
echo "  ✓ Test accounts (100 and 101)"
echo "  ✓ Organization structure (OUs)"
echo "  ✓ VPC infrastructure (if needed)"
echo ""

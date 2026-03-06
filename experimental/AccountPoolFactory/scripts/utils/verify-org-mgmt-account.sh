#!/bin/bash
# Verification script for Organization Management Account resources
# Run this in the Org Management Account (495869084367)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "🔍 Organization Management Account Verification"
echo "================================================"
echo ""

# Load configuration
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

REGION=$(grep "region:" config.yaml | awk '{print $2}')
ORG_ADMIN_ACCOUNT_ID="495869084367"
DOMAIN_ACCOUNT_ID="994753223772"

echo "Configuration:"
echo "  Region: $REGION"
echo "  Org Admin Account: $ORG_ADMIN_ACCOUNT_ID"
echo "  Domain Account: $DOMAIN_ACCOUNT_ID"
echo ""

# Verify we're in the correct account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "ERROR")
if [ "$CURRENT_ACCOUNT" = "ERROR" ]; then
    echo "❌ Cannot get current account identity"
    echo "   Please ensure AWS credentials are configured"
    exit 1
fi

echo "Current Account: $CURRENT_ACCOUNT"
if [ "$CURRENT_ACCOUNT" != "$ORG_ADMIN_ACCOUNT_ID" ]; then
    echo "⚠️  WARNING: Not in Organization Management Account"
    echo "   Expected: $ORG_ADMIN_ACCOUNT_ID"
    echo "   Switch using: eval \$(isengardcli credentials amirbo+1@amazon.com)"
    exit 1
fi
echo "✅ In correct account"
echo ""

# Check CloudFormation Stacks
echo "📦 CloudFormation Stacks:"
echo "========================="

STACKS=$(aws cloudformation list-stacks \
    --region "$REGION" \
    --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
    --query 'StackSummaries[?starts_with(StackName, `AccountPoolFactory`)].{Name:StackName,Status:StackStatus,Created:CreationTime}' \
    --output table 2>/dev/null || echo "ERROR")

if [ "$STACKS" = "ERROR" ]; then
    echo "❌ Cannot list stacks"
else
    echo "$STACKS"
fi
echo ""

# Check specific stacks
echo "Checking expected stacks:"
echo ""

# 1. StackSet Roles
echo "1️⃣  AccountPoolFactory-StackSetRoles"
STACK_STATUS=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-StackSetRoles \
    --region "$REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$STACK_STATUS" = "NOT_FOUND" ]; then
    echo "   ❌ Stack NOT found"
    echo "   Action: Deploy using scripts/01-org-mgmt-account/deploy/01-deploy-stackset-roles.sh"
else
    echo "   ✅ Stack exists: $STACK_STATUS"
    
    # Check for StackSet Administration role
    ADMIN_ROLE=$(aws iam get-role \
        --role-name SMUS-AccountPoolFactory-StackSetAdmin \
        --query 'Role.RoleName' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [ "$ADMIN_ROLE" = "NOT_FOUND" ]; then
        echo "   ❌ SMUS-AccountPoolFactory-StackSetAdmin NOT found"
    else
        echo "   ✅ SMUS-AccountPoolFactory-StackSetAdmin exists"
    fi
fi
echo ""

# 2. ProvisionAccount Lambda
echo "2️⃣  AccountPoolFactory-ProvisionAccount"
STACK_STATUS=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-ProvisionAccount \
    --region "$REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$STACK_STATUS" = "NOT_FOUND" ]; then
    echo "   ❌ Stack NOT found"
    echo "   Action: Deploy using scripts/01-org-mgmt-account/deploy/05-deploy-provision-account.sh"
else
    echo "   ✅ Stack exists: $STACK_STATUS"
    
    ROLE_ARN=$(aws cloudformation describe-stacks \
        --stack-name AccountPoolFactory-ProvisionAccount \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`ProvisionAccountRoleArn`].OutputValue' \
        --output text 2>/dev/null || echo "ERROR")
    
    if [ "$ROLE_ARN" != "ERROR" ]; then
        echo "   Role ARN: $ROLE_ARN"
    fi
fi
echo ""

# 3. Trust Policy StackSet
echo "3️⃣  AccountPoolFactory-TrustPolicy StackSet"
STACKSET_STATUS=$(aws cloudformation describe-stack-set \
    --stack-set-name AccountPoolFactory-TrustPolicy \
    --region "$REGION" \
    --query 'StackSet.Status' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$STACKSET_STATUS" = "NOT_FOUND" ]; then
    echo "   ❌ StackSet NOT found"
    echo "   Action: Deploy using scripts/01-org-mgmt-account/deploy/03-deploy-trust-policy-stackset.sh"
else
    echo "   ✅ StackSet exists: $STACKSET_STATUS"
    
    # List instances
    INSTANCES=$(aws cloudformation list-stack-instances \
        --stack-set-name AccountPoolFactory-TrustPolicy \
        --region "$REGION" \
        --query 'Summaries[*].[Account,Status]' \
        --output text 2>/dev/null || echo "ERROR")
    
    if [ "$INSTANCES" != "ERROR" ]; then
        INSTANCE_COUNT=$(echo "$INSTANCES" | wc -l)
        echo "   Deployed to $INSTANCE_COUNT accounts:"
        echo "$INSTANCES" | while read ACCOUNT STATUS; do
            echo "     - $ACCOUNT: $STATUS"
        done
    fi
fi
echo ""

# 4. Check for Infrastructure stack (should NOT be here)
echo "4️⃣  AccountPoolFactory-Infrastructure (should NOT exist here)"
INFRA_STATUS=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-Infrastructure \
    --region "$REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$INFRA_STATUS" = "NOT_FOUND" ]; then
    echo "   ✅ Stack NOT found (correct - should only be in Domain account)"
else
    echo "   ❌ Stack EXISTS: $INFRA_STATUS"
    echo "   Action: DELETE this stack - it should only exist in Domain account"
    echo "   Command: aws cloudformation delete-stack --stack-name AccountPoolFactory-Infrastructure --region $REGION"
fi
echo ""

# Summary
echo "📊 Summary"
echo "=========="
echo ""
echo "Expected stacks in Organization Management Account:"
echo "  1. AccountPoolFactory-StackSetRoles"
echo "  2. AccountPoolFactory-ProvisionAccount"
echo "  3. AccountPoolFactory-TrustPolicy (StackSet)"
echo "  4. SMUS-AccountPoolFactory-DomainAccess (StackSet)"
echo ""
echo "Should NOT exist:"
echo "  - AccountPoolFactory-Infrastructure (Domain account only)"
echo ""

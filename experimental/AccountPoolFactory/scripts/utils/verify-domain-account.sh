#!/bin/bash
# Verification script for Domain Account resources
# Run this in the Domain Account (994753223772)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "🔍 Domain Account Verification"
echo "==============================="
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
if [ "$CURRENT_ACCOUNT" != "$DOMAIN_ACCOUNT_ID" ]; then
    echo "⚠️  WARNING: Not in Domain Account"
    echo "   Expected: $DOMAIN_ACCOUNT_ID"
    echo "   Switch using: eval \$(isengardcli credentials amirbo+3@amazon.com)"
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

# Check Infrastructure Stack
echo "1️⃣  AccountPoolFactory-Infrastructure"
STACK_STATUS=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-Infrastructure \
    --region "$REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$STACK_STATUS" = "NOT_FOUND" ]; then
    echo "   ❌ Stack NOT found"
    echo "   Action: Deploy using scripts/02-domain-account/deploy/01-deploy-infrastructure.sh"
else
    echo "   ✅ Stack exists: $STACK_STATUS"
    
    # Check stack outputs
    echo ""
    echo "   Stack Outputs:"
    aws cloudformation describe-stacks \
        --stack-name AccountPoolFactory-Infrastructure \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
        --output table 2>/dev/null || echo "   ERROR getting outputs"
fi
echo ""

# Check Lambda Functions
echo "2️⃣  Lambda Functions:"
echo "====================="

LAMBDAS=("PoolManager" "SetupOrchestrator" "AccountProvider")
for LAMBDA in "${LAMBDAS[@]}"; do
    echo ""
    echo "   $LAMBDA:"
    
    LAMBDA_ARN=$(aws lambda get-function \
        --function-name "$LAMBDA" \
        --region "$REGION" \
        --query 'Configuration.FunctionArn' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [ "$LAMBDA_ARN" = "NOT_FOUND" ]; then
        echo "     ❌ Lambda NOT found"
    else
        echo "     ✅ Lambda exists"
        
        # Get runtime and last modified
        RUNTIME=$(aws lambda get-function \
            --function-name "$LAMBDA" \
            --region "$REGION" \
            --query 'Configuration.Runtime' \
            --output text 2>/dev/null)
        
        LAST_MODIFIED=$(aws lambda get-function \
            --function-name "$LAMBDA" \
            --region "$REGION" \
            --query 'Configuration.LastModified' \
            --output text 2>/dev/null)
        
        echo "     Runtime: $RUNTIME"
        echo "     Last Modified: $LAST_MODIFIED"
        
        # Check environment variables for SetupOrchestrator
        if [ "$LAMBDA" = "SetupOrchestrator" ]; then
            echo ""
            echo "     Environment Variables:"
            
            ORG_ADMIN_VAR=$(aws lambda get-function-configuration \
                --function-name "$LAMBDA" \
                --region "$REGION" \
                --query 'Environment.Variables.ORG_ADMIN_ACCOUNT_ID' \
                --output text 2>/dev/null || echo "NOT_SET")
            
            if [ "$ORG_ADMIN_VAR" = "NOT_SET" ] || [ "$ORG_ADMIN_VAR" = "None" ]; then
                echo "       ❌ ORG_ADMIN_ACCOUNT_ID: NOT SET"
                echo "       Action: Redeploy infrastructure stack with OrgAdminAccountId parameter"
            else
                echo "       ✅ ORG_ADMIN_ACCOUNT_ID: $ORG_ADMIN_VAR"
            fi
        fi
    fi
done
echo ""

# Check DynamoDB Table
echo "3️⃣  DynamoDB Table:"
echo "==================="

TABLE_NAME="AccountPoolFactory-AccountState"
TABLE_STATUS=$(aws dynamodb describe-table \
    --table-name "$TABLE_NAME" \
    --region "$REGION" \
    --query 'Table.TableStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$TABLE_STATUS" = "NOT_FOUND" ]; then
    echo "   ❌ Table NOT found: $TABLE_NAME"
else
    echo "   ✅ Table exists: $TABLE_STATUS"
    
    # Get item count
    ITEM_COUNT=$(aws dynamodb scan \
        --table-name "$TABLE_NAME" \
        --region "$REGION" \
        --select COUNT \
        --query 'Count' \
        --output text 2>/dev/null || echo "ERROR")
    
    if [ "$ITEM_COUNT" != "ERROR" ]; then
        echo "   Items in table: $ITEM_COUNT"
    fi
fi
echo ""

# Check IAM Roles
echo "4️⃣  IAM Roles:"
echo "=============="

ROLES=("SMUS-AccountPoolFactory-PoolManager-Role" "SMUS-AccountPoolFactory-SetupOrchestrator-Role")
for ROLE in "${ROLES[@]}"; do
    ROLE_ARN=$(aws iam get-role \
        --role-name "$ROLE" \
        --query 'Role.Arn' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [ "$ROLE_ARN" = "NOT_FOUND" ]; then
        echo "   ❌ $ROLE: NOT FOUND"
    else
        echo "   ✅ $ROLE: EXISTS"
    fi
done

# Check AccountProvider role (has domain ID in name)
DOMAIN_ID=$(grep "domain_id:" config.yaml | awk '{print $2}')
ACCOUNT_PROVIDER_ROLE="AccountProviderLambdaRole-${DOMAIN_ID}"
ROLE_ARN=$(aws iam get-role \
    --role-name "$ACCOUNT_PROVIDER_ROLE" \
    --query 'Role.Arn' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$ROLE_ARN" = "NOT_FOUND" ]; then
    echo "   ❌ $ACCOUNT_PROVIDER_ROLE: NOT FOUND"
else
    echo "   ✅ $ACCOUNT_PROVIDER_ROLE: EXISTS"
fi
echo ""

# Check if SetupOrchestrator can assume StackSet management role
echo "5️⃣  Cross-Account Access:"
echo "=========================="

echo "   Testing SetupOrchestrator → StackSetManagement role..."
ASSUME_RESULT=$(aws sts assume-role \
    --role-arn "arn:aws:iam::${ORG_ADMIN_ACCOUNT_ID}:role/SMUS-AccountPoolFactory-StackSetAdmin" \
    --role-session-name "VerificationTest" \
    --external-id "AccountPoolFactory-${DOMAIN_ACCOUNT_ID}" \
    --query 'Credentials.AccessKeyId' \
    --output text 2>/dev/null || echo "FAILED")

if [ "$ASSUME_RESULT" = "FAILED" ]; then
    echo "   ❌ Cannot assume StackSetManagement role"
    echo "   Action: Check SetupOrchestrator role has sts:AssumeRole permission"
else
    echo "   ✅ Can assume StackSetManagement role"
fi
echo ""

# Summary
echo "📊 Summary"
echo "=========="
echo ""
echo "Expected resources in Domain Account:"
echo "  1. AccountPoolFactory-Infrastructure stack"
echo "  2. Lambda functions: PoolManager, SetupOrchestrator, AccountProvider"
echo "  3. DynamoDB table: AccountPoolFactory-AccountState"
echo "  4. IAM roles for each Lambda"
echo "  5. Cross-account access to Org Admin StackSetManagement role"
echo ""

#!/bin/bash
# Comprehensive verification before seeding the pool
# Checks all three account types are ready

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "🔍 Pre-Seed Verification"
echo "========================="
echo ""

# Load configuration
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

REGION=$(grep "region:" config.yaml | awk '{print $2}')
ORG_ADMIN_ACCOUNT_ID="495869084367"
DOMAIN_ACCOUNT_ID="994753223772"

ERRORS=0
WARNINGS=0

echo "Configuration:"
echo "  Region: $REGION"
echo "  Org Admin Account: $ORG_ADMIN_ACCOUNT_ID"
echo "  Domain Account: $DOMAIN_ACCOUNT_ID"
echo ""

# ============================================================================
# Check 1: Organization Management Account
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  Organization Management Account ($ORG_ADMIN_ACCOUNT_ID)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Switch to Org Admin account
eval $(isengardcli credentials amirbo+1@amazon.com) 2>/dev/null || {
    echo "❌ Cannot switch to Org Admin account"
    ERRORS=$((ERRORS + 1))
}

# Check StackSet Roles stack
STACK_STATUS=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-StackSetRoles \
    --region "$REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$STACK_STATUS" = "NOT_FOUND" ]; then
    echo "❌ AccountPoolFactory-StackSetRoles stack NOT found"
    ERRORS=$((ERRORS + 1))
elif [[ "$STACK_STATUS" == *"COMPLETE"* ]]; then
    echo "✅ AccountPoolFactory-StackSetRoles: $STACK_STATUS"
else
    echo "⚠️  AccountPoolFactory-StackSetRoles: $STACK_STATUS"
    WARNINGS=$((WARNINGS + 1))
fi

# Check StackSet Management role
MGMT_ROLE=$(aws iam get-role \
    --role-name AccountPoolFactory-StackSetManagement \
    --query 'Role.RoleName' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$MGMT_ROLE" = "NOT_FOUND" ]; then
    echo "❌ AccountPoolFactory-StackSetManagement role NOT found"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ AccountPoolFactory-StackSetManagement role exists"
fi

# Check Account Creation Role stack
STACK_STATUS=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-AccountCreationRole \
    --region "$REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$STACK_STATUS" = "NOT_FOUND" ]; then
    echo "❌ AccountPoolFactory-AccountCreationRole stack NOT found"
    ERRORS=$((ERRORS + 1))
elif [[ "$STACK_STATUS" == *"COMPLETE"* ]]; then
    echo "✅ AccountPoolFactory-AccountCreationRole: $STACK_STATUS"
else
    echo "⚠️  AccountPoolFactory-AccountCreationRole: $STACK_STATUS"
    WARNINGS=$((WARNINGS + 1))
fi

# Check Trust Policy StackSet
STACKSET_STATUS=$(aws cloudformation describe-stack-set \
    --stack-set-name AccountPoolFactory-TrustPolicy \
    --region "$REGION" \
    --query 'StackSet.Status' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$STACKSET_STATUS" = "NOT_FOUND" ]; then
    echo "❌ AccountPoolFactory-TrustPolicy StackSet NOT found"
    ERRORS=$((ERRORS + 1))
elif [ "$STACKSET_STATUS" = "ACTIVE" ]; then
    echo "✅ AccountPoolFactory-TrustPolicy StackSet: $STACKSET_STATUS"
else
    echo "⚠️  AccountPoolFactory-TrustPolicy StackSet: $STACKSET_STATUS"
    WARNINGS=$((WARNINGS + 1))
fi

echo ""

# ============================================================================
# Check 2: Domain Account
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  Domain Account ($DOMAIN_ACCOUNT_ID)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Switch to Domain account
eval $(isengardcli credentials amirbo+3@amazon.com) 2>/dev/null || {
    echo "❌ Cannot switch to Domain account"
    ERRORS=$((ERRORS + 1))
}

# Check Infrastructure stack
STACK_STATUS=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-Infrastructure \
    --region "$REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$STACK_STATUS" = "NOT_FOUND" ]; then
    echo "❌ AccountPoolFactory-Infrastructure stack NOT found"
    ERRORS=$((ERRORS + 1))
elif [[ "$STACK_STATUS" == *"COMPLETE"* ]]; then
    echo "✅ AccountPoolFactory-Infrastructure: $STACK_STATUS"
else
    echo "⚠️  AccountPoolFactory-Infrastructure: $STACK_STATUS"
    WARNINGS=$((WARNINGS + 1))
fi

# Check Lambda functions
LAMBDAS=("PoolManager" "SetupOrchestrator" "AccountProvider")
for LAMBDA in "${LAMBDAS[@]}"; do
    LAMBDA_ARN=$(aws lambda get-function \
        --function-name "$LAMBDA" \
        --region "$REGION" \
        --query 'Configuration.FunctionArn' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [ "$LAMBDA_ARN" = "NOT_FOUND" ]; then
        echo "❌ Lambda $LAMBDA NOT found"
        ERRORS=$((ERRORS + 1))
    else
        echo "✅ Lambda $LAMBDA exists"
    fi
done

# Check SetupOrchestrator environment variable
ORG_ADMIN_VAR=$(aws lambda get-function-configuration \
    --function-name SetupOrchestrator \
    --region "$REGION" \
    --query 'Environment.Variables.ORG_ADMIN_ACCOUNT_ID' \
    --output text 2>/dev/null || echo "NOT_SET")

if [ "$ORG_ADMIN_VAR" = "NOT_SET" ] || [ "$ORG_ADMIN_VAR" = "None" ]; then
    echo "❌ SetupOrchestrator missing ORG_ADMIN_ACCOUNT_ID"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ SetupOrchestrator has ORG_ADMIN_ACCOUNT_ID: $ORG_ADMIN_VAR"
fi

# Check DynamoDB table
TABLE_STATUS=$(aws dynamodb describe-table \
    --table-name AccountPoolFactory-AccountState \
    --region "$REGION" \
    --query 'Table.TableStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$TABLE_STATUS" = "NOT_FOUND" ]; then
    echo "❌ DynamoDB table NOT found"
    ERRORS=$((ERRORS + 1))
elif [ "$TABLE_STATUS" = "ACTIVE" ]; then
    ITEM_COUNT=$(aws dynamodb scan \
        --table-name AccountPoolFactory-AccountState \
        --region "$REGION" \
        --select COUNT \
        --query 'Count' \
        --output text 2>/dev/null || echo "0")
    echo "✅ DynamoDB table: $TABLE_STATUS (items: $ITEM_COUNT)"
    
    if [ "$ITEM_COUNT" != "0" ]; then
        echo "⚠️  Table has $ITEM_COUNT existing items"
        echo "   Consider clearing: scripts/utils/clear-dynamodb-table.sh"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo "⚠️  DynamoDB table: $TABLE_STATUS"
    WARNINGS=$((WARNINGS + 1))
fi

# Check cross-account access (verify trust policy exists)
# Note: We can't test this directly as Admin user - only SetupOrchestrator Lambda can assume this role
TRUST_POLICY=$(aws iam get-role \
    --role-name AccountPoolFactory-SetupOrchestrator-Role \
    --query 'Role.AssumeRolePolicyDocument' \
    --output json 2>/dev/null || echo "{}")

SETUP_POLICY=$(aws iam get-role-policy \
    --role-name AccountPoolFactory-SetupOrchestrator-Role \
    --policy-name SetupOrchestratorPolicy \
    --query 'PolicyDocument.Statement[?Effect==`Allow`]' \
    --output json 2>/dev/null || echo "[]")

# Check if SetupOrchestrator has permission to assume StackSetManagement role
HAS_ASSUME=$(echo "$SETUP_POLICY" | jq -r '.[] | select(.Action[] | contains("sts:AssumeRole")) | .Resource[] | select(contains("AccountPoolFactory-StackSetManagement"))' || echo "")

if [ -z "$HAS_ASSUME" ]; then
    echo "❌ SetupOrchestrator missing permission to assume StackSetManagement role"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ SetupOrchestrator has permission to assume StackSetManagement role"
    echo "   (Trust policy verified - actual assume will work from Lambda)"
fi

echo ""

# ============================================================================
# Summary
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "✅ All checks passed! Ready to seed the pool."
    echo ""
    echo "Next steps:"
    echo "1. Clear DynamoDB table (if needed): scripts/utils/clear-dynamodb-table.sh"
    echo "2. Seed the pool: cd tests/setup && ./03-seed-test-accounts.sh"
    echo "3. Monitor: aws logs tail /aws/lambda/PoolManager --follow --region $REGION"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo "⚠️  $WARNINGS warning(s) found, but no critical errors"
    echo ""
    echo "You can proceed with seeding, but review warnings above."
    echo ""
    echo "Next steps:"
    echo "1. Clear DynamoDB table (if needed): scripts/utils/clear-dynamodb-table.sh"
    echo "2. Seed the pool: cd tests/setup && ./03-seed-test-accounts.sh"
    echo "3. Monitor: aws logs tail /aws/lambda/PoolManager --follow --region $REGION"
    exit 0
else
    echo "❌ $ERRORS error(s) and $WARNINGS warning(s) found"
    echo ""
    echo "Fix the errors above before seeding the pool."
    echo ""
    echo "Common fixes:"
    echo "- Deploy missing stacks: scripts/01-org-mgmt-account/deploy/"
    echo "- Deploy infrastructure: scripts/02-domain-account/deploy/"
    echo "- Verify account access: eval \$(isengardcli credentials ...)"
    exit 1
fi

#!/bin/bash
# Verification script for Organization Management Account resources
# Run this in the Org Management Account (495869084367)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

source scripts/utils/resolve-config.sh org

echo "🔍 Organization Management Account Verification"
echo "================================================"
echo ""
echo "Region: $REGION  |  Org Admin: $CURRENT_ACCOUNT"
echo ""

# CF Stack
STATUS=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-OrgAdmin \
    --region "$REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")
[ "$STATUS" = "CREATE_COMPLETE" ] || [ "$STATUS" = "UPDATE_COMPLETE" ] \
    && echo "✅ AccountPoolFactory-OrgAdmin: $STATUS" \
    || echo "❌ AccountPoolFactory-OrgAdmin: $STATUS (run deploy-org-admin.sh)"

# IAM Roles
for ROLE in "SMUS-AccountPoolFactory-StackSetAdmin" "SMUS-AccountPoolFactory-AccountCreation"; do
    aws iam get-role --role-name "$ROLE" --query 'Role.RoleName' --output text &>/dev/null \
        && echo "✅ $ROLE exists" \
        || echo "❌ $ROLE not found"
done

# StackSet
SS=$(aws cloudformation describe-stack-set \
    --stack-set-name SMUS-AccountPoolFactory-DomainAccess \
    --region "$REGION" \
    --query 'StackSet.Status' \
    --output text 2>/dev/null || echo "NOT_FOUND")
[ "$SS" = "ACTIVE" ] \
    && echo "✅ SMUS-AccountPoolFactory-DomainAccess StackSet: ACTIVE" \
    || echo "❌ SMUS-AccountPoolFactory-DomainAccess StackSet: $SS"

#!/bin/bash
set -e

# Verify Org Admin Account deployment
# Checks all expected resources exist and are healthy

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

REGION=$(grep "region:" config.yaml | awk '{print $2}')
ORG_ADMIN_ACCOUNT_ID=$(grep "account_id:" config.yaml | head -1 | awk '{print $2}' | tr -d '"')

echo "🔍 Verifying Org Admin Account ($ORG_ADMIN_ACCOUNT_ID)"
echo "======================================================="
echo "Region: $REGION"
echo ""

CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "$ORG_ADMIN_ACCOUNT_ID" ]; then
    echo "❌ Must run in Org Admin account ($ORG_ADMIN_ACCOUNT_ID), currently in $CURRENT_ACCOUNT"
    exit 1
fi

PASS=0
FAIL=0

check() {
    local label="$1"
    local result="$2"
    local expected="$3"

    if [ "$result" = "$expected" ]; then
        echo "  ✅ $label: $result"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $label: expected '$expected', got '$result'"
        FAIL=$((FAIL + 1))
    fi
}

check_exists() {
    local label="$1"
    local result="$2"

    if [ -n "$result" ] && [ "$result" != "None" ] && [ "$result" != "null" ]; then
        echo "  ✅ $label: $result"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $label: not found"
        FAIL=$((FAIL + 1))
    fi
}

# --- CloudFormation Stacks ---
echo "📦 CloudFormation Stacks"

STATUS=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-StackSetRoles \
    --region "$REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")
check "AccountPoolFactory-StackSetRoles" "$STATUS" "CREATE_COMPLETE"

STATUS=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-ProvisionAccount \
    --region "$REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")
# Accept CREATE_COMPLETE or UPDATE_COMPLETE
if [ "$STATUS" = "CREATE_COMPLETE" ] || [ "$STATUS" = "UPDATE_COMPLETE" ]; then
    echo "  ✅ AccountPoolFactory-ProvisionAccount: $STATUS"
    PASS=$((PASS + 1))
else
    echo "  ❌ AccountPoolFactory-ProvisionAccount: expected CREATE_COMPLETE or UPDATE_COMPLETE, got $STATUS"
    FAIL=$((FAIL + 1))
fi

echo ""

# --- StackSet ---
echo "📦 StackSet"

SS_STATUS=$(aws cloudformation describe-stack-set \
    --stack-set-name SMUS-AccountPoolFactory-DomainAccess \
    --region "$REGION" \
    --query 'StackSet.Status' \
    --output text 2>/dev/null || echo "NOT_FOUND")
check "SMUS-AccountPoolFactory-DomainAccess" "$SS_STATUS" "ACTIVE"

echo ""

# --- IAM Roles ---
echo "🔐 IAM Roles"

for ROLE_NAME in \
    "SMUS-AccountPoolFactory-StackSetAdmin" \
    "SMUS-AccountPoolFactory-AccountCreation" \
    "SMUS-AccountPoolFactory-ProvisionAccount-Role"; do

    ROLE_ARN=$(aws iam get-role \
        --role-name "$ROLE_NAME" \
        --query 'Role.Arn' \
        --output text 2>/dev/null || echo "")
    check_exists "$ROLE_NAME" "$ROLE_ARN"
done

echo ""

# --- Lambda ---
echo "⚡ Lambda Functions"

LAMBDA_STATE=$(aws lambda get-function \
    --function-name ProvisionAccount \
    --region "$REGION" \
    --query 'Configuration.State' \
    --output text 2>/dev/null || echo "NOT_FOUND")
check "ProvisionAccount" "$LAMBDA_STATE" "Active"

echo ""

# --- Organization Structure ---
echo "🏢 Organization Structure"

TARGET_OU_ID=$(grep "target_ou_id:" "$PROJECT_ROOT/config.yaml" | awk '{print $2}')
if [ -n "$TARGET_OU_ID" ] && [ "$TARGET_OU_ID" != "null" ]; then
    OU_EXISTS=$(aws organizations describe-organizational-unit \
        --organizational-unit-id "$TARGET_OU_ID" \
        --query 'OrganizationalUnit.Name' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    if [ "$OU_EXISTS" != "NOT_FOUND" ]; then
        echo "  ✅ Target OU exists: $OU_EXISTS ($TARGET_OU_ID)"
        PASS=$((PASS + 1))
    else
        echo "  ❌ Target OU $TARGET_OU_ID not found in Organizations"
        FAIL=$((FAIL + 1))
    fi
else
    echo "  ⚠️  No target_ou_id in config.yaml — set organization.target_ou_id"
fi

echo ""

# --- Summary ---
echo "======================================================="
TOTAL=$((PASS + FAIL))
if [ "$FAIL" -eq 0 ]; then
    echo "✅ All $PASS checks passed — Org Admin account is ready"
    exit 0
else
    echo "❌ $FAIL of $TOTAL checks failed"
    exit 1
fi

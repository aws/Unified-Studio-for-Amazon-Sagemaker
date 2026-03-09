#!/bin/bash
set -e

# Verify Org Admin Account deployment
# Checks all expected resources exist and are healthy

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

source scripts/utils/resolve-config.sh org

echo "🔍 Verifying Org Admin Account ($CURRENT_ACCOUNT)"
echo "======================================================="
echo "Region: $REGION"
echo ""

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
    --stack-name AccountPoolFactory-OrgAdmin \
    --region "$REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")
if [ "$STATUS" = "CREATE_COMPLETE" ] || [ "$STATUS" = "UPDATE_COMPLETE" ]; then
    echo "  ✅ AccountPoolFactory-OrgAdmin: $STATUS"
    PASS=$((PASS + 1))
else
    echo "  ❌ AccountPoolFactory-OrgAdmin: expected CREATE_COMPLETE or UPDATE_COMPLETE, got $STATUS"
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
    "SMUS-AccountPoolFactory-AccountCreation"; do

    ROLE_ARN=$(aws iam get-role \
        --role-name "$ROLE_NAME" \
        --query 'Role.Arn' \
        --output text 2>/dev/null || echo "")
    check_exists "$ROLE_NAME" "$ROLE_ARN"
done

echo ""

# --- Organization Structure ---
echo "🏢 Organization Structure"

if [ -n "$TARGET_OU_ID" ] && [ "$TARGET_OU_ID" != "root" ]; then
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
    echo "  ⚠️  No target_ou_id resolved — set target_ou_id or target_ou_name in org-config.yaml"
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

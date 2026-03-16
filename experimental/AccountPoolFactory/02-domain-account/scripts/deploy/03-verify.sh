#!/bin/bash
set -e

# Verify Domain Account deployment
# Checks all expected resources exist and are healthy

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

source "$SCRIPT_DIR/../resolve-config.sh"

echo "🔍 Verifying Domain Account ($DOMAIN_ACCOUNT_ID)"
echo "=================================================="
echo "Region: $REGION"
echo "Domain ID: $DOMAIN_ID"
echo ""

CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "$DOMAIN_ACCOUNT_ID" ]; then
    echo "❌ Must run in Domain account ($DOMAIN_ACCOUNT_ID), currently in $CURRENT_ACCOUNT"
    exit 1
fi

PASS=0
FAIL=0

check() {
    local label="$1" result="$2" expected="$3"
    if [ "$result" = "$expected" ]; then
        echo "  ✅ $label: $result"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $label: expected '$expected', got '$result'"
        FAIL=$((FAIL + 1))
    fi
}

check_ok() {
    local label="$1" result="$2"
    if [ "$result" = "CREATE_COMPLETE" ] || [ "$result" = "UPDATE_COMPLETE" ]; then
        echo "  ✅ $label: $result"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $label: expected CREATE_COMPLETE or UPDATE_COMPLETE, got '$result'"
        FAIL=$((FAIL + 1))
    fi
}

check_exists() {
    local label="$1" result="$2"
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
    --stack-name AccountPoolFactory-Infrastructure \
    --region "$REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")
check_ok "AccountPoolFactory-Infrastructure" "$STATUS"
echo ""

# --- Lambda Functions ---
echo "⚡ Lambda Functions"
for FUNC in PoolManager ProvisionAccount SetupOrchestrator DeprovisionAccount AccountProvider AccountReconciler AccountRecycler; do
    STATE=$(aws lambda get-function \
        --function-name "$FUNC" \
        --region "$REGION" \
        --query 'Configuration.State' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    check "$FUNC" "$STATE" "Active"
done
echo ""

# --- IAM Roles ---
echo "🔐 IAM Roles"
for ROLE_NAME in \
    "SMUS-AccountPoolFactory-LambdaExecution-Role" \
    "SMUS-AccountPoolFactory-ProvisionAccount-Role" \
    "SMUS-AccountPoolFactory-AccountResolution-Role"; do
    ROLE_ARN=$(aws iam get-role \
        --role-name "$ROLE_NAME" \
        --query 'Role.Arn' \
        --output text 2>/dev/null || echo "")
    check_exists "$ROLE_NAME" "$ROLE_ARN"
done
echo ""

# --- DynamoDB ---
echo "📊 DynamoDB"
TABLE_STATUS=$(aws dynamodb describe-table \
    --table-name AccountPoolFactory-AccountState \
    --region "$REGION" \
    --query 'Table.TableStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")
check "AccountPoolFactory-AccountState" "$TABLE_STATUS" "ACTIVE"
echo ""

# --- DataZone Domain ---
echo "🌐 DataZone Domain"
DOMAIN_STATUS=$(aws datazone get-domain \
    --identifier "$DOMAIN_ID" \
    --region "$REGION" \
    --query 'status' \
    --output text 2>/dev/null || echo "NOT_FOUND")
check "Domain $DOMAIN_ID" "$DOMAIN_STATUS" "AVAILABLE"
echo ""

# --- Per-pool SSM Parameters ---
echo "🏊 Per-pool SSM Parameters"
for pool_name in $POOL_NAMES; do
    echo "  Pool: $pool_name"
    for PARAM in MinimumPoolSize TargetPoolSize ReclaimStrategy ProjectProfileName OUId OUName StackSets; do
        VAL=$(aws ssm get-parameter \
            --name "/AccountPoolFactory/Pools/${pool_name}/${PARAM}" \
            --region "$REGION" \
            --query 'Parameter.Value' --output text 2>/dev/null || echo "")
        check_exists "    /Pools/${pool_name}/${PARAM}" "$VAL"
    done
done
echo ""

# --- Account Pool ---
echo "🏊 Account Pool"
POOL_COUNT=$(aws datazone list-account-pools \
    --domain-identifier "$DOMAIN_ID" \
    --region "$REGION" \
    --query 'length(items)' \
    --output text 2>/dev/null || echo "0")

if [ "$POOL_COUNT" -gt 0 ]; then
    POOL_NAME=$(aws datazone list-account-pools \
        --domain-identifier "$DOMAIN_ID" \
        --region "$REGION" \
        --query 'items[0].name' \
        --output text 2>/dev/null || echo "")
    echo "  ✅ Account pool found: $POOL_NAME"
    PASS=$((PASS + 1))
else
    echo "  ❌ No account pool found"
    FAIL=$((FAIL + 1))
fi
echo ""

# --- Project Profile ---
echo "📋 Project Profile"
PROFILE_ID=$(aws datazone list-project-profiles \
    --domain-identifier "$DOMAIN_ID" \
    --region "$REGION" \
    --query "items[?name=='$PROJECT_PROFILE_NAME'].{id:id,status:status}" \
    --output json 2>/dev/null || echo "[]")

PROFILE_FOUND=$(echo "$PROFILE_ID" | python3 -c "import json,sys; items=json.loads(sys.stdin.read()); print(items[0]['id'] if items else '')")
PROFILE_STATUS=$(echo "$PROFILE_ID" | python3 -c "import json,sys; items=json.loads(sys.stdin.read()); print(items[0]['status'] if items else '')")

if [ -n "$PROFILE_FOUND" ]; then
    echo "  ✅ Project profile found: $PROJECT_PROFILE_NAME ($PROFILE_STATUS)"
    PASS=$((PASS + 1))
else
    echo "  ❌ Project profile '$PROJECT_PROFILE_NAME' not found — run: ./02-domain-account/scripts/deploy/02-deploy-project-profile.sh"
    FAIL=$((FAIL + 1))
fi
echo ""

# --- Policy Grants ---
echo "🔐 Policy Grants (ON_CREATE blueprints)"
GRANTS=$(aws datazone search-policy-grants \
    --domain-identifier "$DOMAIN_ID" \
    --managed-policy-type "CREATE_ENVIRONMENT_FROM_BLUEPRINT" \
    --region "$REGION" \
    --query 'length(items)' \
    --output text 2>/dev/null || echo "UNSUPPORTED")

if [ "$GRANTS" = "UNSUPPORTED" ]; then
    GRANT_STACKS=$(aws cloudformation list-stacks \
        --region "$REGION" \
        --query 'StackSummaries[?contains(StackName, `PolicyGrants`) && StackStatus != `DELETE_COMPLETE`].StackName' \
        --output text 2>/dev/null || echo "")
    if [ -n "$GRANT_STACKS" ] && [ "$GRANT_STACKS" != "None" ]; then
        echo "  ✅ Policy grant stacks found: $GRANT_STACKS"
        PASS=$((PASS + 1))
    else
        echo "  ⚠️  No policy grant stacks found — may have been configured manually"
    fi
else
    if [ "$GRANTS" -gt 0 ]; then
        echo "  ✅ $GRANTS policy grants configured"
        PASS=$((PASS + 1))
    else
        echo "  ❌ No policy grants found"
        FAIL=$((FAIL + 1))
    fi
fi
echo ""

# --- Pool Account Status ---
echo "📋 Pool Account Status"
for STATE_VAL in AVAILABLE ASSIGNED CREATING PROVISIONING; do
    COUNT=$(aws dynamodb query \
        --table-name AccountPoolFactory-AccountState \
        --index-name StateIndex \
        --key-condition-expression '#state = :state' \
        --expression-attribute-names '{"#state":"state"}' \
        --expression-attribute-values "{\":state\":{\"S\":\"$STATE_VAL\"}}" \
        --select COUNT \
        --region "$REGION" \
        --query 'Count' \
        --output text 2>/dev/null || echo "0")
    echo "  $STATE_VAL: $COUNT"
done
echo ""

# --- Summary ---
echo "=================================================="
TOTAL=$((PASS + FAIL))
if [ "$FAIL" -eq 0 ]; then
    echo "✅ All $PASS checks passed — Domain account is ready"
    exit 0
else
    echo "❌ $FAIL of $TOTAL checks failed"
    exit 1
fi

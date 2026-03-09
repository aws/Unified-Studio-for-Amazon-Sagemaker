#!/bin/bash
set -e

# Verify Org Admin Account deployment
# Checks CF stack, S3 templates, SSM params, and StackSet definitions per pool.

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
    local label="$1" result="$2" expected="$3"
    if [ "$result" = "$expected" ]; then
        echo "  ✅ $label: $result"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $label: expected '$expected', got '$result'"
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

# ── CF Stack ──────────────────────────────────────────────────────────────────
echo "📦 CloudFormation Stack"
STATUS=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-OrgAdmin \
    --region "$REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")
if [ "$STATUS" = "CREATE_COMPLETE" ] || [ "$STATUS" = "UPDATE_COMPLETE" ]; then
    echo "  ✅ AccountPoolFactory-OrgAdmin: $STATUS"
    PASS=$((PASS + 1))
else
    echo "  ❌ AccountPoolFactory-OrgAdmin: expected CREATE/UPDATE_COMPLETE, got $STATUS"
    FAIL=$((FAIL + 1))
fi

BUCKET_NAME=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-OrgAdmin --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`TemplateBucketName`].OutputValue' \
    --output text 2>/dev/null || echo "")
check_exists "TemplateBucketName output" "$BUCKET_NAME"
echo ""

# ── IAM Roles ─────────────────────────────────────────────────────────────────
echo "🔐 IAM Roles"
for ROLE_NAME in \
    "SMUS-AccountPoolFactory-StackSetAdmin" \
    "SMUS-AccountPoolFactory-AccountCreation"; do
    ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" \
        --query 'Role.Arn' --output text 2>/dev/null || echo "")
    check_exists "$ROLE_NAME" "$ROLE_ARN"
done
echo ""

# ── S3 Bucket & Templates ─────────────────────────────────────────────────────
echo "🪣 S3 Templates"
if [ -n "$BUCKET_NAME" ] && [ "$BUCKET_NAME" != "None" ]; then
    for KEY in \
        "stacksets/common/domain-access.yaml" \
        "stacksets/common/vpc.yaml" \
        "stacksets/common/iam-roles.yaml" \
        "stacksets/common/eventbridge.yaml" \
        "stacksets/common/blueprints.yaml"; do
        EXISTS=$(aws s3api head-object --bucket "$BUCKET_NAME" --key "$KEY" \
            --region "$REGION" --query 'ContentLength' --output text 2>/dev/null || echo "")
        check_exists "s3://$BUCKET_NAME/$KEY" "$EXISTS"
    done
else
    echo "  ⚠️  Skipping S3 checks — bucket name not resolved"
    FAIL=$((FAIL + 1))
fi
echo ""

# ── SSM Parameters ────────────────────────────────────────────────────────────
echo "🔧 SSM Parameters (global)"
for PARAM in \
    "/AccountPoolFactory/TemplateBucketName" \
    "/AccountPoolFactory/StackSetPrefix"; do
    VAL=$(aws ssm get-parameter --name "$PARAM" --region "$REGION" \
        --query 'Parameter.Value' --output text 2>/dev/null || echo "")
    check_exists "$PARAM" "$VAL"
done
echo ""

# ── Per-pool checks ───────────────────────────────────────────────────────────
for pool_name in $POOL_NAMES; do
    echo "🏊 Pool: $pool_name"

    # SSM params
    for PARAM in OUId EmailPrefix EmailDomain AccountTags StackSets; do
        VAL=$(aws ssm get-parameter \
            --name "/AccountPoolFactory/Pools/${pool_name}/${PARAM}" \
            --region "$REGION" \
            --query 'Parameter.Value' --output text 2>/dev/null || echo "")
        check_exists "  SSM /Pools/${pool_name}/${PARAM}" "$VAL"
    done

    # StackSet definitions
    STACKSETS_JSON=$(aws ssm get-parameter \
        --name "/AccountPoolFactory/Pools/${pool_name}/StackSets" \
        --region "$REGION" \
        --query 'Parameter.Value' --output text 2>/dev/null || echo "[]")

    python3 -c "
import json, subprocess, sys

entries = json.loads('''$STACKSETS_JSON''')
region = '$REGION'
pass_count = 0
fail_count = 0

for entry in entries:
    name = entry.get('stacksetName', '')
    r = subprocess.run(
        ['aws', 'cloudformation', 'describe-stack-set',
         '--stack-set-name', name, '--region', region,
         '--query', 'StackSet.Status', '--output', 'text'],
        capture_output=True, text=True
    )
    status = r.stdout.strip()
    if status == 'ACTIVE':
        print(f'  ✅   StackSet {name}: ACTIVE')
        pass_count += 1
    else:
        print(f'  ❌   StackSet {name}: {status or \"NOT_FOUND\"}')
        fail_count += 1

# Write counts to temp file for bash to read
with open('/tmp/ss_check.txt', 'w') as f:
    f.write(f'{pass_count} {fail_count}')
"
    if [ -f /tmp/ss_check.txt ]; then
        read SS_PASS SS_FAIL < /tmp/ss_check.txt
        PASS=$((PASS + SS_PASS))
        FAIL=$((FAIL + SS_FAIL))
        rm -f /tmp/ss_check.txt
    fi

    # OU exists
    KEY=$(echo "$pool_name" | tr '[:lower:]-' '[:upper:]_')
    eval "ou_id=\$POOL_${KEY}_OU_ID"
    if [ -n "$ou_id" ] && [ "$ou_id" != "root" ]; then
        OU_NAME=$(aws organizations describe-organizational-unit \
            --organizational-unit-id "$ou_id" \
            --query 'OrganizationalUnit.Name' --output text 2>/dev/null || echo "NOT_FOUND")
        check_exists "  OU $ou_id" "$OU_NAME"
    else
        echo "  ⚠️  No OU ID resolved for pool $pool_name"
    fi
    echo ""
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo "======================================================="
TOTAL=$((PASS + FAIL))
if [ "$FAIL" -eq 0 ]; then
    echo "✅ All $PASS checks passed — Org Admin account is ready"
    exit 0
else
    echo "❌ $FAIL of $TOTAL checks failed"
    exit 1
fi

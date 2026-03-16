#!/bin/bash
set -e

# Verify Org Admin Account deployment
# Checks CF stack, S3 templates, SSM params (per-OU), and StackSet definitions.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

source "$SCRIPT_DIR/../resolve-config.sh"

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
    while IFS= read -r tmpl; do
        [ -z "$tmpl" ] && continue
        KEY="stacksets/common/${tmpl}"
        EXISTS=$(aws s3api head-object --bucket "$BUCKET_NAME" --key "$KEY" \
            --region "$REGION" --query 'ContentLength' --output text 2>/dev/null || echo "")
        check_exists "s3://$BUCKET_NAME/$KEY" "$EXISTS"
    done <<< "$APPROVED_STACKSETS"
else
    echo "  ⚠️  Skipping S3 checks — bucket name not resolved"
    FAIL=$((FAIL + 1))
fi
echo ""

# ── SSM Parameters (global) ───────────────────────────────────────────────────
echo "🔧 SSM Parameters (global)"
for PARAM in \
    "/AccountPoolFactory/TemplateBucketName" \
    "/AccountPoolFactory/StackSetPrefix"; do
    VAL=$(aws ssm get-parameter --name "$PARAM" --region "$REGION" \
        --query 'Parameter.Value' --output text 2>/dev/null || echo "")
    check_exists "$PARAM" "$VAL"
done
echo ""

# ── Per-OU SSM params ─────────────────────────────────────────────────────────
echo "🏢 Per-OU SSM Parameters"
i=0
while [ $i -lt $OU_COUNT ]; do
    eval "ou_name=\$OU_${i}_NAME"
    eval "ou_id=\$OU_${i}_ID"

    echo "  OU: $ou_name (ID: $ou_id)"

    for PARAM in EmailPrefix EmailDomain AccountTags OUName; do
        VAL=$(aws ssm get-parameter \
            --name "/AccountPoolFactory/OUs/${ou_id}/${PARAM}" \
            --region "$REGION" \
            --query 'Parameter.Value' --output text 2>/dev/null || echo "")
        check_exists "    /OUs/${ou_id}/${PARAM}" "$VAL"
    done

    # Verify OU exists in Organizations
    if [ -n "$ou_id" ] && [ "$ou_id" != "root" ]; then
        OU_NAME_CHECK=$(aws organizations describe-organizational-unit \
            --organizational-unit-id "$ou_id" \
            --query 'OrganizationalUnit.Name' --output text 2>/dev/null || echo "NOT_FOUND")
        check_exists "    OU $ou_id exists" "$OU_NAME_CHECK"
    fi

    i=$((i + 1))
done
echo ""

# ── StackSet definitions ──────────────────────────────────────────────────────
echo "📦 StackSet Definitions"
while IFS= read -r tmpl; do
    [ -z "$tmpl" ] && continue
    # Derive StackSet name: prefix + TitleCase stem (strip leading NN- numeric prefix)
    stem=$(echo "$tmpl" | sed 's/\.yaml$//' | sed 's/^[0-9]*-//')
    title=$(echo "$stem" | sed 's/[-_]/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2))}1' | tr -d ' ')
    stackset_name="${STACKSET_PREFIX}-${title}"

    STATUS=$(aws cloudformation describe-stack-set \
        --stack-set-name "$stackset_name" \
        --region "$REGION" \
        --query 'StackSet.Status' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    if [ "$STATUS" = "ACTIVE" ]; then
        echo "  ✅ StackSet $stackset_name: ACTIVE"
        PASS=$((PASS + 1))
    else
        echo "  ❌ StackSet $stackset_name: $STATUS"
        FAIL=$((FAIL + 1))
    fi
done <<< "$APPROVED_STACKSETS"
echo ""

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

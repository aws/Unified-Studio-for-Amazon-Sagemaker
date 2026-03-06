#!/usr/bin/env bash
set -e

# Cleanup Legacy StackSets by assuming OrganizationAccountAccessRole in each member account
# to delete the CF stacks directly, then removing StackSet instances and StackSets.
#
# Targets these old StackSets:
#   - AccountPoolFactory-DomainAccess
#   - AccountPoolFactory-DomainAccessRole
#   - AccountPoolFactory-TrustPolicy
#
# Must be run from the Org Admin account (495869084367)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

REGION=$(grep "region:" config.yaml | awk '{print $2}')
ORG_ADMIN_ACCOUNT_ID=$(grep "account_id:" config.yaml | head -1 | awk '{print $2}' | tr -d '"')

echo "🧹 Legacy StackSet Cleanup"
echo "=========================="
echo "Region: $REGION"
echo "Org Admin: $ORG_ADMIN_ACCOUNT_ID"
echo ""

CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "$ORG_ADMIN_ACCOUNT_ID" ]; then
    echo "❌ Must run in Org Admin account ($ORG_ADMIN_ACCOUNT_ID), currently in $CURRENT_ACCOUNT"
    exit 1
fi

LEGACY_STACKSETS=(
    "AccountPoolFactory-DomainAccess"
    "AccountPoolFactory-DomainAccessRole"
    "AccountPoolFactory-TrustPolicy"
)

# Save org admin credentials to restore after each assume-role
ORG_ACCESS_KEY="$AWS_ACCESS_KEY_ID"
ORG_SECRET_KEY="$AWS_SECRET_ACCESS_KEY"
ORG_SESSION_TOKEN="$AWS_SESSION_TOKEN"

restore_org_creds() {
    export AWS_ACCESS_KEY_ID="$ORG_ACCESS_KEY"
    export AWS_SECRET_ACCESS_KEY="$ORG_SECRET_KEY"
    export AWS_SESSION_TOKEN="$ORG_SESSION_TOKEN"
}

# Use temp file instead of associative array (bash 3 compat)
WORK_DIR=$(mktemp -d)
INSTANCE_FILE="$WORK_DIR/instances.txt"
> "$INSTANCE_FILE"

trap "rm -rf $WORK_DIR" EXIT

# Step 1: Collect all accounts and their stack names per StackSet
echo "📋 Step 1: Collecting StackSet instances..."

for SS in "${LEGACY_STACKSETS[@]}"; do
    if ! aws cloudformation describe-stack-set --stack-set-name "$SS" --region "$REGION" &>/dev/null; then
        echo "   $SS: not found, skipping"
        continue
    fi

    echo "   $SS: fetching instances..."
    aws cloudformation list-stack-instances \
        --stack-set-name "$SS" \
        --region "$REGION" \
        --query 'Summaries[*].[Account,StackId]' \
        --output text 2>/dev/null | while IFS=$'\t' read -r ACCT STACK_ID; do
        if [ -n "$ACCT" ] && [ "$ACCT" != "None" ] && [ -n "$STACK_ID" ] && [ "$STACK_ID" != "None" ]; then
            STACK_NAME=$(echo "$STACK_ID" | sed 's|.*/stack/||' | sed 's|/.*||')
            if [ -n "$STACK_NAME" ]; then
                echo "$ACCT $STACK_NAME" >> "$INSTANCE_FILE"
            fi
        fi
    done
done

# Get unique accounts
UNIQUE_ACCOUNTS=$(awk '{print $1}' "$INSTANCE_FILE" | sort -u)
ACCT_COUNT=$(echo "$UNIQUE_ACCOUNTS" | grep -c . || echo 0)
echo ""
echo "   Found $ACCT_COUNT unique accounts to clean"
echo ""

# Step 2: For each account, assume role and delete stacks
echo "📦 Step 2: Deleting stacks in member accounts..."
FAILED_FILE="$WORK_DIR/failed.txt"
> "$FAILED_FILE"
SUCCESS_COUNT=0
SKIP_COUNT=0

for ACCT in $UNIQUE_ACCOUNTS; do
    # Get stacks for this account
    STACKS_FOR_ACCT=$(grep "^$ACCT " "$INSTANCE_FILE" | awk '{print $2}' | sort -u)
    STACK_COUNT=$(echo "$STACKS_FOR_ACCT" | grep -c . || echo 0)

    echo ""
    echo "--- Account $ACCT ($STACK_COUNT stacks) ---"

    if [ "$ACCT" = "$ORG_ADMIN_ACCOUNT_ID" ]; then
        echo "   Skipping (org admin account)"
        SKIP_COUNT=$((SKIP_COUNT + 1))
        continue
    fi

    # Assume OrganizationAccountAccessRole
    CREDS=$(aws sts assume-role \
        --role-arn "arn:aws:iam::${ACCT}:role/OrganizationAccountAccessRole" \
        --role-session-name "legacy-cleanup" \
        --duration-seconds 900 \
        --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
        --output text 2>/dev/null) || {
        echo "   ⚠️  Cannot assume role, skipping"
        echo "$ACCT" >> "$FAILED_FILE"
        continue
    }

    export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | awk '{print $1}')
    export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | awk '{print $2}')
    export AWS_SESSION_TOKEN=$(echo "$CREDS" | awk '{print $3}')

    for STACK_NAME in $STACKS_FOR_ACCT; do
        if [ -z "$STACK_NAME" ] || echo "$STACK_NAME" | grep -q "^arn:"; then
            echo "   (no stack deployed, will clean instance in step 3)"
            continue
        fi

        STATUS=$(aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --region "$REGION" \
            --query 'Stacks[0].StackStatus' \
            --output text 2>/dev/null || echo "NOT_FOUND")

        if [ "$STATUS" = "NOT_FOUND" ] || [ "$STATUS" = "DELETE_COMPLETE" ]; then
            echo "   $STACK_NAME: already gone"
            continue
        fi

        echo "   $STACK_NAME: deleting (was $STATUS)..."
        aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION" 2>/dev/null || {
            echo "   ⚠️  delete-stack failed"
            continue
        }

        # Wait up to 60s
        WAIT=0
        while [ $WAIT -lt 60 ]; do
            S=$(aws cloudformation describe-stacks \
                --stack-name "$STACK_NAME" \
                --region "$REGION" \
                --query 'Stacks[0].StackStatus' \
                --output text 2>/dev/null || echo "DELETE_COMPLETE")
            if [ "$S" = "DELETE_COMPLETE" ] || [ "$S" = "NOT_FOUND" ]; then
                echo "   ✅ $STACK_NAME deleted"
                SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
                break
            elif [ "$S" = "DELETE_FAILED" ]; then
                echo "   ⚠️  $STACK_NAME DELETE_FAILED"
                break
            fi
            sleep 5
            WAIT=$((WAIT + 5))
        done
    done

    restore_org_creds
done

FAILED_COUNT=$(grep -c . "$FAILED_FILE" 2>/dev/null || echo 0)
echo ""
echo "📊 Stack deletion: $SUCCESS_COUNT succeeded, $FAILED_COUNT accounts unreachable, $SKIP_COUNT skipped"

# Step 3: Remove StackSet instances with --retain-stacks (stacks already deleted)
echo ""
echo "📦 Step 3: Removing StackSet instances..."
restore_org_creds

for SS in "${LEGACY_STACKSETS[@]}"; do
    if ! aws cloudformation describe-stack-set --stack-set-name "$SS" --region "$REGION" &>/dev/null; then
        echo "   $SS: not found, skipping"
        continue
    fi

    ACCOUNTS=$(aws cloudformation list-stack-instances \
        --stack-set-name "$SS" \
        --region "$REGION" \
        --query 'Summaries[*].Account' \
        --output text 2>/dev/null)

    if [ -z "$ACCOUNTS" ] || [ "$ACCOUNTS" = "None" ]; then
        echo "   $SS: no instances"
    else
        UNIQUE=$(echo "$ACCOUNTS" | tr '\t' '\n' | sort -u | tr '\n' ' ')
        COUNT=$(echo "$UNIQUE" | wc -w | tr -d ' ')
        echo "   $SS: removing $COUNT instances with --retain-stacks..."

        OP_ID=$(aws cloudformation delete-stack-instances \
            --stack-set-name "$SS" \
            --accounts $UNIQUE \
            --regions "$REGION" \
            --retain-stacks \
            --region "$REGION" \
            --query 'OperationId' \
            --output text 2>/dev/null || echo "")

        if [ -n "$OP_ID" ] && [ "$OP_ID" != "None" ]; then
            WAIT=0
            while [ $WAIT -lt 600 ]; do
                S=$(aws cloudformation describe-stack-set-operation \
                    --stack-set-name "$SS" \
                    --operation-id "$OP_ID" \
                    --region "$REGION" \
                    --query 'StackSetOperation.Status' \
                    --output text 2>/dev/null || echo "UNKNOWN")
                if [ "$S" = "SUCCEEDED" ] || [ "$S" = "FAILED" ] || [ "$S" = "STOPPED" ]; then
                    echo "   $SS instance removal: $S"
                    break
                fi
                sleep 10
                WAIT=$((WAIT + 10))
            done
        fi
    fi
done

# Step 4: Delete the StackSets themselves
echo ""
echo "📦 Step 4: Deleting StackSets..."
for SS in "${LEGACY_STACKSETS[@]}"; do
    aws cloudformation delete-stack-set \
        --stack-set-name "$SS" \
        --region "$REGION" 2>/dev/null \
        && echo "   ✅ $SS deleted" \
        || echo "   ⚠️  $SS could not be deleted"
done

# Step 5: Final verification
echo ""
echo "=== Verification ==="
REMAINING=$(aws cloudformation list-stack-sets \
    --region "$REGION" \
    --status ACTIVE \
    --query 'Summaries[?contains(StackSetName, `AccountPoolFactory-DomainAccess`) || contains(StackSetName, `AccountPoolFactory-TrustPolicy`)].StackSetName' \
    --output text 2>/dev/null)

if [ -n "$REMAINING" ] && [ "$REMAINING" != "None" ]; then
    echo "⚠️  Remaining legacy StackSets: $REMAINING"
else
    echo "✅ All legacy StackSets cleaned up"
fi

FAILED_COUNT=$(grep -c . "$FAILED_FILE" 2>/dev/null || echo 0)
if [ "$FAILED_COUNT" -gt 0 ]; then
    echo ""
    echo "⚠️  Could not access these accounts (role may not exist):"
    cat "$FAILED_FILE" | while read A; do echo "   - $A"; done
fi

echo ""
echo "✅ Legacy StackSet cleanup complete!"

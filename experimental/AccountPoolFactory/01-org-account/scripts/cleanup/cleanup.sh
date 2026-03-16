#!/bin/bash
set -e

# Cleanup Organization Management Account Resources
# Removes all Account Pool Factory stacks and StackSets from the Org Admin account

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

source "$SCRIPT_DIR/../resolve-config.sh"

echo "🧹 Cleaning up Org Admin Account ($CURRENT_ACCOUNT)"
echo "========================================================="
echo "Region: $REGION"
echo ""

echo "⚠️  This will delete ALL AccountPoolFactory resources in this account."
read -p "Continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled"
    exit 0
fi
echo ""

# Helper: delete a StackSet and all its instances
delete_stackset() {
    local STACKSET_NAME="$1"
    echo "📦 Deleting StackSet: $STACKSET_NAME"

    if ! aws cloudformation describe-stack-set --stack-set-name "$STACKSET_NAME" --region "$REGION" &>/dev/null; then
        echo "   Not found, skipping"
        return
    fi

    # Get all instances
    ACCOUNTS=$(aws cloudformation list-stack-instances \
        --stack-set-name "$STACKSET_NAME" \
        --region "$REGION" \
        --query 'Summaries[*].Account' \
        --output text 2>/dev/null)

    if [ -n "$ACCOUNTS" ] && [ "$ACCOUNTS" != "None" ]; then
        UNIQUE_ACCOUNTS=$(echo "$ACCOUNTS" | tr '\t' '\n' | sort -u | tr '\n' ' ')
        echo "   Deleting instances in $(echo "$UNIQUE_ACCOUNTS" | wc -w | tr -d ' ') account(s)..."

        OPERATION_ID=$(aws cloudformation delete-stack-instances \
            --stack-set-name "$STACKSET_NAME" \
            --accounts $UNIQUE_ACCOUNTS \
            --regions "$REGION" \
            --no-retain-stacks \
            --region "$REGION" \
            --query 'OperationId' \
            --output text 2>/dev/null || echo "")

        if [ -n "$OPERATION_ID" ] && [ "$OPERATION_ID" != "None" ]; then
            echo "   Waiting for instance deletion (op: $OPERATION_ID)..."
            local WAIT=0
            while [ $WAIT -lt 300 ]; do
                STATUS=$(aws cloudformation describe-stack-set-operation \
                    --stack-set-name "$STACKSET_NAME" \
                    --operation-id "$OPERATION_ID" \
                    --region "$REGION" \
                    --query 'StackSetOperation.Status' \
                    --output text 2>/dev/null || echo "UNKNOWN")
                if [ "$STATUS" = "SUCCEEDED" ] || [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "STOPPED" ]; then
                    echo "   Instance deletion: $STATUS"
                    break
                fi
                sleep 10
                WAIT=$((WAIT + 10))
            done
        fi

        # If instances remain, retry with --retain-stacks
        REMAINING_ACCOUNTS=$(aws cloudformation list-stack-instances \
            --stack-set-name "$STACKSET_NAME" \
            --region "$REGION" \
            --query 'Summaries[*].Account' \
            --output text 2>/dev/null)

        if [ -n "$REMAINING_ACCOUNTS" ] && [ "$REMAINING_ACCOUNTS" != "None" ]; then
            UNIQUE_REMAINING=$(echo "$REMAINING_ACCOUNTS" | tr '\t' '\n' | sort -u | tr '\n' ' ')
            echo "   ⚠️  Instances remain, retrying with --retain-stacks..."
            RETRY_OP=$(aws cloudformation delete-stack-instances \
                --stack-set-name "$STACKSET_NAME" \
                --accounts $UNIQUE_REMAINING \
                --regions "$REGION" \
                --retain-stacks \
                --region "$REGION" \
                --query 'OperationId' \
                --output text 2>/dev/null || echo "")

            if [ -n "$RETRY_OP" ] && [ "$RETRY_OP" != "None" ]; then
                local WAIT2=0
                while [ $WAIT2 -lt 120 ]; do
                    STATUS=$(aws cloudformation describe-stack-set-operation \
                        --stack-set-name "$STACKSET_NAME" \
                        --operation-id "$RETRY_OP" \
                        --region "$REGION" \
                        --query 'StackSetOperation.Status' \
                        --output text 2>/dev/null || echo "UNKNOWN")
                    if [ "$STATUS" = "SUCCEEDED" ] || [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "STOPPED" ]; then
                        echo "   Retain-stacks deletion: $STATUS"
                        break
                    fi
                    sleep 10
                    WAIT2=$((WAIT2 + 10))
                done
            fi
        fi
    fi

    aws cloudformation delete-stack-set \
        --stack-set-name "$STACKSET_NAME" \
        --region "$REGION" 2>/dev/null && echo "   ✅ Deleted" || echo "   ⚠️  Could not delete (may have remaining instances)"
}

# Helper: delete a CF stack
delete_stack() {
    local STACK_NAME="$1"
    echo "📦 Deleting stack: $STACK_NAME"

    STATUS=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "NOT_FOUND")

    if [ "$STATUS" = "NOT_FOUND" ]; then
        echo "   Not found, skipping"
        return
    fi

    aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"
    echo "   Waiting for deletion..."
    aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$REGION" 2>/dev/null \
        && echo "   ✅ Deleted" \
        || echo "   ⚠️  Delete may have failed, check console"
}

# Step 1: Delete all StackSets derived from approved_stacksets
echo "=== Step 1: StackSets ==="
while IFS= read -r tmpl; do
    [ -z "$tmpl" ] && continue
    stem=$(echo "$tmpl" | sed 's/\.yaml$//' | sed 's/^[0-9]*-//')
    title=$(echo "$stem" | sed 's/[-_]/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2))}1' | tr -d ' ')
    stackset_name="${STACKSET_PREFIX}-${title}"
    delete_stackset "$stackset_name"
done <<< "$APPROVED_STACKSETS"

# Also delete legacy StackSet names
delete_stackset "SMUS-AccountPoolFactory-DomainAccess"
delete_stackset "AccountPoolFactory-DomainAccess"
delete_stackset "AccountPoolFactory-DomainAccessRole"
delete_stackset "AccountPoolFactory-TrustPolicy"
echo ""

# Step 2: Delete CF stacks
echo "=== Step 2: CloudFormation Stacks ==="
delete_stack "AccountPoolFactory-OrgAdmin"
delete_stack "AccountPoolFactory-ProvisionAccount"
delete_stack "AccountPoolFactory-AccountCreationRole"
delete_stack "AccountPoolFactory-StackSetRoles"
echo ""

# Step 3: Delete per-OU SSM parameters
echo "=== Step 3: Per-OU SSM Parameters ==="
i=0
while [ $i -lt $OU_COUNT ]; do
    eval "ou_id=\$OU_${i}_ID"
    echo "   Deleting SSM params for OU: $ou_id"
    for PARAM in EmailPrefix EmailDomain AccountTags OUName; do
        aws ssm delete-parameter \
            --name "/AccountPoolFactory/OUs/${ou_id}/${PARAM}" \
            --region "$REGION" 2>/dev/null || true
    done
    i=$((i + 1))
done
aws ssm delete-parameter --name "/AccountPoolFactory/TemplateBucketName" --region "$REGION" 2>/dev/null || true
aws ssm delete-parameter --name "/AccountPoolFactory/StackSetPrefix" --region "$REGION" 2>/dev/null || true
echo "   ✅ SSM params deleted"
echo ""

# Step 4: Check for anything remaining
echo "=== Step 4: Verification ==="
REMAINING=$(aws cloudformation list-stacks \
    --region "$REGION" \
    --query 'StackSummaries[?contains(StackName, `AccountPoolFactory`) && StackStatus != `DELETE_COMPLETE`].StackName' \
    --output text 2>/dev/null)

if [ -n "$REMAINING" ] && [ "$REMAINING" != "None" ]; then
    echo "⚠️  Remaining stacks: $REMAINING"
else
    echo "✅ No remaining stacks"
fi

REMAINING_SS=$(aws cloudformation list-stack-sets \
    --region "$REGION" \
    --status ACTIVE \
    --query 'Summaries[?contains(StackSetName, `AccountPoolFactory`) || contains(StackSetName, `SMUS`)].StackSetName' \
    --output text 2>/dev/null)

if [ -n "$REMAINING_SS" ] && [ "$REMAINING_SS" != "None" ]; then
    echo "⚠️  Remaining StackSets: $REMAINING_SS"
else
    echo "✅ No remaining StackSets"
fi

echo ""
echo "✅ Org Admin cleanup complete!"

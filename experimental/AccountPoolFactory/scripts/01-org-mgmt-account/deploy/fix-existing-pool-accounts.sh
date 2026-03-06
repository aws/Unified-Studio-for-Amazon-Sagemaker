#!/bin/bash
set -e

# Fix existing pool accounts that were created before the SMUS rename
#
# These accounts have old role names and are missing:
#   - SMUS-AccountPoolFactory-StackSetExecution (needed by StackSet)
#   - SMUS-AccountPoolFactory-DomainAccess (deployed by StackSet once execution role exists)
#
# This script:
#   1. Assumes OrganizationAccountAccessRole into each pool account
#   2. Deploys 01-stackset-execution-role.yaml as a CF stack
#   3. Deletes OUTDATED StackSet instances
#   4. Re-creates StackSet instances (deploys DomainAccess role)
#   5. Optionally deploys 04-project-role.yaml via DomainAccess role
#
# Prerequisites:
#   - Run from Org Admin account (amirbo+1 / 495869084367)
#   - Pool accounts must have OrganizationAccountAccessRole
#
# Usage:
#   ./fix-existing-pool-accounts.sh [account_id1 account_id2 ...]
#   If no accounts specified, queries DynamoDB for AVAILABLE accounts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

REGION=$(grep "region:" config.yaml | awk '{print $2}')
ORG_ADMIN_ACCOUNT_ID=$(grep "account_id:" config.yaml | head -1 | awk '{print $2}' | tr -d '"')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')
DOMAIN_ID=$(grep "domain_id:" config.yaml | awk '{print $2}')
STACKSET_NAME="SMUS-AccountPoolFactory-DomainAccess"

# Verify correct account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "$ORG_ADMIN_ACCOUNT_ID" ]; then
    echo "❌ Must run in Org Admin account ($ORG_ADMIN_ACCOUNT_ID), currently in $CURRENT_ACCOUNT"
    exit 1
fi

echo "🔧 Fix Existing Pool Accounts (SMUS Rename Migration)"
echo "======================================================"
echo "Org Admin Account: $ORG_ADMIN_ACCOUNT_ID"
echo "Domain Account:    $DOMAIN_ACCOUNT_ID"
echo "Domain ID:         $DOMAIN_ID"
echo "Region:            $REGION"
echo ""

# Get target accounts
if [ $# -gt 0 ]; then
    ACCOUNTS=("$@")
else
    echo "📋 No accounts specified, querying DynamoDB..."
    ACCOUNTS_JSON=$(aws dynamodb scan \
        --table-name AccountPoolFactory-AccountState \
        --region "$REGION" \
        --projection-expression "accountId,#s" \
        --expression-attribute-names '{"#s":"state"}' \
        --output json)

    # Use temp file instead of associative array (bash 3 compat)
    ACCOUNTS=()
    while IFS= read -r line; do
        ACCOUNTS+=("$line")
    done < <(echo "$ACCOUNTS_JSON" | python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
for item in data.get('Items', []):
    state = item.get('state', {}).get('S', '')
    account_id = item.get('accountId', {}).get('S', '')
    if account_id and state in ('AVAILABLE', 'PROVISIONING'):
        print(account_id)
" | sort -u)

    if [ ${#ACCOUNTS[@]} -eq 0 ]; then
        echo "❌ No pool accounts found in DynamoDB"
        exit 1
    fi
fi

echo "Target accounts: ${ACCOUNTS[*]}"
echo ""

# Helper: run a command in a pool account via OrganizationAccountAccessRole
# Uses a credentials file to avoid polluting the parent shell environment
run_in_account() {
    local TARGET_ACCOUNT="$1"
    shift
    local CREDS_FILE=$(mktemp)

    aws sts assume-role \
        --role-arn "arn:aws:iam::${TARGET_ACCOUNT}:role/OrganizationAccountAccessRole" \
        --role-session-name "FixPoolAccount" \
        --output json > "$CREDS_FILE"

    local AK=$(python3 -c "import json; print(json.load(open('$CREDS_FILE'))['Credentials']['AccessKeyId'])")
    local SK=$(python3 -c "import json; print(json.load(open('$CREDS_FILE'))['Credentials']['SecretAccessKey'])")
    local ST=$(python3 -c "import json; print(json.load(open('$CREDS_FILE'))['Credentials']['SessionToken'])")
    rm -f "$CREDS_FILE"

    AWS_ACCESS_KEY_ID="$AK" AWS_SECRET_ACCESS_KEY="$SK" AWS_SESSION_TOKEN="$ST" "$@"
}

# ============================================================
# Step 1: Deploy StackSet Execution Role to each pool account
# ============================================================
echo "═══════════════════════════════════════════════════════"
echo "Step 1: Deploy SMUS-AccountPoolFactory-StackSetExecution"
echo "═══════════════════════════════════════════════════════"

TEMPLATE_FILE="templates/cloudformation/03-project-account/deploy/01-stackset-execution-role.yaml"
EXEC_STACK_NAME="SMUS-StackSetExecution"

for ACCOUNT_ID in "${ACCOUNTS[@]}"; do
    echo ""
    echo "🔐 Account: $ACCOUNT_ID"
    echo "   Assuming OrganizationAccountAccessRole..."

    # Check if stack already exists (in subshell to avoid credential leak)
    STACK_EXISTS=$(run_in_account "$ACCOUNT_ID" \
        aws cloudformation describe-stacks \
            --stack-name "$EXEC_STACK_NAME" \
            --region "$REGION" \
            --query 'Stacks[0].StackStatus' \
            --output text 2>/dev/null || echo "DOES_NOT_EXIST")

    if [ "$STACK_EXISTS" = "CREATE_COMPLETE" ] || [ "$STACK_EXISTS" = "UPDATE_COMPLETE" ]; then
        echo "   ✅ StackSetExecution role stack already exists ($STACK_EXISTS)"
    else
        echo "   📦 Deploying StackSet Execution Role..."
        run_in_account "$ACCOUNT_ID" \
            aws cloudformation deploy \
                --template-file "$TEMPLATE_FILE" \
                --stack-name "$EXEC_STACK_NAME" \
                --parameter-overrides \
                    AdministratorAccountId="$ORG_ADMIN_ACCOUNT_ID" \
                --capabilities CAPABILITY_NAMED_IAM \
                --region "$REGION" \
                --no-fail-on-empty-changeset

        echo "   ✅ StackSetExecution role deployed"
    fi
done

echo ""
echo "✅ Step 1 complete — StackSetExecution role deployed to all accounts"
echo ""

# ============================================================
# Step 2: Delete OUTDATED StackSet instances
# ============================================================
echo "═══════════════════════════════════════════════════════"
echo "Step 2: Delete OUTDATED StackSet instances"
echo "═══════════════════════════════════════════════════════"

for ACCOUNT_ID in "${ACCOUNTS[@]}"; do
    echo ""
    echo "🗑️  Account: $ACCOUNT_ID"

    INSTANCE_STATUS=$(aws cloudformation list-stack-instances \
        --stack-set-name "$STACKSET_NAME" \
        --stack-instance-account "$ACCOUNT_ID" \
        --stack-instance-region "$REGION" \
        --region "$REGION" \
        --query 'Summaries[0].Status' \
        --output text 2>/dev/null || echo "NONE")

    if [ "$INSTANCE_STATUS" = "NONE" ] || [ "$INSTANCE_STATUS" = "None" ]; then
        echo "   No StackSet instance found — will create fresh"
        continue
    fi

    echo "   Current status: $INSTANCE_STATUS"

    if [ "$INSTANCE_STATUS" = "OUTDATED" ] || [ "$INSTANCE_STATUS" = "INOPERABLE" ]; then
        echo "   Deleting OUTDATED instance..."
        OPERATION_ID=$(aws cloudformation delete-stack-instances \
            --stack-set-name "$STACKSET_NAME" \
            --accounts "$ACCOUNT_ID" \
            --regions "$REGION" \
            --no-retain-stacks \
            --region "$REGION" \
            --query 'OperationId' \
            --output text)

        echo "   Operation: $OPERATION_ID"
        echo "   Waiting for deletion..."

        for i in $(seq 1 30); do
            OP_STATUS=$(aws cloudformation describe-stack-set-operation \
                --stack-set-name "$STACKSET_NAME" \
                --operation-id "$OPERATION_ID" \
                --region "$REGION" \
                --query 'StackSetOperation.Status' \
                --output text 2>/dev/null || echo "UNKNOWN")

            if [ "$OP_STATUS" = "SUCCEEDED" ]; then
                echo "   ✅ Instance deleted"
                break
            elif [ "$OP_STATUS" = "FAILED" ] || [ "$OP_STATUS" = "STOPPED" ]; then
                echo "   ⚠️  Deletion $OP_STATUS — may need manual cleanup"
                break
            fi
            echo "   ⏳ Status: $OP_STATUS (attempt $i/30)"
            sleep 10
        done
    elif [ "$INSTANCE_STATUS" = "CURRENT" ]; then
        echo "   ✅ Instance already CURRENT — no action needed"
    fi
done

echo ""
echo "✅ Step 2 complete"
echo ""

# ============================================================
# Step 3: Create fresh StackSet instances (deploys DomainAccess role)
# ============================================================
echo "═══════════════════════════════════════════════════════"
echo "Step 3: Create StackSet instances (DomainAccess role)"
echo "═══════════════════════════════════════════════════════"

for ACCOUNT_ID in "${ACCOUNTS[@]}"; do
    echo ""
    echo "📦 Account: $ACCOUNT_ID"

    # Check if instance already exists and is CURRENT
    INSTANCE_STATUS=$(aws cloudformation list-stack-instances \
        --stack-set-name "$STACKSET_NAME" \
        --stack-instance-account "$ACCOUNT_ID" \
        --stack-instance-region "$REGION" \
        --region "$REGION" \
        --query 'Summaries[0].Status' \
        --output text 2>/dev/null || echo "NONE")

    if [ "$INSTANCE_STATUS" = "CURRENT" ]; then
        echo "   ✅ Instance already CURRENT"
        continue
    fi

    echo "   Creating StackSet instance..."
    OPERATION_ID=$(aws cloudformation create-stack-instances \
        --stack-set-name "$STACKSET_NAME" \
        --accounts "$ACCOUNT_ID" \
        --regions "$REGION" \
        --region "$REGION" \
        --operation-preferences FailureToleranceCount=0,MaxConcurrentCount=1 \
        --query 'OperationId' \
        --output text)

    echo "   Operation: $OPERATION_ID"
    echo "   Waiting for deployment..."

    for i in $(seq 1 30); do
        OP_STATUS=$(aws cloudformation describe-stack-set-operation \
            --stack-set-name "$STACKSET_NAME" \
            --operation-id "$OPERATION_ID" \
            --region "$REGION" \
            --query 'StackSetOperation.Status' \
            --output text 2>/dev/null || echo "UNKNOWN")

        if [ "$OP_STATUS" = "SUCCEEDED" ]; then
            echo "   ✅ DomainAccess role deployed"
            break
        elif [ "$OP_STATUS" = "FAILED" ] || [ "$OP_STATUS" = "STOPPED" ]; then
            echo "   ❌ Deployment $OP_STATUS"
            # Show failure reason
            aws cloudformation list-stack-instance-resource-drifts \
                --stack-set-name "$STACKSET_NAME" \
                --stack-instance-account "$ACCOUNT_ID" \
                --stack-instance-region "$REGION" \
                --operation-id "$OPERATION_ID" \
                --region "$REGION" 2>/dev/null || true
            break
        fi
        echo "   ⏳ Status: $OP_STATUS (attempt $i/30)"
        sleep 10
    done
done

echo ""
echo "✅ Step 3 complete"
echo ""

# ============================================================
# Step 4: Deploy Project Role to each pool account
# ============================================================
echo "═══════════════════════════════════════════════════════"
echo "Step 4: Deploy Project Role (via OrganizationAccountAccessRole)"
echo "═══════════════════════════════════════════════════════"

PROJECT_ROLE_ENABLED=$(python3 -c "import yaml; c=yaml.safe_load(open('config.yaml')); print(str(c.get('project_role',{}).get('enabled', True)).lower())" 2>/dev/null || echo "true")

if [ "$PROJECT_ROLE_ENABLED" != "true" ]; then
    echo "⏭️  Project role disabled in config — skipping"
else
    PROJECT_ROLE_NAME=$(python3 -c "import yaml; c=yaml.safe_load(open('config.yaml')); print(c.get('project_role',{}).get('role_name', 'AmazonSageMakerProjectRole'))" 2>/dev/null)
    PROJECT_ROLE_POLICY=$(python3 -c "import yaml; c=yaml.safe_load(open('config.yaml')); print(c.get('project_role',{}).get('managed_policy_arn', 'arn:aws:iam::aws:policy/AmazonSageMakerFullAccess'))" 2>/dev/null)
    PROJECT_ROLE_TEMPLATE="templates/cloudformation/03-project-account/deploy/04-project-role.yaml"
    PROJECT_ROLE_STACK="DataZone-ProjectRole"

    echo "Role Name:   $PROJECT_ROLE_NAME"
    echo "Policy ARN:  $PROJECT_ROLE_POLICY"
    echo ""

    for ACCOUNT_ID in "${ACCOUNTS[@]}"; do
        echo "📦 Account: $ACCOUNT_ID"

        STACK_EXISTS=$(run_in_account "$ACCOUNT_ID" \
            aws cloudformation describe-stacks \
                --stack-name "$PROJECT_ROLE_STACK-$ACCOUNT_ID" \
                --region "$REGION" \
                --query 'Stacks[0].StackStatus' \
                --output text 2>/dev/null || echo "DOES_NOT_EXIST")

        if [ "$STACK_EXISTS" = "CREATE_COMPLETE" ] || [ "$STACK_EXISTS" = "UPDATE_COMPLETE" ]; then
            echo "   ✅ ProjectRole stack already exists ($STACK_EXISTS)"
        else
            echo "   📦 Deploying project role..."
            run_in_account "$ACCOUNT_ID" \
                aws cloudformation deploy \
                    --template-file "$PROJECT_ROLE_TEMPLATE" \
                    --stack-name "$PROJECT_ROLE_STACK-$ACCOUNT_ID" \
                    --parameter-overrides \
                        RoleName="$PROJECT_ROLE_NAME" \
                        ManagedPolicyArn="$PROJECT_ROLE_POLICY" \
                    --capabilities CAPABILITY_NAMED_IAM \
                    --region "$REGION" \
                    --no-fail-on-empty-changeset

            echo "   ✅ Project role deployed"
        fi
        echo ""
    done
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo "✅ All steps complete!"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Accounts fixed: ${ACCOUNTS[*]}"
echo ""
echo "Each account now has:"
echo "  - SMUS-AccountPoolFactory-StackSetExecution (CF stack)"
echo "  - SMUS-AccountPoolFactory-DomainAccess (via StackSet)"
if [ "$PROJECT_ROLE_ENABLED" = "true" ]; then
    echo "  - $PROJECT_ROLE_NAME (CF stack)"
fi
echo ""
echo "Next: Switch to Domain account and run the end-to-end test:"
echo "  eval \$(isengardcli credentials amirbo+3@amazon.com)"
echo "  ./tests/setup/create-test-project.sh"

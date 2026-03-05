#!/bin/bash
set -e

# Deploy Trust Policy StackSet to Pool Accounts
# This script must be run in the Organization Admin account
# It updates the OrganizationAccountAccessRole trust policy in all pool accounts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load configuration
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

# Extract values from config.yaml
REGION=$(grep "region:" config.yaml | awk '{print $2}')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')
ORG_ADMIN_ACCOUNT_ID=$(grep "account_id:" config.yaml | head -1 | awk '{print $2}' | tr -d '"')
TARGET_OU_ID=$(grep "target_ou_id:" config.yaml | awk '{print $2}')

echo "🚀 Deploying Trust Policy StackSet"
echo "===================================="
echo "Region: $REGION"
echo "Org Admin Account: $ORG_ADMIN_ACCOUNT_ID"
echo "Domain Account: $DOMAIN_ACCOUNT_ID"
echo "Target OU: $TARGET_OU_ID"
echo ""

# Check if we're in the correct account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "$ORG_ADMIN_ACCOUNT_ID" ]; then
    echo "❌ Error: This script must be run in the Org Admin account ($ORG_ADMIN_ACCOUNT_ID)"
    echo "   Current account: $CURRENT_ACCOUNT"
    echo ""
    echo "Switch to the Org Admin account using:"
    echo "   eval \$(isengardcli credentials amirbo+1@amazon.com)"
    exit 1
fi

# Step 1: Deploy StackSet Administration Role in Org Admin account
echo "📦 Step 1: Deploying StackSet Administration Role..."
aws cloudformation deploy \
    --template-file templates/cloudformation/01-org-admin/stackset-roles.yaml \
    --stack-name AccountPoolFactory-StackSetRoles \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION"

echo "✅ StackSet Administration Role deployed"
echo ""

# Step 2: Get list of accounts and deploy execution role to each
echo "📋 Step 2: Getting accounts in target OU..."
ACCOUNT_IDS=$(aws organizations list-accounts-for-parent \
    --parent-id "$TARGET_OU_ID" \
    --query 'Accounts[?Status==`ACTIVE`].Id' \
    --output text)

if [ -z "$ACCOUNT_IDS" ]; then
    echo "⚠️ No accounts found in target OU"
    echo "   Create accounts first using ./seed-initial-pool.sh"
    exit 0
fi

ACCOUNT_COUNT=$(echo "$ACCOUNT_IDS" | wc -w)
echo "   Found $ACCOUNT_COUNT accounts: $ACCOUNT_IDS"
echo ""

echo "📦 Step 3: Deploying StackSet Execution Role to each account..."
for ACCOUNT_ID in $ACCOUNT_IDS; do
    # Skip Domain account - it's not a pool account
    if [ "$ACCOUNT_ID" = "$DOMAIN_ACCOUNT_ID" ]; then
        echo "   Skipping Domain account $ACCOUNT_ID"
        continue
    fi
    
    echo "   Deploying to account $ACCOUNT_ID..."
    
    # Assume OrganizationAccountAccessRole in target account
    ASSUMED_ROLE=$(aws sts assume-role \
        --role-arn "arn:aws:iam::${ACCOUNT_ID}:role/OrganizationAccountAccessRole" \
        --role-session-name "StackSetSetup" \
        --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
        --output text)
    
    ACCESS_KEY=$(echo "$ASSUMED_ROLE" | awk '{print $1}')
    SECRET_KEY=$(echo "$ASSUMED_ROLE" | awk '{print $2}')
    SESSION_TOKEN=$(echo "$ASSUMED_ROLE" | awk '{print $3}')
    
    # Deploy execution role in target account
    AWS_ACCESS_KEY_ID="$ACCESS_KEY" \
    AWS_SECRET_ACCESS_KEY="$SECRET_KEY" \
    AWS_SESSION_TOKEN="$SESSION_TOKEN" \
    aws cloudformation deploy \
        --template-file templates/cloudformation/03-project-account/stackset-execution-role.yaml \
        --stack-name AccountPoolFactory-StackSetExecutionRole \
        --parameter-overrides AdministratorAccountId="$ORG_ADMIN_ACCOUNT_ID" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION"
    
    echo "   ✅ Deployed to account $ACCOUNT_ID"
done

echo "✅ StackSet Execution Roles deployed to all accounts"
echo ""

STACKSET_NAME="AccountPoolFactory-TrustPolicy"

echo "📦 Step 4: Creating Trust Policy StackSet..."

# Use SELF_MANAGED mode instead of SERVICE_MANAGED to avoid trusted access requirement
aws cloudformation create-stack-set \
    --stack-set-name "$STACKSET_NAME" \
    --template-body file://templates/cloudformation/01-org-admin/trust-policy-update.yaml \
    --parameters ParameterKey=DomainAccountId,ParameterValue="$DOMAIN_ACCOUNT_ID" \
    --capabilities CAPABILITY_NAMED_IAM \
    --permission-model SELF_MANAGED \
    --administration-role-arn "arn:aws:iam::${ORG_ADMIN_ACCOUNT_ID}:role/AWSCloudFormationStackSetAdministrationRole" \
    --execution-role-name "AWSCloudFormationStackSetExecutionRole" \
    --region "$REGION"

echo "✅ StackSet created"
echo ""

# Get list of accounts in target OU (excluding Domain account)
echo "📋 Step 5: Deploying StackSet instances..."
ALL_ACCOUNT_IDS=$(aws organizations list-accounts-for-parent \
    --parent-id "$TARGET_OU_ID" \
    --query 'Accounts[?Status==`ACTIVE`].Id' \
    --output text)

# Filter out Domain account
ACCOUNT_IDS=""
for ACCOUNT_ID in $ALL_ACCOUNT_IDS; do
    if [ "$ACCOUNT_ID" != "$DOMAIN_ACCOUNT_ID" ]; then
        ACCOUNT_IDS="$ACCOUNT_IDS $ACCOUNT_ID"
    fi
done

ACCOUNT_IDS=$(echo "$ACCOUNT_IDS" | xargs)  # Trim whitespace

if [ -z "$ACCOUNT_IDS" ]; then
    echo "⚠️ No pool accounts found in target OU"
    exit 0
fi

echo "   Deploying to pool accounts: $ACCOUNT_IDS"
echo ""

# Deploy to each account
aws cloudformation create-stack-instances \
    --stack-set-name "$STACKSET_NAME" \
    --accounts $ACCOUNT_IDS \
    --regions "$REGION" \
    --operation-preferences FailureToleranceCount=0,MaxConcurrentCount=5 \
    --region "$REGION"

echo "✅ StackSet instances deployment initiated"

echo ""
echo "📊 Checking deployment status..."
echo "   This may take a few minutes..."
echo ""

# Wait for deployment to complete
MAX_WAIT=300  # 5 minutes
WAIT_TIME=0
SLEEP_INTERVAL=10

while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    # Get operation status
    OPERATION_ID=$(aws cloudformation list-stack-set-operations \
        --stack-set-name "$STACKSET_NAME" \
        --region "$REGION" \
        --query 'Summaries[0].OperationId' \
        --output text)
    
    if [ "$OPERATION_ID" != "None" ] && [ -n "$OPERATION_ID" ]; then
        STATUS=$(aws cloudformation describe-stack-set-operation \
            --stack-set-name "$STACKSET_NAME" \
            --operation-id "$OPERATION_ID" \
            --region "$REGION" \
            --query 'StackSetOperation.Status' \
            --output text)
        
        echo "   Operation status: $STATUS"
        
        if [ "$STATUS" = "SUCCEEDED" ]; then
            echo ""
            echo "✅ StackSet deployment completed successfully!"
            break
        elif [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "STOPPED" ]; then
            echo ""
            echo "❌ StackSet deployment failed"
            echo ""
            echo "Check the CloudFormation console for details:"
            echo "   https://console.aws.amazon.com/cloudformation/home?region=$REGION#/stacksets/$STACKSET_NAME"
            exit 1
        fi
    fi
    
    sleep $SLEEP_INTERVAL
    WAIT_TIME=$((WAIT_TIME + SLEEP_INTERVAL))
done

if [ $WAIT_TIME -ge $MAX_WAIT ]; then
    echo ""
    echo "⏱️ Deployment is still in progress after 5 minutes"
    echo "   Monitor progress in the CloudFormation console:"
    echo "   https://console.aws.amazon.com/cloudformation/home?region=$REGION#/stacksets/$STACKSET_NAME"
fi

echo ""
echo "📊 StackSet Summary:"
aws cloudformation describe-stack-set \
    --stack-set-name "$STACKSET_NAME" \
    --region "$REGION" \
    --query 'StackSet.[StackSetName,Status,Description]' \
    --output table

echo ""
echo "📋 Stack Instances:"
aws cloudformation list-stack-instances \
    --stack-set-name "$STACKSET_NAME" \
    --region "$REGION" \
    --query 'Summaries[*].[Account,Region,Status]' \
    --output table

echo ""
echo "✅ Trust policy deployment complete!"
echo ""
echo "Next steps:"
echo "1. Verify all stack instances are in CREATE_COMPLETE status"
echo "2. Switch back to Domain account:"
echo "   eval \$(isengardcli credentials amirbo+3@amazon.com)"
echo "3. Retry Setup Orchestrator for failed accounts"

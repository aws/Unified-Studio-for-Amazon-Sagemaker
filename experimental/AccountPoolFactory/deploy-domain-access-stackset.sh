#!/bin/bash

# Deploy Domain Access Role StackSet
# This StackSet deploys a role in each project account that trusts the Domain account
# Must be run from Org Admin account (495869084367)
# This is deployed as an approved StackSet with SERVICE_MANAGED permissions

set -e

# Load configuration
DOMAIN_ACCOUNT_ID=$(yq eval '.aws.domain_account_id' config.yaml | tr -d '"')
DOMAIN_ID=$(yq eval '.datazone.domain_id' config.yaml)
TARGET_OU_ID=$(yq eval '.organization.target_ou_id' config.yaml)
REGION=$(yq eval '.aws.region' config.yaml)

echo "🚀 Deploying Domain Access Role StackSet (Approved StackSet)"
echo "=============================================================="
echo "Domain Account: $DOMAIN_ACCOUNT_ID"
echo "Domain ID: $DOMAIN_ID"
echo "Target OU: $TARGET_OU_ID"
echo "Region: $REGION"
echo ""

# Verify we're in the Org Admin account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "495869084367" ]; then
    echo "❌ Error: Must run from Org Admin account (495869084367)"
    echo "   Current account: $CURRENT_ACCOUNT"
    echo ""
    echo "Switch accounts with:"
    echo "  eval \$(isengardcli credentials amirbo+1@amazon.com)"
    exit 1
fi

echo "✅ Running in correct account"
echo ""

# Create or update StackSet
STACKSET_NAME="AccountPoolFactory-DomainAccessRole"
TEMPLATE_FILE="templates/cloudformation/01-org-admin/domain-access-role.yaml"

echo "📦 Creating/updating StackSet with SERVICE_MANAGED permissions..."
echo "   This StackSet will automatically deploy to all accounts in the target OU"
echo ""

# Check if StackSet exists
if aws cloudformation describe-stack-set --stack-set-name "$STACKSET_NAME" --region "$REGION" 2>/dev/null; then
    echo "ℹ️  StackSet exists, updating..."
    
    aws cloudformation update-stack-set \
        --stack-set-name "$STACKSET_NAME" \
        --template-body "file://$TEMPLATE_FILE" \
        --parameters \
            ParameterKey=DomainAccountId,ParameterValue="$DOMAIN_ACCOUNT_ID" \
            ParameterKey=DomainId,ParameterValue="$DOMAIN_ID" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION"
    
    echo "✅ StackSet updated"
else
    echo "ℹ️  Creating new StackSet with auto-deployment..."
    
    aws cloudformation create-stack-set \
        --stack-set-name "$STACKSET_NAME" \
        --template-body "file://$TEMPLATE_FILE" \
        --parameters \
            ParameterKey=DomainAccountId,ParameterValue="$DOMAIN_ACCOUNT_ID" \
            ParameterKey=DomainId,ParameterValue="$DOMAIN_ID" \
        --capabilities CAPABILITY_NAMED_IAM \
        --permission-model SERVICE_MANAGED \
        --auto-deployment Enabled=true,RetainStacksOnAccountRemoval=false \
        --region "$REGION"
    
    echo "✅ StackSet created with auto-deployment enabled"
fi

echo ""
echo "📋 Deploying StackSet instances to target OU..."
echo "   This will deploy to all existing accounts in the OU"
echo "   New accounts will get this stack automatically"
echo ""

# Deploy to target OU
OPERATION_ID=$(aws cloudformation create-stack-instances \
    --stack-set-name "$STACKSET_NAME" \
    --deployment-targets OrganizationalUnitIds="$TARGET_OU_ID" \
    --regions "$REGION" \
    --operation-preferences \
        FailureToleranceCount=0,MaxConcurrentCount=10 \
    --region "$REGION" \
    --query 'OperationId' \
    --output text)

echo "✅ StackSet deployment initiated"
echo "   Operation ID: $OPERATION_ID"
echo ""

echo "⏳ Waiting for deployment to complete..."
echo ""

# Wait for operation to complete
while true; do
    STATUS=$(aws cloudformation describe-stack-set-operation \
        --stack-set-name "$STACKSET_NAME" \
        --operation-id "$OPERATION_ID" \
        --region "$REGION" \
        --query 'StackSetOperation.Status' \
        --output text)
    
    if [ "$STATUS" == "SUCCEEDED" ]; then
        echo "✅ StackSet deployment completed successfully"
        break
    elif [ "$STATUS" == "FAILED" ] || [ "$STATUS" == "STOPPED" ]; then
        echo "❌ StackSet deployment failed with status: $STATUS"
        echo ""
        echo "Check failed instances:"
        echo "  aws cloudformation list-stack-instances --stack-set-name $STACKSET_NAME --region $REGION --query 'Summaries[?Status==\`OUTDATED\`]'"
        exit 1
    else
        echo "   Status: $STATUS"
        sleep 10
    fi
done

echo ""
echo "✅ Domain Access Role StackSet deployed!"
echo ""
echo "📊 StackSet Details:"
echo "   Name: $STACKSET_NAME"
echo "   Permission Model: SERVICE_MANAGED"
echo "   Auto-Deployment: Enabled"
echo "   Target OU: $TARGET_OU_ID"
echo ""
echo "ℹ️  This StackSet will automatically deploy to:"
echo "   - All existing accounts in the target OU"
echo "   - Any new accounts created in the target OU"
echo ""
echo "Next steps:"
echo "1. Verify deployment: aws cloudformation list-stack-instances --stack-set-name $STACKSET_NAME --region $REGION"
echo "2. Switch to Domain account: eval \$(isengardcli credentials amirbo+3@amazon.com)"
echo "3. Deploy updated Setup Orchestrator: ./deploy-infrastructure.sh"
echo "4. Test account setup: ./seed-initial-pool.sh"


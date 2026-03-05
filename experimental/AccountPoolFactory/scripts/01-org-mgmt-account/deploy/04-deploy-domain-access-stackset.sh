#!/bin/bash
set -e

# Deploy AccountPoolFactory-DomainAccess StackSet
# This StackSet creates the AccountPoolFactory-DomainAccess role in project accounts
# with ExternalId protection for secure cross-account access

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load configuration
CONFIG_FILE="$PROJECT_ROOT/config.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: config.yaml not found at $CONFIG_FILE"
    exit 1
fi

# Parse configuration
REGION=$(grep 'region:' "$CONFIG_FILE" | awk '{print $2}')
DOMAIN_ACCOUNT_ID=$(grep 'domain_account_id:' "$CONFIG_FILE" | sed 's/.*"\(.*\)".*/\1/')
DOMAIN_ID=$(grep 'domain_id:' "$CONFIG_FILE" | awk '{print $2}')

echo "🚀 Deploying AccountPoolFactory-DomainAccess StackSet..."
echo "   Region: $REGION"
echo "   Domain Account: $DOMAIN_ACCOUNT_ID"
echo "   Domain ID: $DOMAIN_ID"

# Template path
TEMPLATE_FILE="$PROJECT_ROOT/templates/cloudformation/01-org-mgmt-account/deploy/04-domain-access-stackset.yaml"

if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "❌ Error: Template not found at $TEMPLATE_FILE"
    exit 1
fi

# Check if StackSet already exists
STACKSET_NAME="AccountPoolFactory-DomainAccess"
if aws cloudformation describe-stack-set \
    --stack-set-name "$STACKSET_NAME" \
    --region "$REGION" &>/dev/null; then
    
    echo "📝 StackSet already exists, updating..."
    
    aws cloudformation update-stack-set \
        --stack-set-name "$STACKSET_NAME" \
        --template-body "file://$TEMPLATE_FILE" \
        --parameters \
            ParameterKey=DomainAccountId,ParameterValue="$DOMAIN_ACCOUNT_ID" \
            ParameterKey=DomainId,ParameterValue="$DOMAIN_ID" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION"
    
    echo "✅ StackSet updated successfully"
else
    echo "📝 Creating new StackSet..."
    
    aws cloudformation create-stack-set \
        --stack-set-name "$STACKSET_NAME" \
        --template-body "file://$TEMPLATE_FILE" \
        --parameters \
            ParameterKey=DomainAccountId,ParameterValue="$DOMAIN_ACCOUNT_ID" \
            ParameterKey=DomainId,ParameterValue="$DOMAIN_ID" \
        --capabilities CAPABILITY_NAMED_IAM \
        --permission-model SELF_MANAGED \
        --region "$REGION"
    
    echo "✅ StackSet created successfully"
fi

echo ""
echo "📋 Next Steps:"
echo "   1. StackSet instances will be deployed automatically by ProvisionAccount Lambda"
echo "   2. Each new account will get AccountPoolFactory-DomainAccess role with ExternalId: $DOMAIN_ID"
echo "   3. SetupOrchestrator will use this role (NOT OrganizationAccountAccessRole)"

#!/bin/bash
set -e

# Deploy StackSet Administration and Management Roles
# This script must be run in the Organization Admin account

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

# Load configuration
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    echo "   Copy config.yaml.template and update with your values"
    exit 1
fi

# Extract values from config.yaml
REGION=$(grep "region:" config.yaml | awk '{print $2}')
ORG_ADMIN_ACCOUNT_ID=$(grep "account_id:" config.yaml | head -1 | awk '{print $2}' | tr -d '"')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')

echo "🚀 Deploying StackSet Roles"
echo "============================"
echo "Region: $REGION"
echo "Org Admin Account: $ORG_ADMIN_ACCOUNT_ID"
echo "Domain Account: $DOMAIN_ACCOUNT_ID"
echo ""

# Check if we're in the correct account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "$ORG_ADMIN_ACCOUNT_ID" ]; then
    echo "❌ Error: This script must be run in the Organization Management account ($ORG_ADMIN_ACCOUNT_ID)"
    echo "   Current account: $CURRENT_ACCOUNT"
    echo ""
    echo "Please switch to the Organization Management account and try again."
    exit 1
fi

echo "📦 Deploying StackSet roles..."
aws cloudformation deploy \
    --template-file templates/cloudformation/01-org-mgmt-account/deploy/01-stackset-roles.yaml \
    --stack-name AccountPoolFactory-StackSetRoles \
    --parameter-overrides DomainAccountId="$DOMAIN_ACCOUNT_ID" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION"

echo ""
echo "✅ StackSet roles deployed successfully!"
echo ""
echo "📋 Deployed roles:"
echo "   - AWSCloudFormationStackSetAdministrationRole (for CloudFormation service)"
echo "   - AccountPoolFactory-StackSetManagement (for SetupOrchestrator Lambda)"
echo ""
echo "Next steps:"
echo "1. Run: ./scripts/01-org-mgmt-account/deploy/02-deploy-account-creation-role.sh"
echo "2. Run: ./scripts/01-org-mgmt-account/deploy/03-deploy-trust-policy-stackset.sh"

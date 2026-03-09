#!/bin/bash
set -e

# Deploy the AccountPoolFactory Org Admin governance stack.
# Run this ONCE in the AWS Organizations management account.
# Output: role ARNs + ExternalId — the deploy-infrastructure.sh script reads these automatically.
#
# Usage:
#   eval $(isengardcli credentials amirbo+1@amazon.com)
#   ./scripts/01-org-mgmt-account/deploy/deploy-org-admin.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

source scripts/utils/resolve-config.sh org

STACK_NAME="AccountPoolFactory-OrgAdmin"
TEMPLATE="templates/cloudformation/01-org-mgmt-account/deploy/SMUS-AccountPoolFactory-OrgAdmin.yaml"
STACKSET_NAME="SMUS-AccountPoolFactory-DomainAccess"
STACKSET_TEMPLATE="templates/cloudformation/01-org-mgmt-account/deploy/03-domain-access-stackset.yaml"

# Resolve domain account ID from the AccountCreation role if already deployed,
# otherwise require it as an argument or prompt
DOMAIN_ACCOUNT_ID="${1:-}"
if [ -z "$DOMAIN_ACCOUNT_ID" ]; then
    # Try to read from existing stack
    DOMAIN_ACCOUNT_ID=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" --region "$REGION" \
        --query 'Stacks[0].Parameters[?ParameterKey==`DomainAccountId`].ParameterValue' \
        --output text 2>/dev/null || echo "")
fi
if [ -z "$DOMAIN_ACCOUNT_ID" ] || [ "$DOMAIN_ACCOUNT_ID" = "None" ]; then
    echo "❌ Domain account ID required. Pass it as argument or deploy once with:"
    echo "   ./deploy-org-admin.sh <domain-account-id>"
    exit 1
fi

# Resolve domain ID from domain account's DataZone (needed for StackSet ExternalId)
DOMAIN_ID="${2:-}"
if [ -z "$DOMAIN_ID" ]; then
    # Try to read from existing stack
    DOMAIN_ID=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" --region "$REGION" \
        --query 'Stacks[0].Parameters[?ParameterKey==`DomainId`].ParameterValue' \
        --output text 2>/dev/null || echo "")
fi
if [ -z "$DOMAIN_ID" ] || [ "$DOMAIN_ID" = "None" ]; then
    echo "❌ Domain ID required. Pass it as second argument:"
    echo "   ./deploy-org-admin.sh <domain-account-id> <domain-id>"
    exit 1
fi

echo "Org Admin Account: $CURRENT_ACCOUNT"
echo "Domain Account:    $DOMAIN_ACCOUNT_ID"
echo "Domain ID:         $DOMAIN_ID"
echo "Target OU:         ${TARGET_OU_ID:-root} (${TARGET_OU_NAME:-})"
echo ""

# Step 1: Deploy the IAM roles CF stack
aws cloudformation deploy \
    --template-file "$TEMPLATE" \
    --stack-name "$STACK_NAME" \
    --parameter-overrides \
        DomainAccountId="$DOMAIN_ACCOUNT_ID" \
        DomainId="$DOMAIN_ID" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    --no-fail-on-empty-changeset

# Step 2: Create or update the DomainAccess StackSet
STACKSET_ADMIN_ARN="arn:aws:iam::${CURRENT_ACCOUNT}:role/SMUS-AccountPoolFactory-StackSetAdmin"

if aws cloudformation describe-stack-set --stack-set-name "$STACKSET_NAME" --region "$REGION" &>/dev/null; then
    aws cloudformation update-stack-set \
        --stack-set-name "$STACKSET_NAME" \
        --template-body "file://$STACKSET_TEMPLATE" \
        --parameters \
            ParameterKey=DomainAccountId,ParameterValue="$DOMAIN_ACCOUNT_ID" \
            ParameterKey=DomainId,ParameterValue="$DOMAIN_ID" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION" 2>/dev/null || true
else
    aws cloudformation create-stack-set \
        --stack-set-name "$STACKSET_NAME" \
        --template-body "file://$STACKSET_TEMPLATE" \
        --parameters \
            ParameterKey=DomainAccountId,ParameterValue="$DOMAIN_ACCOUNT_ID" \
            ParameterKey=DomainId,ParameterValue="$DOMAIN_ID" \
        --capabilities CAPABILITY_NAMED_IAM \
        --permission-model SELF_MANAGED \
        --administration-role-arn "$STACKSET_ADMIN_ARN" \
        --execution-role-name "SMUS-AccountPoolFactory-StackSetExecution" \
        --region "$REGION"
fi

ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`AccountCreationRoleArn`].OutputValue' \
    --output text)

EXTERNAL_ID="AccountPoolFactory-${DOMAIN_ACCOUNT_ID}"

cat <<EOF

Org Admin stack deployed.

The domain admin's deploy-infrastructure.sh reads these automatically from the
AccountPoolFactory-OrgAdmin stack outputs — no manual copy needed.

  AccountCreationRoleArn : $ROLE_ARN
  ExternalId             : $EXTERNAL_ID

Domain admin next step:
  eval \$(isengardcli credentials amirbo+3@amazon.com)
  ./scripts/02-domain-account/deploy/01-deploy-infrastructure.sh

EOF

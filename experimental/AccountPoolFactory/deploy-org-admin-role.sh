#!/bin/bash
set -e

# Deploy Account Creation Role in Org Admin Account
# This role allows Pool Manager Lambda in Domain account to create AWS accounts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load configuration
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

REGION=$(grep "region:" config.yaml | awk '{print $2}')
ORG_ADMIN_ACCOUNT_ID=$(grep "account_id:" config.yaml | head -1 | awk '{print $2}' | tr -d '"')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')

echo "🚀 Deploying Account Creation Role in Org Admin Account"
echo "========================================================"
echo "Org Admin Account: $ORG_ADMIN_ACCOUNT_ID"
echo "Domain Account: $DOMAIN_ACCOUNT_ID"
echo "Region: $REGION"
echo ""

# Check if we're running in the correct account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "$ORG_ADMIN_ACCOUNT_ID" ]; then
    echo "⚠️  WARNING: Current account ($CURRENT_ACCOUNT) is not the Org Admin account ($ORG_ADMIN_ACCOUNT_ID)"
    echo "Please switch to the Org Admin account credentials and run again"
    exit 1
fi

echo "✅ Running in correct account"
echo ""

# Deploy the role
echo "📦 Deploying cross-account role..."
aws cloudformation deploy \
    --template-file templates/cloudformation/01-org-admin/account-creation-role.yaml \
    --stack-name AccountPoolFactory-AccountCreationRole \
    --parameter-overrides \
        DomainAccountId="$DOMAIN_ACCOUNT_ID" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION"

echo ""
echo "✅ Role deployed successfully"
echo ""

# Get stack outputs
ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-AccountCreationRole \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`RoleArn`].OutputValue' \
    --output text)

EXTERNAL_ID=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-AccountCreationRole \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`ExternalId`].OutputValue' \
    --output text)

echo "📊 Role Details:"
echo "  Role ARN: $ROLE_ARN"
echo "  External ID: $EXTERNAL_ID"
echo ""

# Save to file for reference
cat > org-admin-role-details.json <<EOF
{
  "roleArn": "$ROLE_ARN",
  "externalId": "$EXTERNAL_ID",
  "orgAdminAccountId": "$ORG_ADMIN_ACCOUNT_ID",
  "domainAccountId": "$DOMAIN_ACCOUNT_ID",
  "createdAt": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

echo "📄 Role details saved to: org-admin-role-details.json"
echo ""

echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Switch back to Domain account credentials"
echo "2. Update SSM parameter with role ARN:"
echo "   aws ssm put-parameter --name /AccountPoolFactory/PoolManager/OrgAdminRoleArn --value '$ROLE_ARN' --type String --region $REGION"
echo "3. Update SSM parameter with external ID:"
echo "   aws ssm put-parameter --name /AccountPoolFactory/PoolManager/ExternalId --value '$EXTERNAL_ID' --type String --region $REGION"
echo "4. Trigger pool replenishment: ./seed-initial-pool.sh"
echo ""

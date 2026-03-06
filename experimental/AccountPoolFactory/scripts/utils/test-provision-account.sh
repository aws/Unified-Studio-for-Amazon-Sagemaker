#!/bin/bash
set -e

# Test ProvisionAccount Lambda directly
# This script tests account provisioning without going through PoolManager

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Load configuration
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

REGION=$(grep "region:" config.yaml | awk '{print $2}')
ORG_ADMIN_ACCOUNT_ID=$(grep "account_id:" config.yaml | head -1 | awk '{print $2}' | tr -d '"')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')
DOMAIN_ID=$(grep "domain_id:" config.yaml | awk '{print $2}')
TARGET_OU_ID=$(grep "target_ou_id:" config.yaml | awk '{print $2}')

echo "🧪 Testing ProvisionAccount Lambda"
echo "==================================="
echo "Region: $REGION"
echo "Org Admin Account: $ORG_ADMIN_ACCOUNT_ID"
echo "Domain Account: $DOMAIN_ACCOUNT_ID"
echo "Domain ID: $DOMAIN_ID"
echo "Target OU: $TARGET_OU_ID"
echo ""

# Verify we're in the correct account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "$ORG_ADMIN_ACCOUNT_ID" ]; then
    echo "❌ Error: Must run in Org Admin account ($ORG_ADMIN_ACCOUNT_ID)"
    echo "   Current account: $CURRENT_ACCOUNT"
    echo ""
    echo "Switch accounts with:"
    echo "   eval \$(isengardcli credentials amirbo+1@amazon.com)"
    exit 1
fi

echo "✅ Running in correct account"
echo ""

# Generate unique test account details
UNIQUE_ID=$(uuidgen | tr '[:upper:]' '[:lower:]' | cut -c1-8)
ACCOUNT_NAME="smus-test-provision-${UNIQUE_ID}"
ACCOUNT_EMAIL="amirbo+pool-test+${UNIQUE_ID}@amazon.com"

echo "📧 Test Account Details:"
echo "   Name: $ACCOUNT_NAME"
echo "   Email: $ACCOUNT_EMAIL"
echo ""

# Create payload
PAYLOAD=$(cat <<EOF
{
  "action": "provision",
  "accountName": "$ACCOUNT_NAME",
  "accountEmail": "$ACCOUNT_EMAIL",
  "ouId": "$TARGET_OU_ID",
  "domainId": "$DOMAIN_ID",
  "domainAccountId": "$DOMAIN_ACCOUNT_ID",
  "orgAdminAccountId": "$ORG_ADMIN_ACCOUNT_ID"
}
EOF
)

echo "📤 Invoking ProvisionAccount Lambda..."
echo ""

# Invoke Lambda and capture response
RESPONSE_FILE="/tmp/provision-account-response.json"
aws lambda invoke \
    --function-name ProvisionAccount \
    --cli-binary-format raw-in-base64-out \
    --payload "$PAYLOAD" \
    --region "$REGION" \
    "$RESPONSE_FILE" \
    > /dev/null 2>&1

# Check if response file was created
if [ ! -f "$RESPONSE_FILE" ]; then
    echo "❌ Lambda invocation failed - no response file created"
    exit 1
fi

# Parse response
STATUS=$(jq -r '.status' "$RESPONSE_FILE" 2>/dev/null || echo "ERROR")
MESSAGE=$(jq -r '.message' "$RESPONSE_FILE" 2>/dev/null || echo "Unknown error")
ACCOUNT_ID=$(jq -r '.accountId' "$RESPONSE_FILE" 2>/dev/null || echo "null")

echo "📥 Response:"
cat "$RESPONSE_FILE" | jq '.'
echo ""

# Check result
if [ "$STATUS" = "SUCCESS" ]; then
    echo "✅ Account provisioned successfully!"
    echo ""
    echo "📋 Account Details:"
    echo "   Account ID: $ACCOUNT_ID"
    echo "   Account Name: $ACCOUNT_NAME"
    echo "   Account Email: $ACCOUNT_EMAIL"
    echo ""
    echo "🔍 Verify account in Organizations:"
    echo "   aws organizations describe-account --account-id $ACCOUNT_ID --region $REGION"
    echo ""
    echo "🔍 Check StackSet instance:"
    echo "   aws cloudformation list-stack-instances --stack-set-name SMUS-AccountPoolFactory-DomainAccess --stack-instance-account $ACCOUNT_ID --stack-instance-region $REGION --region $REGION"
    echo ""
else
    echo "❌ Account provisioning failed!"
    echo "   Status: $STATUS"
    echo "   Message: $MESSAGE"
    echo ""
    
    # Check Lambda logs for more details
    echo "📋 Recent Lambda logs:"
    aws logs tail /aws/lambda/ProvisionAccount --since 2m --region "$REGION" --format short | tail -30
    exit 1
fi

# Clean up
rm -f "$RESPONSE_FILE"

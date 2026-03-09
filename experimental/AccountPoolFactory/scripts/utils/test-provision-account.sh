#!/bin/bash
set -e

# Test ProvisionAccount Lambda directly
# ProvisionAccount now runs in the DOMAIN account (not Org Admin).
# Run this script from the Domain account.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

source scripts/utils/resolve-config.sh domain

echo "🧪 Testing ProvisionAccount Lambda (runs in Domain account)"
echo "============================================================"
echo "Region: $REGION  |  Domain Account: $DOMAIN_ACCOUNT_ID"
echo ""

if [ "$CURRENT_ACCOUNT" != "$DOMAIN_ACCOUNT_ID" ]; then
    echo "❌ Must run in Domain account ($DOMAIN_ACCOUNT_ID), currently in $CURRENT_ACCOUNT"
    echo "   eval \$(isengardcli credentials amirbo+3@amazon.com)"
    exit 1
fi

UNIQUE_ID=$(python3 -c "import uuid; print(str(uuid.uuid4()).replace('-','')[:8])")
ACCOUNT_NAME="smus-test-provision-${UNIQUE_ID}"
ACCOUNT_EMAIL="amirbo+pool-test+${UNIQUE_ID}@amazon.com"

echo "Account Name:  $ACCOUNT_NAME"
echo "Account Email: $ACCOUNT_EMAIL"
echo ""

PAYLOAD=$(cat <<EOF
{
  "action": "provision",
  "accountName": "$ACCOUNT_NAME",
  "accountEmail": "$ACCOUNT_EMAIL",
  "ouId": "$TARGET_OU_ID",
  "domainId": "$DOMAIN_ID",
  "domainAccountId": "$DOMAIN_ACCOUNT_ID"
}
EOF
)

echo "📤 Invoking ProvisionAccount Lambda (timeout ~10 min)..."
RESPONSE_FILE="/tmp/provision-account-response.json"
aws lambda invoke \
    --function-name ProvisionAccount \
    --cli-binary-format raw-in-base64-out \
    --cli-read-timeout 660 \
    --payload "$PAYLOAD" \
    --region "$REGION" \
    "$RESPONSE_FILE" > /dev/null

cat "$RESPONSE_FILE" | python3 -m json.tool
STATUS=$(python3 -c "import json; print(json.load(open('$RESPONSE_FILE')).get('status','ERROR'))")

if [ "$STATUS" = "SUCCESS" ]; then
    ACCOUNT_ID=$(python3 -c "import json; print(json.load(open('$RESPONSE_FILE')).get('accountId',''))")
    echo ""
    echo "✅ Account provisioned: $ACCOUNT_ID"
    echo "   aws cloudformation list-stack-instances --stack-set-name SMUS-AccountPoolFactory-DomainAccess --stack-instance-account $ACCOUNT_ID --stack-instance-region $REGION --region $REGION"
else
    echo "❌ Provisioning failed — check logs:"
    echo "   aws logs tail /aws/lambda/ProvisionAccount --region $REGION"
    exit 1
fi
rm -f "$RESPONSE_FILE"

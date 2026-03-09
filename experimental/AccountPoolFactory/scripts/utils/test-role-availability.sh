#!/bin/bash
# Test script to verify OrganizationAccountAccessRole availability timing in new accounts.
# Run this in the Org Admin Account (495869084367) — it tests direct role assumption
# which mirrors what ProvisionAccount Lambda does via the AccountCreation role chain.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "🧪 Testing OrganizationAccountAccessRole Availability"
echo "====================================================="
echo ""

source scripts/utils/resolve-config.sh org

ORG_ADMIN_ACCOUNT_ID="495869084367"

# Verify we're in the correct account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "ERROR")
if [ "$CURRENT_ACCOUNT" = "ERROR" ]; then
    echo "❌ Cannot get current account identity"
    exit 1
fi

echo "Current Account: $CURRENT_ACCOUNT"
if [ "$CURRENT_ACCOUNT" != "$ORG_ADMIN_ACCOUNT_ID" ]; then
    echo "❌ Error: This script must be run in the Org Admin account ($ORG_ADMIN_ACCOUNT_ID)"
    echo "   Switch using: eval \$(isengardcli credentials amirbo+1@amazon.com)"
    exit 1
fi
echo "✅ Running in correct account"
echo ""

# Check if there are any recently created accounts to test
echo "🔍 Looking for recently created test accounts..."
RECENT_ACCOUNTS=$(aws dynamodb scan \
    --table-name AccountPoolFactory-AccountState \
    --region "$REGION" \
    --filter-expression "attribute_exists(accountId)" \
    --projection-expression "accountId" \
    --max-items 3 2>/dev/null | jq -r '.Items[].accountId.S' || echo "")

if [ -z "$RECENT_ACCOUNTS" ]; then
    echo "⚠️  No test accounts found in DynamoDB"
    echo ""
    echo "To test role availability timing:"
    echo "1. Switch to Domain account: eval \$(isengardcli credentials amirbo+3@amazon.com)"
    echo "2. Trigger replenishment: aws lambda invoke --function-name PoolManager --region $REGION --cli-binary-format raw-in-base64-out --payload '{\"action\":\"force_replenishment\"}' response.json"
    echo "3. Monitor logs: aws logs tail /aws/lambda/ProvisionAccount --region $REGION --follow"
    echo ""
    exit 0
fi

echo "Found test accounts:"
echo "$RECENT_ACCOUNTS" | while read ACCOUNT_ID; do
    echo "  - $ACCOUNT_ID"
done
echo ""

# Test role availability for each account
echo "🧪 Testing role availability..."
echo ""

for ACCOUNT_ID in $RECENT_ACCOUNTS; do
    echo "Testing account: $ACCOUNT_ID"
    ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/OrganizationAccountAccessRole"
    
    START_TIME=$(date +%s)
    MAX_WAIT=120
    ATTEMPT=0
    
    while [ $(($(date +%s) - START_TIME)) -lt $MAX_WAIT ]; do
        ATTEMPT=$((ATTEMPT + 1))
        ELAPSED=$(($(date +%s) - START_TIME))
        
        # Try to assume the role
        if aws sts assume-role \
            --role-arn "$ROLE_ARN" \
            --role-session-name "RoleAvailabilityTest" \
            --duration-seconds 900 \
            --region "$REGION" > /dev/null 2>&1; then
            
            echo "  ✅ Role available after ${ELAPSED} seconds (${ATTEMPT} attempts)"
            break
        else
            if [ $((ATTEMPT % 6)) -eq 0 ]; then
                echo "  ⏳ Attempt ${ATTEMPT} (${ELAPSED}s): Role not ready yet..."
            fi
            sleep 5
        fi
    done
    
    if [ $(($(date +%s) - START_TIME)) -ge $MAX_WAIT ]; then
        echo "  ❌ Role did not become available after ${MAX_WAIT} seconds"
    fi
    
    echo ""
done

echo "✅ Test complete"
echo ""
echo "Summary:"
echo "- Typical wait time: 30-60 seconds"
echo "- ProvisionAccount Lambda configured with 120 second timeout"
echo "- Polls every 5 seconds with progress logging every 30 seconds"
echo ""

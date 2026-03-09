#!/bin/bash
set -e

# Check Account Pool status — accounts by state + recent Lambda activity

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

source scripts/utils/resolve-config.sh domain

echo "📊 Account Pool Status"
echo "======================"
echo ""

# Count by state
echo "Accounts by state:"
for STATE in AVAILABLE ASSIGNED CREATING PROVISIONING DEPROVISIONING FAILED; do
    COUNT=$(aws dynamodb query \
        --table-name AccountPoolFactory-AccountState \
        --index-name StateIndex \
        --key-condition-expression '#state = :state' \
        --expression-attribute-names '{"#state":"state"}' \
        --expression-attribute-values "{\":state\":{\"S\":\"$STATE\"}}" \
        --select COUNT \
        --region "$REGION" \
        --query 'Count' \
        --output text 2>/dev/null || echo "0")
    if [ "$COUNT" != "0" ]; then
        echo "  $STATE: $COUNT"
    fi
done

echo ""

# Show all accounts
TOTAL=$(aws dynamodb scan \
    --table-name AccountPoolFactory-AccountState \
    --region "$REGION" \
    --select COUNT \
    --query 'Count' \
    --output text 2>/dev/null || echo "0")

echo "Total accounts: $TOTAL"
echo ""

if [ "$TOTAL" != "0" ]; then
    echo "Account details:"
    aws dynamodb scan \
        --table-name AccountPoolFactory-AccountState \
        --region "$REGION" \
        --query 'Items[*].{AccountId:accountId.S,State:state.S,ProjectId:projectId.S}' \
        --output table
fi

echo ""

# Recent Lambda activity
echo "Recent PoolManager activity (last 15 min):"
aws logs tail /aws/lambda/PoolManager \
    --since 15m \
    --format short \
    --region "$REGION" 2>/dev/null | tail -20 || echo "  No recent logs"

echo ""
echo "Recent AccountProvider activity (last 15 min):"
aws logs tail /aws/lambda/AccountProvider \
    --since 15m \
    --format short \
    --region "$REGION" 2>/dev/null | tail -20 || echo "  No recent logs"

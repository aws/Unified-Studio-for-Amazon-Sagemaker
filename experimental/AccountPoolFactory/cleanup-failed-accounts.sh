#!/bin/bash
set -e

# Cleanup Failed Accounts
# This script removes failed accounts from DynamoDB to unblock pool replenishment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load configuration
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

REGION=$(grep "region:" config.yaml | awk '{print $2}')
TABLE_NAME="AccountPoolFactory-AccountState"

echo "🧹 Cleaning up failed accounts"
echo "==============================="
echo "Region: $REGION"
echo "Table: $TABLE_NAME"
echo ""

# Get all failed accounts
echo "📋 Scanning for failed accounts..."
FAILED_ACCOUNTS=$(aws dynamodb scan \
    --table-name "$TABLE_NAME" \
    --filter-expression "#s = :failed" \
    --expression-attribute-names '{"#s":"state"}' \
    --expression-attribute-values '{":failed":{"S":"FAILED"}}' \
    --region "$REGION" \
    --output json)

ACCOUNT_COUNT=$(echo "$FAILED_ACCOUNTS" | jq -r '.Items | length')

if [ "$ACCOUNT_COUNT" -eq 0 ]; then
    echo "✅ No failed accounts found"
    exit 0
fi

echo "Found $ACCOUNT_COUNT failed account(s):"
echo ""
echo "$FAILED_ACCOUNTS" | jq -r '.Items[] | "  - Account: \(.accountId.S)\n    Failed Step: \(.failedStep.S // "unknown")\n    Error: \(.errorMessage.S // "N/A" | .[0:100])...\n"'

echo ""
read -p "Delete these $ACCOUNT_COUNT failed account(s) from DynamoDB? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Aborted"
    exit 1
fi

echo ""
echo "🗑️  Deleting failed accounts..."

DELETED=0
FAILED=0

echo "$FAILED_ACCOUNTS" | jq -c '.Items[]' | while read -r item; do
    ACCOUNT_ID=$(echo "$item" | jq -r '.accountId.S')
    TIMESTAMP=$(echo "$item" | jq -r '.timestamp.N // .timestamp.S')
    
    echo "  Deleting account $ACCOUNT_ID (timestamp: $TIMESTAMP)..."
    
    # Determine timestamp type
    if echo "$item" | jq -e '.timestamp.N' > /dev/null 2>&1; then
        TIMESTAMP_TYPE="N"
    else
        TIMESTAMP_TYPE="S"
    fi
    
    if aws dynamodb delete-item \
        --table-name "$TABLE_NAME" \
        --key "{\"accountId\":{\"S\":\"$ACCOUNT_ID\"},\"timestamp\":{\"$TIMESTAMP_TYPE\":\"$TIMESTAMP\"}}" \
        --region "$REGION" 2>/dev/null; then
        echo "    ✅ Deleted"
        DELETED=$((DELETED + 1))
    else
        echo "    ❌ Failed to delete"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "============================================"
echo "✅ Cleanup complete"
echo "   Deleted: $DELETED"
echo "   Failed: $FAILED"
echo ""
echo "You can now trigger pool replenishment:"
echo "  ./seed-initial-pool.sh"


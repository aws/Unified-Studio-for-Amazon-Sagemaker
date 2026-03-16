#!/bin/bash
# Clear all items from AccountPoolFactory-AccountState DynamoDB table
# Run this in the Domain Account

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

source "$SCRIPT_DIR/../resolve-config.sh"

TABLE_NAME="AccountPoolFactory-AccountState"

echo "🗑️  Clear DynamoDB Table"
echo "========================"
echo ""
echo "Configuration:"
echo "  Region: $REGION"
echo "  Domain Account: $DOMAIN_ACCOUNT_ID"
echo "  Table: $TABLE_NAME"
echo ""

# Verify we're in the correct account
if [ "$CURRENT_ACCOUNT" != "$DOMAIN_ACCOUNT_ID" ]; then
    echo "⚠️  WARNING: Not in Domain Account"
    echo "   Expected: $DOMAIN_ACCOUNT_ID"
    echo "   Current:  $CURRENT_ACCOUNT"
    echo "   Switch using: eval \$(isengardcli credentials amirbo+3@amazon.com)"
    exit 1
fi
echo "✅ In correct account"
echo ""

# Check if table exists
TABLE_STATUS=$(aws dynamodb describe-table \
    --table-name "$TABLE_NAME" \
    --region "$REGION" \
    --query 'Table.TableStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$TABLE_STATUS" = "NOT_FOUND" ]; then
    echo "❌ Table NOT found: $TABLE_NAME"
    exit 1
fi

echo "Table Status: $TABLE_STATUS"
echo ""

# Get current item count
ITEM_COUNT=$(aws dynamodb scan \
    --table-name "$TABLE_NAME" \
    --region "$REGION" \
    --select COUNT \
    --query 'Count' \
    --output text 2>/dev/null || echo "0")

echo "Current items in table: $ITEM_COUNT"
echo ""

if [ "$ITEM_COUNT" = "0" ]; then
    echo "✅ Table is already empty"
    exit 0
fi

# Confirm deletion (skip if --force flag provided)
if [ "$1" != "--force" ]; then
    echo "⚠️  WARNING: This will delete ALL items from the table!"
    echo ""
    read -p "Are you sure you want to proceed? (yes/no): " CONFIRM

    if [ "$CONFIRM" != "yes" ]; then
        echo "❌ Operation cancelled"
        exit 0
    fi
else
    echo "🚀 Force mode enabled - skipping confirmation"
fi

echo ""
echo "🗑️  Deleting items..."
echo ""

# Scan and delete all items using correct key schema (accountId + timestamp)
DELETED_COUNT=0

# Get all items with their keys
ITEMS=$(aws dynamodb scan \
    --table-name "$TABLE_NAME" \
    --region "$REGION" \
    --query 'Items[*].[accountId.S, timestamp.N]' \
    --output text 2>/dev/null || echo "")

if [ -z "$ITEMS" ]; then
    echo "✅ No items to delete"
else
    echo "$ITEMS" | while read ACCOUNT_ID TIMESTAMP; do
        if [ -n "$ACCOUNT_ID" ] && [ -n "$TIMESTAMP" ]; then
            aws dynamodb delete-item \
                --table-name "$TABLE_NAME" \
                --key "{\"accountId\":{\"S\":\"$ACCOUNT_ID\"},\"timestamp\":{\"N\":\"$TIMESTAMP\"}}" \
                --region "$REGION" 2>/dev/null

            DELETED_COUNT=$((DELETED_COUNT + 1))
            echo "  ✓ Deleted: $ACCOUNT_ID (timestamp: $TIMESTAMP)"
        fi
    done
fi

echo ""
echo "✅ Table cleared successfully"
echo ""

# Verify table is empty
FINAL_COUNT=$(aws dynamodb scan \
    --table-name "$TABLE_NAME" \
    --region "$REGION" \
    --select COUNT \
    --query 'Count' \
    --output text 2>/dev/null || echo "0")

echo "Final item count: $FINAL_COUNT"
echo ""

if [ "$FINAL_COUNT" = "0" ]; then
    echo "✅ Verification passed - table is empty"
else
    echo "⚠️  Warning: Table still has $FINAL_COUNT items"
    echo "   You may need to run this script again"
fi

echo ""
echo "Next steps:"
echo "1. Verify infrastructure is ready (run verify scripts)"
echo "2. Seed the pool: cd tests/setup && ./03-seed-test-accounts.sh"
echo "3. Monitor: aws logs tail /aws/lambda/PoolManager --follow --region $REGION"
echo ""

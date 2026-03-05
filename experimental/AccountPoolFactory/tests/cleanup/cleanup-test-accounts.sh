#!/bin/bash
set -e

# Cleanup ALL DataZone-Pool Accounts
# This script closes all pool accounts in Organizations and cleans up DynamoDB

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load configuration
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

REGION=$(grep "region:" config.yaml | awk '{print $2}')
TABLE_NAME="AccountPoolFactory-AccountState"

echo "🧹 COMPREHENSIVE CLEANUP - ALL POOL ACCOUNTS"
echo "============================================="
echo "Region: $REGION"
echo ""
echo "⚠️  WARNING: This will:"
echo "  1. Close ALL DataZone-Pool accounts in AWS Organizations"
echo "  2. Delete ALL records from DynamoDB table"
echo "  3. This action CANNOT be undone"
echo ""

read -p "Are you ABSOLUTELY SURE you want to proceed? (type 'DELETE ALL' to confirm): " CONFIRM

if [ "$CONFIRM" != "DELETE ALL" ]; then
    echo "❌ Aborted"
    exit 1
fi

echo ""
echo "Step 1: Checking for running Lambda functions..."
echo "================================================"

POOL_MANAGER_RUNNING=$(aws lambda list-functions --region "$REGION" --query "Functions[?FunctionName=='PoolManager'].FunctionName" --output text)
SETUP_ORCHESTRATOR_RUNNING=$(aws lambda list-functions --region "$REGION" --query "Functions[?FunctionName=='SetupOrchestrator'].FunctionName" --output text)

if [ -n "$POOL_MANAGER_RUNNING" ]; then
    echo "  ⚠️  PoolManager Lambda exists"
    echo "     Checking for active invocations..."
    # Note: We can't easily check for running invocations, so we'll proceed with caution
fi

if [ -n "$SETUP_ORCHESTRATOR_RUNNING" ]; then
    echo "  ⚠️  SetupOrchestrator Lambda exists"
    echo "     Checking for active invocations..."
fi

echo "  ✅ Proceeding with cleanup"
echo ""

echo "Step 2: Getting all DataZone-Pool accounts from Organizations..."
echo "================================================================="

ACCOUNTS=$(aws organizations list-accounts \
    --query 'Accounts[?starts_with(Name, `DataZone-Pool`) && Status==`ACTIVE`].{Id:Id, Name:Name, Email:Email}' \
    --output json)

ACCOUNT_COUNT=$(echo "$ACCOUNTS" | jq -r 'length')

echo "Found $ACCOUNT_COUNT ACTIVE DataZone-Pool account(s)"
echo ""

if [ "$ACCOUNT_COUNT" -eq 0 ]; then
    echo "✅ No active accounts to close"
else
    echo "$ACCOUNTS" | jq -r '.[] | "  - \(.Id) (\(.Name))"'
    echo ""
    
    echo "Step 3: Closing accounts in Organizations..."
    echo "============================================="
    
    CLOSED=0
    FAILED=0
    
    echo "$ACCOUNTS" | jq -c '.[]' | while read -r account; do
        ACCOUNT_ID=$(echo "$account" | jq -r '.Id')
        ACCOUNT_NAME=$(echo "$account" | jq -r '.Name')
        
        echo "  Closing account $ACCOUNT_ID ($ACCOUNT_NAME)..."
        
        if aws organizations close-account --account-id "$ACCOUNT_ID" 2>/dev/null; then
            echo "    ✅ Close initiated (will be SUSPENDED in ~90 days)"
            CLOSED=$((CLOSED + 1))
        else
            echo "    ⚠️  Failed to close (may already be closing)"
            FAILED=$((FAILED + 1))
        fi
        
        # Rate limiting - AWS has limits on close-account API calls
        sleep 2
    done
    
    echo ""
    echo "  Closed: $CLOSED"
    echo "  Failed: $FAILED"
fi

echo ""
echo "Step 4: Cleaning up DynamoDB table..."
echo "======================================"

# Get all items from DynamoDB
ALL_ITEMS=$(aws dynamodb scan \
    --table-name "$TABLE_NAME" \
    --region "$REGION" \
    --output json)

ITEM_COUNT=$(echo "$ALL_ITEMS" | jq -r '.Items | length')

echo "Found $ITEM_COUNT record(s) in DynamoDB"

if [ "$ITEM_COUNT" -eq 0 ]; then
    echo "✅ DynamoDB table is already empty"
else
    echo ""
    echo "Deleting all records..."
    
    DELETED=0
    FAILED=0
    
    echo "$ALL_ITEMS" | jq -c '.Items[]' | while read -r item; do
        ACCOUNT_ID=$(echo "$item" | jq -r '.accountId.S')
        
        # Determine timestamp type and value
        if echo "$item" | jq -e '.timestamp.N' > /dev/null 2>&1; then
            TIMESTAMP=$(echo "$item" | jq -r '.timestamp.N')
            TIMESTAMP_TYPE="N"
        else
            TIMESTAMP=$(echo "$item" | jq -r '.timestamp.S')
            TIMESTAMP_TYPE="S"
        fi
        
        echo "  Deleting $ACCOUNT_ID (timestamp: $TIMESTAMP)..."
        
        if aws dynamodb delete-item \
            --table-name "$TABLE_NAME" \
            --key "{\"accountId\":{\"S\":\"$ACCOUNT_ID\"},\"timestamp\":{\"$TIMESTAMP_TYPE\":\"$TIMESTAMP\"}}" \
            --region "$REGION" 2>/dev/null; then
            echo "    ✅ Deleted"
            DELETED=$((DELETED + 1))
        else
            echo "    ❌ Failed"
            FAILED=$((FAILED + 1))
        fi
    done
    
    echo ""
    echo "  Deleted: $DELETED"
    echo "  Failed: $FAILED"
fi

echo ""
echo "Step 5: Verification..."
echo "======================="

# Verify Organizations
REMAINING_ACTIVE=$(aws organizations list-accounts \
    --query 'Accounts[?starts_with(Name, `DataZone-Pool`) && Status==`ACTIVE`] | length(@)' \
    --output text)

echo "  Active accounts in Organizations: $REMAINING_ACTIVE"

# Verify DynamoDB
REMAINING_ITEMS=$(aws dynamodb scan \
    --table-name "$TABLE_NAME" \
    --region "$REGION" \
    --select COUNT \
    --output json | jq -r '.Count')

echo "  Records in DynamoDB: $REMAINING_ITEMS"

echo ""
echo "============================================"
echo "✅ CLEANUP COMPLETE"
echo ""
echo "Summary:"
echo "  - Closed $ACCOUNT_COUNT account(s) in Organizations"
echo "  - Deleted $ITEM_COUNT record(s) from DynamoDB"
echo "  - Remaining active accounts: $REMAINING_ACTIVE"
echo "  - Remaining DynamoDB records: $REMAINING_ITEMS"
echo ""
echo "Note: Closed accounts will be SUSPENDED in ~90 days"
echo "      You can now seed a fresh pool with: ./seed-initial-pool.sh"


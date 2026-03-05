#!/bin/bash
set -e

# Cleanup Account Pool Factory Infrastructure
# This script removes all infrastructure components

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load configuration
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

REGION=$(grep "region:" config.yaml | awk '{print $2}')

echo "🧹 Cleaning up Account Pool Factory Infrastructure"
echo "=================================================="
echo "Region: $REGION"
echo ""

# Warning
echo "⚠️  WARNING: This will delete all infrastructure components"
echo "⚠️  This does NOT close accounts in the pool"
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Cleanup cancelled"
    exit 0
fi

# Delete CloudFormation stack
echo ""
echo "🗑️  Deleting infrastructure stack..."
aws cloudformation delete-stack \
    --stack-name AccountPoolFactory-Infrastructure \
    --region "$REGION"

echo "⏳ Waiting for stack deletion..."
aws cloudformation wait stack-delete-complete \
    --stack-name AccountPoolFactory-Infrastructure \
    --region "$REGION"

echo "✅ Infrastructure stack deleted"

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "Note: Accounts in the pool are NOT closed by this script."
echo "To close accounts, use the Pool Manager delete-failed-account API or AWS Organizations console."

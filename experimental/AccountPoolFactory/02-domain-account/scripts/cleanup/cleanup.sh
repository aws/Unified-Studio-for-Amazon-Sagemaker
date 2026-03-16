#!/bin/bash
set -e

# Cleanup Account Pool Factory Infrastructure
# This script removes all infrastructure components from the domain account

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

source "$SCRIPT_DIR/../resolve-config.sh"

echo "🧹 Cleaning up Account Pool Factory Infrastructure"
echo "=================================================="
echo "Region: $REGION"
echo "Domain Account: $DOMAIN_ACCOUNT_ID"
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

# Delete per-pool SSM parameters
echo ""
echo "🗑️  Deleting per-pool SSM parameters..."
for pool_name in $POOL_NAMES; do
    echo "   Pool: $pool_name"
    for PARAM in MinimumPoolSize TargetPoolSize ReclaimStrategy ProjectProfileName OUId OUName StackSets; do
        aws ssm delete-parameter \
            --name "/AccountPoolFactory/Pools/${pool_name}/${PARAM}" \
            --region "$REGION" 2>/dev/null || true
    done
done

# Delete legacy SSM parameters
echo "   Deleting legacy SSM params..."
for PARAM in MinimumPoolSize TargetPoolSize ReclaimStrategy PoolName NamePrefix MaxConcurrentSetups MaxRecycleRetries MaxConcurrentRecycles; do
    aws ssm delete-parameter \
        --name "/AccountPoolFactory/PoolManager/${PARAM}" \
        --region "$REGION" 2>/dev/null || true
done
echo "✅ SSM parameters deleted"

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

#!/bin/bash
set -e

# Cleanup Organization Management Account Resources
# This script removes all Account Pool Factory resources from the Org Admin account

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

# Load configuration
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

REGION=$(grep "region:" config.yaml | awk '{print $2}')
ORG_ADMIN_ACCOUNT_ID=$(grep "account_id:" config.yaml | head -1 | awk '{print $2}' | tr -d '"')

echo "🧹 Cleaning up Organization Management Account Resources"
echo "========================================================="
echo "Region: $REGION"
echo "Org Admin Account: $ORG_ADMIN_ACCOUNT_ID"
echo ""

# Check if we're in the correct account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "$ORG_ADMIN_ACCOUNT_ID" ]; then
    echo "❌ Error: This script must be run in the Organization Management account ($ORG_ADMIN_ACCOUNT_ID)"
    echo "   Current account: $CURRENT_ACCOUNT"
    exit 1
fi

echo "⚠️  WARNING: This will delete all Account Pool Factory resources in this account"
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cleanup cancelled"
    exit 0
fi

echo ""

# Step 1: Delete StackSet instances
echo "📦 Step 1: Deleting StackSet instances..."
STACKSET_NAME="AccountPoolFactory-TrustPolicy"

# Check if StackSet exists
if aws cloudformation describe-stack-set --stack-set-name "$STACKSET_NAME" --region "$REGION" &>/dev/null; then
    # Get all stack instances
    INSTANCES=$(aws cloudformation list-stack-instances \
        --stack-set-name "$STACKSET_NAME" \
        --region "$REGION" \
        --query 'Summaries[*].[Account,Region]' \
        --output text)
    
    if [ -n "$INSTANCES" ]; then
        ACCOUNTS=$(echo "$INSTANCES" | awk '{print $1}' | sort -u | tr '\n' ' ')
        REGIONS=$(echo "$INSTANCES" | awk '{print $2}' | sort -u | tr '\n' ' ')
        
        echo "   Deleting instances in accounts: $ACCOUNTS"
        echo "   Regions: $REGIONS"
        
        aws cloudformation delete-stack-instances \
            --stack-set-name "$STACKSET_NAME" \
            --accounts $ACCOUNTS \
            --regions $REGIONS \
            --no-retain-stacks \
            --region "$REGION"
        
        echo "   Waiting for instances to delete..."
        sleep 30
    fi
    
    # Delete the StackSet
    echo "   Deleting StackSet..."
    aws cloudformation delete-stack-set \
        --stack-set-name "$STACKSET_NAME" \
        --region "$REGION" || echo "   StackSet already deleted or doesn't exist"
    
    echo "✅ StackSet deleted"
else
    echo "   StackSet not found (already deleted)"
fi

echo ""

# Step 2: Delete Account Creation Role stack
echo "📦 Step 2: Deleting Account Creation Role..."
aws cloudformation delete-stack \
    --stack-name AccountPoolFactory-AccountCreationRole \
    --region "$REGION" || echo "   Stack not found"

aws cloudformation wait stack-delete-complete \
    --stack-name AccountPoolFactory-AccountCreationRole \
    --region "$REGION" 2>/dev/null || echo "   Stack already deleted"

echo "✅ Account Creation Role deleted"
echo ""

# Step 3: Delete StackSet Roles stack
echo "📦 Step 3: Deleting StackSet Roles..."
aws cloudformation delete-stack \
    --stack-name AccountPoolFactory-StackSetRoles \
    --region "$REGION" || echo "   Stack not found"

aws cloudformation wait stack-delete-complete \
    --stack-name AccountPoolFactory-StackSetRoles \
    --region "$REGION" 2>/dev/null || echo "   Stack already deleted"

echo "✅ StackSet Roles deleted"
echo ""

# Step 4: Clean up any remaining resources
echo "📦 Step 4: Checking for remaining resources..."

# Check for any remaining CloudFormation stacks
REMAINING_STACKS=$(aws cloudformation list-stacks \
    --region "$REGION" \
    --query 'StackSummaries[?contains(StackName, `AccountPoolFactory`) && StackStatus != `DELETE_COMPLETE`].StackName' \
    --output text)

if [ -n "$REMAINING_STACKS" ]; then
    echo "⚠️  Found remaining stacks:"
    echo "$REMAINING_STACKS"
    echo ""
    echo "Please delete these manually if needed"
else
    echo "✅ No remaining stacks found"
fi

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "Next steps:"
echo "1. Switch to Domain account and run cleanup:"
echo "   ./scripts/cleanup/02-domain-account/cleanup-domain-account.sh"
echo "2. Verify all resources are deleted in AWS Console"

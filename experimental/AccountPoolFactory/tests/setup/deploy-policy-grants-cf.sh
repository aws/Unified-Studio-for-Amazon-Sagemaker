#!/bin/bash
set -e

# Deploy Policy Grants (one-time per domain)
# Creates CREATE_ENVIRONMENT_FROM_BLUEPRINT grants for all enabled blueprints
# Run this ONCE after blueprint enablement, not per account

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Load configuration
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

REGION=$(grep "region:" config.yaml | awk '{print $2}')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')
DOMAIN_ID=$(grep "domain_id:" config.yaml | awk '{print $2}')
ROOT_DOMAIN_UNIT_ID=$(grep "root_domain_unit_id:" config.yaml | awk '{print $2}')

echo "🔐 Deploying Policy Grants (one-time per domain)"
echo "================================================="
echo "Region: $REGION"
echo "Domain Account: $DOMAIN_ACCOUNT_ID"
echo "Domain ID: $DOMAIN_ID"
echo "Root Domain Unit ID: $ROOT_DOMAIN_UNIT_ID"
echo ""

# Require account ID and blueprint IDs as arguments
if [ -z "$1" ]; then
    echo "Usage: $0 <project-account-id> [blueprint-id-1,blueprint-id-2,...]"
    echo ""
    echo "If blueprint IDs are not provided, they will be read from the"
    echo "DataZone-Blueprints-<account-id> stack outputs in the project account."
    exit 1
fi

PROJECT_ACCOUNT_ID="$1"

if [ -n "$2" ]; then
    BLUEPRINT_IDS="$2"
else
    echo "📋 Fetching blueprint IDs from stack outputs..."
    STACK_NAME="DataZone-Blueprints-${PROJECT_ACCOUNT_ID}"
    
    # Get blueprint IDs from the blueprint stack outputs in the project account
    BLUEPRINT_IDS=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?ends_with(OutputKey, `BlueprintId`)].OutputValue' \
        --output text | tr '\t' ',')
    
    if [ -z "$BLUEPRINT_IDS" ]; then
        echo "❌ Could not fetch blueprint IDs from stack $STACK_NAME"
        exit 1
    fi
    echo "   Found: $BLUEPRINT_IDS"
fi

echo ""
echo "📦 Deploying policy grants stack..."
aws cloudformation deploy \
    --template-file tests/setup/templates/policy-grants.yaml \
    --stack-name "AccountPoolFactory-PolicyGrants-${PROJECT_ACCOUNT_ID}" \
    --parameter-overrides \
        DomainId="$DOMAIN_ID" \
        DomainUnitId="$ROOT_DOMAIN_UNIT_ID" \
        ProjectAccountId="$PROJECT_ACCOUNT_ID" \
        BlueprintIds="$BLUEPRINT_IDS" \
    --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
    --region "$REGION"

echo ""
echo "✅ Policy grants deployed for account $PROJECT_ACCOUNT_ID"

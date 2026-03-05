#!/bin/bash
set -e

# Deploy Lambda Functions (PoolManager, SetupOrchestrator, DeprovisionAccount)
# Updates Lambda function code for functions created by infrastructure stack

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

# Load configuration
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

REGION=$(grep "region:" config.yaml | awk '{print $2}')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')

echo "🚀 Deploying Lambda Functions"
echo "=============================="
echo "Region: $REGION"
echo "Domain Account: $DOMAIN_ACCOUNT_ID"
echo ""

# Verify we're in the correct account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "$DOMAIN_ACCOUNT_ID" ]; then
    echo "❌ Error: This script must be run in the Domain account ($DOMAIN_ACCOUNT_ID)"
    echo "   Current account: $CURRENT_ACCOUNT"
    exit 1
fi

echo "✅ Running in correct account"
echo ""

# Deploy PoolManager Lambda code
echo "📦 Deploying PoolManager Lambda code..."
cd src/pool-manager
zip -q ../../pool-manager.zip lambda_function.py
cd ../..

aws lambda update-function-code \
    --function-name PoolManager \
    --zip-file fileb://pool-manager.zip \
    --region "$REGION" \
    > /dev/null

rm -f pool-manager.zip
echo "✅ PoolManager code deployed"
echo ""

# Deploy SetupOrchestrator Lambda code
echo "📦 Deploying SetupOrchestrator Lambda code..."
cd src/setup-orchestrator
zip -q ../../setup-orchestrator.zip lambda_function.py
cd ../..

aws lambda update-function-code \
    --function-name SetupOrchestrator \
    --zip-file fileb://setup-orchestrator.zip \
    --region "$REGION" \
    > /dev/null

rm -f setup-orchestrator.zip
echo "✅ SetupOrchestrator code deployed"
echo ""

# Deploy DeprovisionAccount Lambda code
echo "📦 Deploying DeprovisionAccount Lambda code..."
cd src/deprovision-account
zip -q ../../deprovision-account.zip lambda_function.py
cd ../..

aws lambda update-function-code \
    --function-name DeprovisionAccount \
    --zip-file fileb://deprovision-account.zip \
    --region "$REGION" \
    > /dev/null

rm -f deprovision-account.zip
echo "✅ DeprovisionAccount code deployed"
echo ""

echo "✅ All Lambda functions deployed successfully!"
echo ""
echo "📋 Functions updated:"
echo "  - PoolManager"
echo "  - SetupOrchestrator"
echo "  - DeprovisionAccount"
echo ""

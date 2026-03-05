#!/bin/bash
set -e

# Seed Initial Account Pool
# This script triggers the Pool Manager to create the initial set of accounts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Load configuration
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

REGION=$(grep "region:" config.yaml | awk '{print $2}')

echo "🌱 Seeding initial account pool"
echo "================================"
echo "Region: $REGION"
echo ""

# Invoke Pool Manager with force replenishment
echo "🚀 Triggering pool replenishment..."
aws lambda invoke \
    --function-name PoolManager \
    --payload '{"action":"force_replenishment"}' \
    --cli-binary-format raw-in-base64-out \
    --region "$REGION" \
    response.json

echo ""
echo "📄 Response:"
cat response.json
echo ""

rm -f response.json

echo ""
echo "✅ Pool replenishment triggered"
echo ""
echo "Monitor progress:"
echo "  aws logs tail /aws/lambda/PoolManager --follow --region $REGION"
echo ""
echo "Check pool status:"
echo "  aws dynamodb query --table-name AccountPoolFactory-AccountState --index-name StateIndex --key-condition-expression '#state = :state' --expression-attribute-names '{\"#state\":\"state\"}' --expression-attribute-values '{\":state\":{\"S\":\"AVAILABLE\"}}' --select COUNT --region $REGION"

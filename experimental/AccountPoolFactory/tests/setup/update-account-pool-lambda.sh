#!/bin/bash
set -e

# Update Account Pool with real Lambda ARNs

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load files
POOL_FILE="$PROJECT_ROOT/account-pool-details.json"
LAMBDA_FILE="$PROJECT_ROOT/account-provider-lambda-details.json"
CONFIG_FILE="$PROJECT_ROOT/config.yaml"

if [ ! -f "$POOL_FILE" ]; then
    echo "Error: Account pool details not found: $POOL_FILE"
    exit 1
fi

if [ ! -f "$LAMBDA_FILE" ]; then
    echo "Error: Lambda details not found: $LAMBDA_FILE"
    exit 1
fi

# Parse configuration
DOMAIN_ID=$(jq -r '.domainId' "$POOL_FILE")
POOL_ID=$(jq -r '.id' "$POOL_FILE")
LAMBDA_ARN=$(jq -r '.functionArn' "$LAMBDA_FILE")
ROLE_ARN=$(jq -r '.roleArn' "$LAMBDA_FILE")
REGION=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['aws']['region'])")

echo "=== Updating Account Pool with Lambda ARNs ==="
echo "Domain ID: $DOMAIN_ID"
echo "Pool ID: $POOL_ID"
echo "Lambda ARN: $LAMBDA_ARN"
echo "Role ARN: $ROLE_ARN"
echo "Region: $REGION"
echo ""

# Update account pool
aws datazone update-account-pool \
    --domain-identifier "$DOMAIN_ID" \
    --identifier "$POOL_ID" \
    --account-source customAccountPoolHandler="{lambdaFunctionArn=$LAMBDA_ARN,lambdaExecutionRoleArn=$ROLE_ARN}" \
    --region "$REGION" \
    --output json > /dev/null

echo "✅ Account pool updated successfully!"
echo ""

# Verify update
echo "Verifying account pool configuration..."
aws datazone get-account-pool \
    --domain-identifier "$DOMAIN_ID" \
    --identifier "$POOL_ID" \
    --region "$REGION" \
    --output json | jq '{id, name, accountSource}'

echo ""
echo "=== Next Steps ==="
echo "1. Create a DataZone project using the profile"
echo "2. Verify account assignment from pool"

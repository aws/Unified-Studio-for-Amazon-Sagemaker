#!/bin/bash
set -e

# Update account pool resolution strategy to trigger Lambda automatically

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load configuration
CONFIG_FILE="$PROJECT_ROOT/config.yaml"
POOL_FILE="$PROJECT_ROOT/account-pool-details.json"

if [ ! -f "$POOL_FILE" ]; then
    echo "Error: Account pool details not found: $POOL_FILE"
    exit 1
fi

# Parse configuration
read -r DOMAIN_ID REGION < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['region'])
EOF
)

POOL_ID=$(jq -r '.id' "$POOL_FILE")
POOL_NAME=$(jq -r '.name' "$POOL_FILE")

echo "=== Current Account Pool Configuration ==="
echo "Pool ID: $POOL_ID"
echo "Pool Name: $POOL_NAME"
echo ""

# Get current configuration
CURRENT_POOL=$(aws datazone get-account-pool \
    --domain-identifier "$DOMAIN_ID" \
    --identifier "$POOL_ID" \
    --region "$REGION" \
    --output json)

echo "Current resolution strategy:"
echo "$CURRENT_POOL" | jq '{resolutionStrategy, accountSource}'
echo ""

echo "=== Updating Resolution Strategy ==="
echo "Changing from MANUAL to AUTOMATIC"
echo ""
echo "With AUTOMATIC strategy:"
echo "- Lambda is called automatically when environment is created"
echo "- User doesn't need to manually select account"
echo "- Lambda decides which account to use"
echo ""

# Update account pool with AUTOMATIC resolution strategy
UPDATE_RESULT=$(aws datazone update-account-pool \
    --domain-identifier "$DOMAIN_ID" \
    --identifier "$POOL_ID" \
    --resolution-strategy "AUTOMATIC" \
    --region "$REGION" \
    --output json 2>&1)

if echo "$UPDATE_RESULT" | grep -q "error"; then
    echo "❌ Failed to update account pool:"
    echo "$UPDATE_RESULT"
    exit 1
else
    echo "✅ Account pool updated successfully!"
    echo ""
    echo "New configuration:"
    echo "$UPDATE_RESULT" | jq '{
        id,
        name,
        resolutionStrategy,
        accountSource,
        lastUpdatedAt
    }'
    
    # Update saved file
    echo "$UPDATE_RESULT" > "$POOL_FILE"
    echo ""
    echo "Updated details saved to: $POOL_FILE"
fi

echo ""
echo "=== Next Steps ==="
echo "1. Try creating an environment again through the portal"
echo "2. The Lambda should now be invoked automatically"
echo "3. Check Lambda logs to verify invocation"

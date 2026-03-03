#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load configuration
CONFIG_FILE="$PROJECT_ROOT/config.yaml"
POOL_FILE="$PROJECT_ROOT/account-pool-details.json"

# Parse configuration
read -r DOMAIN_ID REGION < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['region'])
EOF
)

POOL_ID=$(jq -r '.id' "$POOL_FILE")

echo "=== Testing ListAccountsInAccountPool API ==="
echo "Domain ID: $DOMAIN_ID"
echo "Pool ID: $POOL_ID"
echo "Region: $REGION"
echo ""

echo "Calling API..."
aws datazone list-accounts-in-account-pool \
  --domain-identifier "$DOMAIN_ID" \
  --identifier "$POOL_ID" \
  --region "$REGION" \
  --debug 2>&1 | tee /tmp/list-accounts-debug.log

echo ""
echo "Debug log saved to: /tmp/list-accounts-debug.log"

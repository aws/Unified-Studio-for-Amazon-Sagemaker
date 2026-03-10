#!/bin/bash
set -e

# Seed the account pool by triggering PoolManager replenishment.
# Run AFTER all deploy steps are complete.
#
# Usage:
#   eval $(isengardcli credentials amirbo+3@amazon.com)
#   ./scripts/02-domain-account/deploy/04-seed-pool.sh [pool-name]
#
# If pool-name is omitted, seeds all pools.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

source scripts/utils/resolve-config.sh domain

POOL_NAME="${1:-}"

echo "🌱 Seeding Account Pool"
echo "======================="
echo "Region:  $REGION"
if [ -n "$POOL_NAME" ]; then
    echo "Pool:    $POOL_NAME"
    PAYLOAD="{\"action\":\"force_replenishment\",\"poolName\":\"$POOL_NAME\"}"
else
    echo "Pools:   all ($POOL_NAMES)"
    PAYLOAD='{"action":"force_replenishment"}'
fi
echo ""

aws lambda invoke \
    --function-name PoolManager \
    --payload "$PAYLOAD" \
    --cli-binary-format raw-in-base64-out \
    --region "$REGION" \
    /tmp/seed-pool-response.json > /dev/null

echo "✅ Replenishment triggered"
echo ""
cat /tmp/seed-pool-response.json
echo ""
echo "Each account takes ~6-8 minutes. Monitor progress:"
echo "  python3 scripts/utils/monitor-pool.py 30"

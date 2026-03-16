#!/bin/bash
set -e

# Invoke AccountReconciler Lambda
#
# Usage:
#   ./invoke-reconciler.sh [--dry-run] [--auto-recycle] [--auto-replenish] [--account ACCOUNT_ID]
#
# Options:
#   --dry-run          Preview changes without modifying DynamoDB
#   --auto-recycle     Trigger AccountRecycler for recyclable accounts
#   --auto-replenish   Trigger PoolManager to replenish if pool is low
#   --account ID       Run reconciler on a single account only

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

source "$SCRIPT_DIR/../resolve-config.sh"

# Parse arguments
DRY_RUN=false
AUTO_RECYCLE=false
AUTO_REPLENISH=false
ACCOUNT_ID=""
SKIP_NEXT=false
for arg in "$@"; do
    if [ "$SKIP_NEXT" = true ]; then
        ACCOUNT_ID="$arg"
        SKIP_NEXT=false
        continue
    fi
    case $arg in
        --dry-run) DRY_RUN=true ;;
        --auto-recycle) AUTO_RECYCLE=true ;;
        --auto-replenish) AUTO_REPLENISH=true ;;
        --account) SKIP_NEXT=true ;;
    esac
done

# Verify account
if [ "$CURRENT_ACCOUNT" != "$DOMAIN_ACCOUNT_ID" ]; then
    echo "❌ Must run in Domain account ($DOMAIN_ACCOUNT_ID), currently in $CURRENT_ACCOUNT"
    exit 1
fi

echo "🔄 Invoking AccountReconciler"
echo "  dryRun:         $DRY_RUN"
echo "  autoRecycle:    $AUTO_RECYCLE"
echo "  autoReplenish:  $AUTO_REPLENISH"
if [ -n "$ACCOUNT_ID" ]; then
    echo "  accountFilter:  $ACCOUNT_ID"
fi
echo ""

# Build JSON payload — pass bash booleans as env vars to python
PAYLOAD=$(DRY_RUN=$DRY_RUN AUTO_RECYCLE=$AUTO_RECYCLE AUTO_REPLENISH=$AUTO_REPLENISH ACCOUNT_ID=$ACCOUNT_ID python3 -c "
import json, os
payload = {
    'source': 'manual',
    'dryRun': os.environ['DRY_RUN'] == 'true',
    'autoRecycle': os.environ['AUTO_RECYCLE'] == 'true',
    'autoReplenish': os.environ['AUTO_REPLENISH'] == 'true'
}
acct = os.environ.get('ACCOUNT_ID', '')
if acct:
    payload['accountIds'] = [acct]
print(json.dumps(payload))
")

echo "Payload: $PAYLOAD"
echo ""

aws lambda invoke \
    --function-name AccountReconciler \
    --payload "$PAYLOAD" \
    --cli-binary-format raw-in-base64-out \
    --region "$REGION" \
    --output json \
    /tmp/reconciler-output.json > /dev/null

echo "📋 Result:"
python3 -c "
import json
with open('/tmp/reconciler-output.json') as f:
    data = json.load(f)
summary = data.get('summary', {})
print(f\"  Status:            {data.get('status')}\")
print(f\"  Dry Run:           {data.get('dryRun')}\")
print(f\"  Org Accounts:      {summary.get('totalOrgAccounts', 0)}\")
print(f\"  Pool Accounts:     {summary.get('totalPoolAccounts', 0)}\")
print(f\"  Orphaned Created:  {summary.get('orphanedCreated', 0)}\")
print(f\"  Unchanged:         {summary.get('unchanged', 0)}\")
print(f\"  Stale Updated:     {summary.get('staleUpdated', 0)}\")
print(f\"  Failed Validation: {summary.get('failedValidation', 0)}\")
print(f\"  Recycling:         {data.get('recyclingTriggered', False)}\")
print(f\"  Replenishment:     {data.get('replenishmentTriggered', False)}\")
"
echo ""
echo "Full output: /tmp/reconciler-output.json"

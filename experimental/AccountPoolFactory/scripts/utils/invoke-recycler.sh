#!/bin/bash
set -e

# Invoke AccountRecycler Lambda
#
# Usage:
#   ./invoke-recycler.sh [--all] [--account <id>] [--accounts <id1,id2,...>] [--force] [--async] [--update-blueprints]
#
# Options:
#   --all                Recycle all recyclable accounts (ORPHANED, FAILED, CLEANING)
#   --account <id>       Recycle a single account
#   --accounts <ids>     Recycle specific accounts (comma-separated)
#   --force              Force recycle even if AVAILABLE (for incomplete setups)
#   --async              Fire-and-forget (Event invocation, no wait for result)
#   --update-blueprints  Update blueprint stacks on all AVAILABLE accounts (rolling, self-triggering)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

REGION=$(grep "region:" config.yaml | awk '{print $2}')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')

# Parse arguments
RECYCLE_ALL=false
SINGLE_ACCOUNT=""
ACCOUNT_LIST=""
FORCE=false
ASYNC=false
UPDATE_BLUEPRINTS=false
while [ $# -gt 0 ]; do
    case "$1" in
        --all) RECYCLE_ALL=true; shift ;;
        --account) SINGLE_ACCOUNT="$2"; shift 2 ;;
        --accounts) ACCOUNT_LIST="$2"; shift 2 ;;
        --force) FORCE=true; shift ;;
        --async) ASYNC=true; shift ;;
        --update-blueprints) UPDATE_BLUEPRINTS=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Verify account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "$DOMAIN_ACCOUNT_ID" ]; then
    echo "❌ Must run in Domain account ($DOMAIN_ACCOUNT_ID), currently in $CURRENT_ACCOUNT"
    exit 1
fi

# Build payload
if [ "$UPDATE_BLUEPRINTS" = true ]; then
    PAYLOAD='{"updateBlueprints": true}'
    echo "🔄 Updating blueprints on all AVAILABLE accounts (rolling, self-triggering)"
elif [ -n "$SINGLE_ACCOUNT" ]; then
    if [ "$FORCE" = true ]; then
        PAYLOAD="{\"accountId\": \"$SINGLE_ACCOUNT\", \"force\": true}"
    else
        PAYLOAD="{\"accountId\": \"$SINGLE_ACCOUNT\"}"
    fi
    echo "🔄 Recycling single account: $SINGLE_ACCOUNT (force=$FORCE)"
elif [ -n "$ACCOUNT_LIST" ]; then
    PAYLOAD=$(python3 -c "
import json
ids = '$ACCOUNT_LIST'.split(',')
payload = {'accountIds': ids}
if '$FORCE' == 'true':
    payload['force'] = True
print(json.dumps(payload))
")
    echo "🔄 Recycling accounts: $ACCOUNT_LIST (force=$FORCE)"
elif [ "$RECYCLE_ALL" = true ]; then
    if [ "$FORCE" = true ]; then
        PAYLOAD='{"recycleAll": true, "force": true}'
    else
        PAYLOAD='{"recycleAll": true}'
    fi
    echo "🔄 Recycling ALL recyclable accounts (force=$FORCE)"
else
    echo "Usage: $0 [--all] [--account <id>] [--accounts <id1,id2,...>]"
    exit 1
fi

echo "  Payload: $PAYLOAD"
echo ""

INVOCATION_TYPE="RequestResponse"
if [ "$ASYNC" = true ]; then
    INVOCATION_TYPE="Event"
    echo "🚀 Firing async (Event) — Lambda runs in background, no result returned"
    echo ""
fi

if [ "$INVOCATION_TYPE" = "Event" ]; then
    aws lambda invoke \
        --function-name AccountRecycler \
        --invocation-type Event \
        --payload "$PAYLOAD" \
        --cli-binary-format raw-in-base64-out \
        --region "$REGION" \
        --output json \
        /dev/null > /dev/null
    echo "✅ Recycler triggered async. Monitor progress:"
    echo "   aws logs tail /aws/lambda/AccountRecycler --follow --region $REGION"
    exit 0
fi

aws lambda invoke \
    --function-name AccountRecycler \
    --payload "$PAYLOAD" \
    --cli-binary-format raw-in-base64-out \
    --region "$REGION" \
    --output json \
    /tmp/recycler-output.json > /dev/null

echo "📋 Result:"
python3 -c "
import json
with open('/tmp/recycler-output.json') as f:
    data = json.load(f)
summary = data.get('summary', {})
print(f\"  Status:     {data.get('status')}\")
print(f\"  Processed:  {summary.get('totalProcessed', 0)}\")
print(f\"  Succeeded:  {summary.get('succeeded', 0)}\")
print(f\"  Failed:     {summary.get('failed', 0)}\")
print(f\"  Skipped:    {summary.get('skipped', 0)}\")
results = data.get('results', [])
if results:
    print()
    for r in results[:20]:
        status = '✅' if r['result'] == 'RECYCLED' else '❌' if r['result'] == 'FAILED' else '⏭️'
        line = f\"  {status} {r['accountId']}: {r.get('previousState','?')} → {r['result']}\"
        if r.get('error'):
            line += f\" ({r['error'][:80]})\"
        print(line)
    if len(results) > 20:
        print(f'  ... and {len(results) - 20} more')
"
echo ""
echo "Full output: /tmp/recycler-output.json"

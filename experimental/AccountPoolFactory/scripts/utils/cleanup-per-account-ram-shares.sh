#!/bin/bash
set -e

# Cleanup per-account RAM shares
# Deletes all DataZone-Domain-Share-<accountId> shares now that the org-wide
# OU-level share (DataZone-Domain-Share-OrgWide) covers all pool accounts.
#
# Usage: ./cleanup-per-account-ram-shares.sh [--dry-run]
#
# Pre-requisite: run from domain account (amirbo+3)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

DRY_RUN=false
if [ "${1}" = "--dry-run" ]; then
    DRY_RUN=true
fi

source scripts/utils/resolve-config.sh domain

ORG_SHARE_NAME="DataZone-Domain-Share-OrgWide"

echo "Cleanup per-account RAM shares"
echo "=============================="
echo "Region: $REGION"
echo "Dry run: $DRY_RUN"
echo ""

# Verify org-wide share exists and is healthy before deleting per-account shares
echo "Verifying org-wide share is ACTIVE..."
ORG_SHARE_STATUS=$(aws ram get-resource-shares \
    --resource-owner SELF \
    --name "$ORG_SHARE_NAME" \
    --region "$REGION" \
    --query 'resourceShares[?status==`ACTIVE`].status' \
    --output text 2>/dev/null)

if [ "$ORG_SHARE_STATUS" != "ACTIVE" ]; then
    echo "ERROR: Org-wide share '$ORG_SHARE_NAME' is not ACTIVE. Aborting."
    echo "       Create it first before deleting per-account shares."
    exit 1
fi
echo "  Org-wide share is ACTIVE"
echo ""

# Collect all per-account share ARNs (paginate through all shares)
echo "Scanning for per-account shares..."
SHARES_FILE=$(mktemp)
NEXT_TOKEN=""

while true; do
    if [ -z "$NEXT_TOKEN" ]; then
        RESP=$(aws ram get-resource-shares \
            --resource-owner SELF \
            --max-results 100 \
            --region "$REGION" \
            --output json 2>/dev/null)
    else
        RESP=$(aws ram get-resource-shares \
            --resource-owner SELF \
            --max-results 100 \
            --next-token "$NEXT_TOKEN" \
            --region "$REGION" \
            --output json 2>/dev/null)
    fi

    # Extract per-account shares (name matches DataZone-Domain-Share-<12digits>, status ACTIVE or FAILED)
    echo "$RESP" | python3 -c "
import json, sys, re
data = json.load(sys.stdin)
pattern = re.compile(r'^DataZone-Domain-Share-\d{12}$')
for s in data.get('resourceShares', []):
    if pattern.match(s.get('name','')) and s.get('status') in ('ACTIVE','FAILED','INACTIVE'):
        print(s['resourceShareArn'] + '\t' + s['name'] + '\t' + s['status'])
" >> "$SHARES_FILE"

    NEXT_TOKEN=$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('nextToken',''))" 2>/dev/null)
    if [ -z "$NEXT_TOKEN" ]; then
        break
    fi
done

TOTAL=$(wc -l < "$SHARES_FILE" | tr -d ' ')

if [ "$TOTAL" -eq 0 ]; then
    echo "No per-account shares found. Nothing to do."
    rm -f "$SHARES_FILE"
    exit 0
fi

echo "Found $TOTAL per-account share(s) to delete:"
echo ""
head -10 "$SHARES_FILE" | awk -F'\t' '{print "  " $2 " [" $3 "]"}'
if [ "$TOTAL" -gt 10 ]; then
    echo "  ... and $((TOTAL - 10)) more"
fi
echo ""

if [ "$DRY_RUN" = "true" ]; then
    echo "DRY RUN: would delete $TOTAL shares. Re-run without --dry-run to proceed."
    rm -f "$SHARES_FILE"
    exit 0
fi

read -p "Delete all $TOTAL per-account RAM shares? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    rm -f "$SHARES_FILE"
    exit 1
fi

echo ""
echo "Deleting shares..."
DELETED=0
FAILED=0

while IFS=$'\t' read -r SHARE_ARN SHARE_NAME SHARE_STATUS; do
    if aws ram delete-resource-share \
        --resource-share-arn "$SHARE_ARN" \
        --region "$REGION" \
        --output json > /dev/null 2>&1; then
        echo "  Deleted: $SHARE_NAME"
        DELETED=$((DELETED + 1))
    else
        echo "  FAILED to delete: $SHARE_NAME"
        FAILED=$((FAILED + 1))
    fi
done < "$SHARES_FILE"

rm -f "$SHARES_FILE"

echo ""
echo "=============================="
echo "Done. Deleted: $DELETED  Failed: $FAILED"
if [ "$FAILED" -gt 0 ]; then
    echo "Re-run the script to retry failed deletions."
fi

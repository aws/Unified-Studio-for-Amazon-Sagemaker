#!/bin/bash
# Pre-seed verification — checks both accounts are ready before seeding the pool

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "🔍 Pre-Seed Verification"
echo "========================="
echo ""

ERRORS=0

# ── Org Admin account ────────────────────────────────────────────────────────
eval $(isengardcli credentials amirbo+1@amazon.com) 2>/dev/null || { echo "❌ Cannot switch to Org Admin"; ERRORS=$((ERRORS+1)); }

source scripts/utils/resolve-config.sh org
echo "━━━ Org Admin Account ($CURRENT_ACCOUNT) ━━━"
echo "Region: $REGION"

STATUS=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-OrgAdmin --region "$REGION" \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "NOT_FOUND")
[ "$STATUS" = "CREATE_COMPLETE" ] || [ "$STATUS" = "UPDATE_COMPLETE" ] \
    && echo "✅ AccountPoolFactory-OrgAdmin: $STATUS" \
    || { echo "❌ AccountPoolFactory-OrgAdmin: $STATUS"; ERRORS=$((ERRORS+1)); }

SS=$(aws cloudformation describe-stack-set \
    --stack-set-name SMUS-AccountPoolFactory-DomainAccess --region "$REGION" \
    --query 'StackSet.Status' --output text 2>/dev/null || echo "NOT_FOUND")
[ "$SS" = "ACTIVE" ] \
    && echo "✅ SMUS-AccountPoolFactory-DomainAccess StackSet: ACTIVE" \
    || { echo "❌ SMUS-AccountPoolFactory-DomainAccess StackSet: $SS"; ERRORS=$((ERRORS+1)); }

echo ""

# ── Domain account ───────────────────────────────────────────────────────────
eval $(isengardcli credentials amirbo+3@amazon.com) 2>/dev/null || { echo "❌ Cannot switch to Domain"; ERRORS=$((ERRORS+1)); }

source scripts/utils/resolve-config.sh domain
echo "━━━ Domain Account ($CURRENT_ACCOUNT) ━━━"

STATUS=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-Infrastructure --region "$REGION" \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "NOT_FOUND")
[ "$STATUS" = "CREATE_COMPLETE" ] || [ "$STATUS" = "UPDATE_COMPLETE" ] \
    && echo "✅ AccountPoolFactory-Infrastructure: $STATUS" \
    || { echo "❌ AccountPoolFactory-Infrastructure: $STATUS"; ERRORS=$((ERRORS+1)); }

for FUNC in PoolManager ProvisionAccount SetupOrchestrator AccountProvider; do
    aws lambda get-function --function-name "$FUNC" --region "$REGION" \
        --query 'Configuration.State' --output text &>/dev/null \
        && echo "✅ Lambda $FUNC exists" \
        || { echo "❌ Lambda $FUNC not found"; ERRORS=$((ERRORS+1)); }
done

TABLE=$(aws dynamodb describe-table \
    --table-name AccountPoolFactory-AccountState --region "$REGION" \
    --query 'Table.TableStatus' --output text 2>/dev/null || echo "NOT_FOUND")
[ "$TABLE" = "ACTIVE" ] \
    && echo "✅ DynamoDB table: ACTIVE" \
    || { echo "❌ DynamoDB table: $TABLE"; ERRORS=$((ERRORS+1)); }

echo ""

# ── Summary ──────────────────────────────────────────────────────────────────
if [ $ERRORS -eq 0 ]; then
    echo "✅ All checks passed — ready to seed the pool"
    echo ""
    echo "  eval \$(isengardcli credentials amirbo+3@amazon.com)"
    echo "  aws lambda invoke --function-name PoolManager \\"
    echo "    --payload '{\"action\":\"force_replenishment\"}' \\"
    echo "    --cli-binary-format raw-in-base64-out --region $REGION /tmp/seed.json"
else
    echo "❌ $ERRORS error(s) — fix before seeding"
    echo "  Org Admin: ./scripts/01-org-mgmt-account/deploy/deploy-org-admin.sh"
    echo "  Domain:    ./scripts/02-domain-account/deploy/01-deploy-infrastructure.sh"
    exit 1
fi

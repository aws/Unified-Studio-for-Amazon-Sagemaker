#!/bin/bash
set -e

# =============================================================================
# Full Deployment Script — Account Pool Factory
# =============================================================================
# Deploy order:
#   Phase 2 FIRST: Org Admin account — consolidated governance stack (roles + StackSet)
#   Phase 1 SECOND: Domain account — CF infra + all Lambda code (reads org admin outputs)
#
# Usage:
#   ./scripts/deploy-all.sh [--skip-domain] [--skip-org] [--skip-dynamodb-clear]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

SKIP_ORG=false
SKIP_DOMAIN=false
SKIP_DYNAMODB_CLEAR=false
for arg in "$@"; do
    case $arg in
        --skip-org) SKIP_ORG=true ;;
        --skip-domain) SKIP_DOMAIN=true ;;
        --skip-dynamodb-clear) SKIP_DYNAMODB_CLEAR=true ;;
    esac
done

echo "============================================="
echo " Account Pool Factory — Full Deploy"
echo "============================================="
echo ""

deploy_lambda() {
    local func_name="$1"
    local src_dir="$2"
    local handler_file="$3"

    echo "  🔄 Deploying $func_name..."
    local tmp_dir=$(mktemp -d)
    cp "$src_dir/$handler_file" "$tmp_dir/"
    (cd "$tmp_dir" && zip -qr lambda.zip .)
    aws lambda update-function-code \
        --function-name "$func_name" \
        --zip-file "fileb://$tmp_dir/lambda.zip" \
        --region "$REGION" > /dev/null
    aws lambda wait function-updated \
        --function-name "$func_name" \
        --region "$REGION"
    rm -rf "$tmp_dir"
    echo "  ✅ $func_name deployed"
}

# =============================================================================
# PHASE 1: Domain Account
# =============================================================================
if [ "$SKIP_DOMAIN" = false ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo " PHASE 1: Domain Account"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "⚠️  Switch to Domain account:"
    echo "   eval \$(isengardcli credentials amirbo+3@amazon.com)"
    echo ""
    read -p "Press Enter when ready (or Ctrl+C to abort)..."

    CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
    echo "✅ Confirmed: Domain account"
    echo ""

    # Resolve all config from domain-config.yaml
    source scripts/utils/resolve-config.sh domain

    echo "Region: $REGION  |  Domain: $DOMAIN_ID  |  Org Admin: $ORG_ADMIN_ACCOUNT_ID"
    echo ""

    # Step 1.1: Infrastructure CF stack
    echo "📦 Step 1.1: Deploying Infrastructure stack..."

    if [ -z "$ACCOUNT_CREATION_ROLE_ARN" ]; then
        echo "❌ AccountCreation role not found — deploy Org Admin stack first (Phase 2)"
        exit 1
    fi

    aws cloudformation deploy \
        --template-file templates/cloudformation/02-domain-account/deploy/01-infrastructure.yaml \
        --stack-name AccountPoolFactory-Infrastructure \
        --parameter-overrides \
            DomainId="$DOMAIN_ID" \
            DomainAccountId="$DOMAIN_ACCOUNT_ID" \
            RootDomainUnitId="$ROOT_DOMAIN_UNIT_ID" \
            OrgAdminAccountId="$ORG_ADMIN_ACCOUNT_ID" \
            AccountCreationRoleArn="$ACCOUNT_CREATION_ROLE_ARN" \
            ExternalId="$EXTERNAL_ID" \
            OrganizationId="$ORG_ID" \
            TargetOUId="$TARGET_OU_ID" \
            EmailPrefix="$EMAIL_PREFIX" \
            EmailDomain="$EMAIL_DOMAIN" \
            ProjectRoleEnabled="$PROJECT_ROLE_ENABLED" \
            ProjectRoleName="$PROJECT_ROLE_NAME" \
            ProjectRoleManagedPolicyArn="$PROJECT_ROLE_POLICY" \
            ExpectedStackPatterns="$EXPECTED_STACK_PATTERNS" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION" \
        --no-fail-on-empty-changeset
    echo "✅ Infrastructure stack deployed"
    echo ""

    # Step 1.2: Deploy all Lambda code
    echo "📦 Step 1.2: Deploying Lambda functions..."

    deploy_lambda "PoolManager" "src/pool-manager" "lambda_function.py"

    # SetupOrchestrator includes CF templates
    echo "  🔄 Deploying SetupOrchestrator..."
    TMP_SO=$(mktemp -d)
    cp src/setup-orchestrator/lambda_function.py "$TMP_SO/"
    cp templates/cloudformation/03-project-account/deploy/*.yaml "$TMP_SO/" 2>/dev/null || true
    (cd "$TMP_SO" && zip -qr lambda.zip .)
    aws lambda update-function-code \
        --function-name SetupOrchestrator \
        --zip-file "fileb://$TMP_SO/lambda.zip" \
        --region "$REGION" > /dev/null
    aws lambda wait function-updated \
        --function-name SetupOrchestrator \
        --region "$REGION"
    rm -rf "$TMP_SO"
    echo "  ✅ SetupOrchestrator deployed"

    deploy_lambda "ProvisionAccount" "src/provision-account" "lambda_function.py"
    deploy_lambda "DeprovisionAccount" "src/deprovision-account" "lambda_function.py"
    deploy_lambda "AccountProvider" "src/account-provider" "lambda_function_prod.py"
    deploy_lambda "AccountReconciler" "src/account-reconciler" "lambda_function.py"
    deploy_lambda "AccountRecycler" "src/account-recycler" "lambda_function.py"

    echo ""
    echo "✅ All Lambda functions deployed"
    echo ""

    # Step 1.3: Clear DynamoDB (optional)
    if [ "$SKIP_DYNAMODB_CLEAR" = false ]; then
        echo "📦 Step 1.3: Clearing DynamoDB table..."
        TABLE_NAME="AccountPoolFactory-AccountState"
        ITEMS=$(aws dynamodb scan --table-name "$TABLE_NAME" --region "$REGION" \
            --projection-expression "accountId,#ts" \
            --expression-attribute-names '{"#ts":"timestamp"}' \
            --output json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
for item in data.get('Items', []):
    aid = item['accountId']['S']
    ts = item['timestamp']['N']
    print(f'{aid}|{ts}')
" 2>/dev/null) || true

        if [ -n "$ITEMS" ]; then
            echo "$ITEMS" | while IFS='|' read -r aid ts; do
                aws dynamodb delete-item \
                    --table-name "$TABLE_NAME" \
                    --key "{\"accountId\":{\"S\":\"$aid\"},\"timestamp\":{\"N\":\"$ts\"}}" \
                    --region "$REGION" 2>/dev/null
            done
            echo "  ✅ DynamoDB table cleared"
        else
            echo "  ℹ️  DynamoDB table already empty"
        fi
        echo ""
    fi

    echo "✅ PHASE 1 COMPLETE"
    echo ""
fi

# =============================================================================
# PHASE 2: Org Admin Account
# =============================================================================
if [ "$SKIP_ORG" = false ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo " PHASE 2: Org Admin Account"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "⚠️  Switch to Org Admin account:"
    echo "   eval \$(isengardcli credentials amirbo+1@amazon.com)"
    echo ""
    read -p "Press Enter when ready (or Ctrl+C to abort)..."

    # Resolve org config
    source scripts/utils/resolve-config.sh org

    echo "Org Admin: $CURRENT_ACCOUNT  |  Region: $REGION"
    echo ""

    # deploy-org-admin.sh needs domain account ID and domain ID as args
    # Read domain account ID from domain-config.yaml or resolve
    DOMAIN_ACCOUNT_ID_FOR_ORG=$(python3 -c "
import yaml, boto3
cfg_file = 'domain-config.yaml'
try:
    c = yaml.safe_load(open(cfg_file))
    print(c.get('domain_account_id', ''))
except: print('')
" 2>/dev/null || echo "")

    DOMAIN_ID_FOR_ORG=$(python3 -c "
import yaml
cfg_file = 'domain-config.yaml'
try:
    c = yaml.safe_load(open(cfg_file))
    print(c.get('domain_id', ''))
except: print('')
" 2>/dev/null || echo "")

    echo "📦 Deploying consolidated Org Admin governance stack..."
    ./scripts/01-org-mgmt-account/deploy/deploy-org-admin.sh "$DOMAIN_ACCOUNT_ID_FOR_ORG" "$DOMAIN_ID_FOR_ORG"

    echo "✅ PHASE 2 COMPLETE"
    echo ""
fi

echo "============================================="
echo " ✅ Full deployment complete!"
echo "============================================="
echo ""
echo "Next steps:"
echo "  1. Deploy project profile: ./scripts/02-domain-account/deploy/02-deploy-project-profile.sh"
echo "  2. Seed pool accounts: invoke PoolManager with replenish action"

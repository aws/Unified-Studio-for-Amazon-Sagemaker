#!/bin/bash
set -e

# =============================================================================
# Full Deployment Script — Account Pool Factory
# =============================================================================
# Deploy order:
#   Phase 1: Domain account — CF infra + all Lambda code + DynamoDB clear
#   Phase 2: Org Admin account — CF stacks + Lambda code + StackSet
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

if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

REGION=$(grep "region:" config.yaml | awk '{print $2}')
ORG_ADMIN_ACCOUNT_ID=$(grep "account_id:" config.yaml | head -1 | awk '{print $2}' | tr -d '"')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')
DOMAIN_ID=$(grep "domain_id:" config.yaml | awk '{print $2}')
ROOT_DOMAIN_UNIT_ID=$(grep "root_domain_unit_id:" config.yaml | awk '{print $2}')
EMAIL_PREFIX=$(grep "email_prefix:" config.yaml | awk '{print $2}')
EMAIL_DOMAIN=$(grep "email_domain:" config.yaml | awk '{print $2}')
TARGET_OU_ID=$(grep "target_ou_id:" config.yaml | awk '{print $2}')
PROJECT_ROLE_ENABLED=$(python3 -c "import yaml; c=yaml.safe_load(open('config.yaml')); print(str(c.get('project_role',{}).get('enabled', True)).lower())" 2>/dev/null || echo "true")
PROJECT_ROLE_NAME=$(python3 -c "import yaml; c=yaml.safe_load(open('config.yaml')); print(c.get('project_role',{}).get('role_name', 'AmazonSageMakerProjectRole'))" 2>/dev/null || echo "AmazonSageMakerProjectRole")
PROJECT_ROLE_POLICY=$(python3 -c "import yaml; c=yaml.safe_load(open('config.yaml')); print(c.get('project_role',{}).get('managed_policy_arn', 'arn:aws:iam::aws:policy/AmazonSageMakerFullAccess'))" 2>/dev/null || echo "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess")

echo "============================================="
echo " Account Pool Factory — Full Deploy"
echo "============================================="
echo "Region:            $REGION"
echo "Org Admin Account: $ORG_ADMIN_ACCOUNT_ID"
echo "Domain Account:    $DOMAIN_ACCOUNT_ID"
echo "Domain ID:         $DOMAIN_ID"
echo "Root Domain Unit:  $ROOT_DOMAIN_UNIT_ID"
echo "Target OU:         $TARGET_OU_ID"
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
    echo " PHASE 1: Domain Account ($DOMAIN_ACCOUNT_ID)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "⚠️  Switch to Domain account:"
    echo "   eval \$(isengardcli credentials amirbo+3@amazon.com)"
    echo ""
    read -p "Press Enter when ready (or Ctrl+C to abort)..."

    CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
    if [ "$CURRENT_ACCOUNT" != "$DOMAIN_ACCOUNT_ID" ]; then
        echo "❌ Wrong account: $CURRENT_ACCOUNT (expected $DOMAIN_ACCOUNT_ID)"
        exit 1
    fi
    echo "✅ Confirmed: Domain account"
    echo ""

    # Step 1.1: Infrastructure CF stack
    echo "📦 Step 1.1: Deploying Infrastructure stack..."
    aws cloudformation deploy \
        --template-file templates/cloudformation/02-domain-account/deploy/01-infrastructure.yaml \
        --stack-name AccountPoolFactory-Infrastructure \
        --parameter-overrides \
            DomainId="$DOMAIN_ID" \
            DomainAccountId="$DOMAIN_ACCOUNT_ID" \
            RootDomainUnitId="$ROOT_DOMAIN_UNIT_ID" \
            OrgAdminAccountId="$ORG_ADMIN_ACCOUNT_ID" \
            ProvisionAccountFunctionArn="arn:aws:lambda:${REGION}:${ORG_ADMIN_ACCOUNT_ID}:function:ProvisionAccount" \
            TargetOUId="$TARGET_OU_ID" \
            EmailPrefix="$EMAIL_PREFIX" \
            EmailDomain="$EMAIL_DOMAIN" \
            ProjectRoleEnabled="$PROJECT_ROLE_ENABLED" \
            ProjectRoleName="$PROJECT_ROLE_NAME" \
            ProjectRoleManagedPolicyArn="$PROJECT_ROLE_POLICY" \
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
    echo " PHASE 2: Org Admin Account ($ORG_ADMIN_ACCOUNT_ID)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "⚠️  Switch to Org Admin account:"
    echo "   eval \$(isengardcli credentials amirbo+1@amazon.com)"
    echo ""
    read -p "Press Enter when ready (or Ctrl+C to abort)..."

    CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
    if [ "$CURRENT_ACCOUNT" != "$ORG_ADMIN_ACCOUNT_ID" ]; then
        echo "❌ Wrong account: $CURRENT_ACCOUNT (expected $ORG_ADMIN_ACCOUNT_ID)"
        exit 1
    fi
    echo "✅ Confirmed: Org Admin account"
    echo ""

    # Step 2.1: StackSet Roles
    echo "📦 Step 2.1: Deploying StackSet roles..."
    aws cloudformation deploy \
        --template-file templates/cloudformation/01-org-mgmt-account/deploy/01-stackset-roles.yaml \
        --stack-name AccountPoolFactory-StackSetRoles \
        --parameter-overrides DomainAccountId="$DOMAIN_ACCOUNT_ID" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION" \
        --no-fail-on-empty-changeset
    echo "✅ StackSet roles deployed"
    echo ""

    # Step 2.2: ProvisionAccount CF stack
    echo "📦 Step 2.2: Deploying ProvisionAccount stack..."
    aws cloudformation deploy \
        --template-file templates/cloudformation/01-org-mgmt-account/deploy/02-provision-account.yaml \
        --stack-name AccountPoolFactory-ProvisionAccount \
        --parameter-overrides DomainAccountId="$DOMAIN_ACCOUNT_ID" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION" \
        --no-fail-on-empty-changeset
    echo "✅ ProvisionAccount stack deployed"
    echo ""

    # Step 2.3: ProvisionAccount Lambda code
    echo "📦 Step 2.3: Deploying ProvisionAccount Lambda code..."
    deploy_lambda "ProvisionAccount" "src/provision-account" "lambda_function.py"
    echo ""

    # Step 2.4: DomainAccess StackSet
    echo "📦 Step 2.4: Creating/updating DomainAccess StackSet..."
    STACKSET_NAME="SMUS-AccountPoolFactory-DomainAccess"
    STACKSET_TEMPLATE="templates/cloudformation/01-org-mgmt-account/deploy/03-domain-access-stackset.yaml"

    if aws cloudformation describe-stack-set \
        --stack-set-name "$STACKSET_NAME" \
        --region "$REGION" &>/dev/null; then
        echo "  StackSet exists, updating..."
        aws cloudformation update-stack-set \
            --stack-set-name "$STACKSET_NAME" \
            --template-body "file://$STACKSET_TEMPLATE" \
            --parameters \
                ParameterKey=DomainAccountId,ParameterValue="$DOMAIN_ACCOUNT_ID" \
                ParameterKey=DomainId,ParameterValue="$DOMAIN_ID" \
            --capabilities CAPABILITY_NAMED_IAM \
            --region "$REGION" 2>/dev/null || echo "  No changes needed"
    else
        echo "  Creating new StackSet..."
        aws cloudformation create-stack-set \
            --stack-set-name "$STACKSET_NAME" \
            --template-body "file://$STACKSET_TEMPLATE" \
            --parameters \
                ParameterKey=DomainAccountId,ParameterValue="$DOMAIN_ACCOUNT_ID" \
                ParameterKey=DomainId,ParameterValue="$DOMAIN_ID" \
            --capabilities CAPABILITY_NAMED_IAM \
            --permission-model SELF_MANAGED \
            --administration-role-arn "arn:aws:iam::${ORG_ADMIN_ACCOUNT_ID}:role/SMUS-AccountPoolFactory-StackSetAdmin" \
            --execution-role-name "SMUS-AccountPoolFactory-StackSetExecution" \
            --region "$REGION"
    fi
    echo "✅ DomainAccess StackSet ready"
    echo ""

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

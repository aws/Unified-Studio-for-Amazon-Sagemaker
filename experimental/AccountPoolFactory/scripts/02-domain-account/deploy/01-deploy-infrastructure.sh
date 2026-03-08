#!/bin/bash
set -e

# Deploy Account Pool Factory Infrastructure
# Deploys CloudFormation stack + all Lambda functions in the domain account.
#
# Usage:
#   ./01-deploy-infrastructure.sh               # full deploy (CFN stack + all Lambdas)
#   ./01-deploy-infrastructure.sh --lambdas-only  # skip CFN stack, update Lambda code only

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

LAMBDAS_ONLY=false
for arg in "$@"; do
    [ "$arg" = "--lambdas-only" ] && LAMBDAS_ONLY=true
done

# Load configuration
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

REGION=$(grep "region:" config.yaml | awk '{print $2}')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')
ORG_ADMIN_ACCOUNT_ID=$(grep "account_id:" config.yaml | head -1 | awk '{print $2}' | tr -d '"')
DOMAIN_ID=$(grep "domain_id:" config.yaml | awk '{print $2}')
ROOT_DOMAIN_UNIT_ID=$(grep "root_domain_unit_id:" config.yaml | awk '{print $2}')
EMAIL_PREFIX=$(grep "email_prefix:" config.yaml | awk '{print $2}')
EMAIL_DOMAIN=$(grep "email_domain:" config.yaml | awk '{print $2}')
TARGET_OU_ID=$(grep "target_ou_id:" config.yaml | awk '{print $2}')

PROJECT_ROLE_ENABLED=$(python3 -c "import yaml; c=yaml.safe_load(open('config.yaml')); print(str(c.get('project_role',{}).get('enabled', True)).lower())" 2>/dev/null || echo "true")
PROJECT_ROLE_NAME=$(python3 -c "import yaml; c=yaml.safe_load(open('config.yaml')); print(c.get('project_role',{}).get('role_name', 'AmazonSageMakerProjectRole'))" 2>/dev/null || echo "AmazonSageMakerProjectRole")
PROJECT_ROLE_POLICY=$(python3 -c "import yaml; c=yaml.safe_load(open('config.yaml')); print(c.get('project_role',{}).get('managed_policy_arn', 'arn:aws:iam::aws:policy/AmazonSageMakerFullAccess'))" 2>/dev/null || echo "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess")
EXPECTED_STACK_PATTERNS=$(python3 -c "
import yaml
c = yaml.safe_load(open('config.yaml'))
print(','.join(c.get('setup_stacks', [])))
" 2>/dev/null || echo "DataZone-VPC-{account_id},DataZone-IAM-{account_id},DataZone-EventBridge-{account_id},DataZone-ProjectRole-{account_id},DataZone-Blueprints-{account_id}")

echo "🚀 Deploying Account Pool Factory Infrastructure"
echo "================================================"
echo "Region:           $REGION"
echo "Domain Account:   $DOMAIN_ACCOUNT_ID"
echo "Org Admin Account:$ORG_ADMIN_ACCOUNT_ID"
echo "Domain ID:        $DOMAIN_ID"
echo "Target OU ID:     $TARGET_OU_ID"
echo "Project Role:     $PROJECT_ROLE_ENABLED ($PROJECT_ROLE_NAME)"
echo "Lambdas only:     $LAMBDAS_ONLY"
echo ""

# Verify we're in the correct account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "$DOMAIN_ACCOUNT_ID" ]; then
    echo "❌ Must run in Domain account ($DOMAIN_ACCOUNT_ID), currently in $CURRENT_ACCOUNT"
    exit 1
fi
echo "✅ Running in correct account"
echo ""

# ── CloudFormation stack (skipped with --lambdas-only) ──────────────────────
if [ "$LAMBDAS_ONLY" = "false" ]; then
    echo "📦 Deploying infrastructure stack..."
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
            ExpectedStackPatterns="$EXPECTED_STACK_PATTERNS" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION"
    echo "✅ Infrastructure stack deployed"

    echo ""
    echo "📊 Stack Outputs:"
    aws cloudformation describe-stacks \
        --stack-name AccountPoolFactory-Infrastructure \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
        --output table
fi

# ── Lambda packaging ─────────────────────────────────────────────────────────
echo ""
echo "📦 Packaging Lambda functions..."

TEMPLATES_DIR="$PROJECT_ROOT/templates/cloudformation/03-project-account/deploy"

# Pool Manager
zip -q "$PROJECT_ROOT/pool-manager.zip" -j "$PROJECT_ROOT/src/pool-manager/lambda_function.py"

# Setup Orchestrator: lambda + all CF templates (flat, no subdirectory)
zip -q "$PROJECT_ROOT/setup-orchestrator.zip" -j "$PROJECT_ROOT/src/setup-orchestrator/lambda_function.py"
zip -q "$PROJECT_ROOT/setup-orchestrator.zip" -j "$TEMPLATES_DIR"/*.yaml

# Single-file Lambdas
zip -q "$PROJECT_ROOT/deprovision-account.zip"  -j "$PROJECT_ROOT/src/deprovision-account/lambda_function.py"
zip -q "$PROJECT_ROOT/account-provider.zip"     -j "$PROJECT_ROOT/src/account-provider/lambda_function_prod.py"
zip -q "$PROJECT_ROOT/account-reconciler.zip"   -j "$PROJECT_ROOT/src/account-reconciler/lambda_function.py"
zip -q "$PROJECT_ROOT/account-recycler.zip"     -j "$PROJECT_ROOT/src/account-recycler/lambda_function.py"

echo "✅ Lambda packages created"

# ── Lambda deployments ───────────────────────────────────────────────────────
deploy_lambda() {
    local name="$1"
    local zipfile="$2"
    echo "🔄 Updating $name..."
    aws lambda update-function-code \
        --function-name "$name" \
        --zip-file "fileb://$zipfile" \
        --region "$REGION" \
        --query 'LastModified' --output text
}

deploy_lambda PoolManager          "$PROJECT_ROOT/pool-manager.zip"
deploy_lambda SetupOrchestrator    "$PROJECT_ROOT/setup-orchestrator.zip"
deploy_lambda DeprovisionAccount   "$PROJECT_ROOT/deprovision-account.zip"
deploy_lambda AccountProvider      "$PROJECT_ROOT/account-provider.zip"
deploy_lambda AccountReconciler    "$PROJECT_ROOT/account-reconciler.zip"
deploy_lambda AccountRecycler      "$PROJECT_ROOT/account-recycler.zip"

# ── Cleanup ──────────────────────────────────────────────────────────────────
rm -f "$PROJECT_ROOT"/{pool-manager,setup-orchestrator,deprovision-account,account-provider,account-reconciler,account-recycler}.zip

echo ""
echo "✅ Deployment complete!"
if [ "$LAMBDAS_ONLY" = "false" ]; then
    echo ""
    echo "Next step: Deploy project profile"
    echo "  ./scripts/02-domain-account/deploy/02-deploy-project-profile.sh"
fi

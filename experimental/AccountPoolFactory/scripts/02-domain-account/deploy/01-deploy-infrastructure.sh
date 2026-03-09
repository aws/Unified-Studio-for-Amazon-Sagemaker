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

source scripts/utils/resolve-config.sh domain

echo "🚀 Deploying Account Pool Factory Infrastructure"
echo "================================================"
echo "Region:                $REGION"
echo "Domain Account:        $DOMAIN_ACCOUNT_ID"
echo "Org Admin Account:     $ORG_ADMIN_ACCOUNT_ID"
echo "Domain ID:             $DOMAIN_ID"
echo "Target OU ID:          $TARGET_OU_ID"
echo "AccountCreation Role:  $ACCOUNT_CREATION_ROLE_ARN"
echo "Project Role:          $PROJECT_ROLE_ENABLED ($PROJECT_ROLE_NAME)"
echo "Lambdas only:          $LAMBDAS_ONLY"
echo ""

if [ "$LAMBDAS_ONLY" = "false" ]; then
    if [ -z "$ACCOUNT_CREATION_ROLE_ARN" ]; then
        echo "❌ AccountCreation role not found. Deploy org admin stack first:"
        echo "   eval \$(isengardcli credentials amirbo+1@amazon.com)"
        echo "   ./scripts/01-org-mgmt-account/deploy/deploy-org-admin.sh $DOMAIN_ACCOUNT_ID $DOMAIN_ID"
        exit 1
    fi
fi

# ── CloudFormation stack ─────────────────────────────────────────────────────
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

zip -q "$PROJECT_ROOT/pool-manager.zip"        -j "$PROJECT_ROOT/src/pool-manager/lambda_function.py"
zip -q "$PROJECT_ROOT/provision-account.zip"   -j "$PROJECT_ROOT/src/provision-account/lambda_function.py"
zip -q "$PROJECT_ROOT/deprovision-account.zip" -j "$PROJECT_ROOT/src/deprovision-account/lambda_function.py"
zip -q "$PROJECT_ROOT/account-provider.zip"    -j "$PROJECT_ROOT/src/account-provider/lambda_function_prod.py"
zip -q "$PROJECT_ROOT/account-reconciler.zip"  -j "$PROJECT_ROOT/src/account-reconciler/lambda_function.py"
zip -q "$PROJECT_ROOT/account-recycler.zip"    -j "$PROJECT_ROOT/src/account-recycler/lambda_function.py"

# Setup Orchestrator: lambda + all CF templates
zip -q "$PROJECT_ROOT/setup-orchestrator.zip"  -j "$PROJECT_ROOT/src/setup-orchestrator/lambda_function.py"
zip -q "$PROJECT_ROOT/setup-orchestrator.zip"  -j "$TEMPLATES_DIR"/*.yaml

echo "✅ Lambda packages created"

# ── Lambda deployments ───────────────────────────────────────────────────────
deploy_lambda() {
    local name="$1" zipfile="$2"
    echo "🔄 Updating $name..."
    aws lambda update-function-code \
        --function-name "$name" \
        --zip-file "fileb://$zipfile" \
        --region "$REGION" \
        --query 'LastModified' --output text
}

deploy_lambda PoolManager          "$PROJECT_ROOT/pool-manager.zip"
deploy_lambda ProvisionAccount     "$PROJECT_ROOT/provision-account.zip"
deploy_lambda SetupOrchestrator    "$PROJECT_ROOT/setup-orchestrator.zip"
deploy_lambda DeprovisionAccount   "$PROJECT_ROOT/deprovision-account.zip"
deploy_lambda AccountProvider      "$PROJECT_ROOT/account-provider.zip"
deploy_lambda AccountReconciler    "$PROJECT_ROOT/account-reconciler.zip"
deploy_lambda AccountRecycler      "$PROJECT_ROOT/account-recycler.zip"

rm -f "$PROJECT_ROOT"/{pool-manager,provision-account,setup-orchestrator,deprovision-account,account-provider,account-reconciler,account-recycler}.zip

echo ""
echo "✅ Deployment complete!"
if [ "$LAMBDAS_ONLY" = "false" ]; then
    echo ""
    echo "Next step: Deploy project profile"
    echo "  ./scripts/02-domain-account/deploy/02-deploy-project-profile.sh"
fi

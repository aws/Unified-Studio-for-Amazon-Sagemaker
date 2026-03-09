#!/bin/bash
set -e

# Deploy Account Pool Factory Infrastructure (domain account).
# Deploy this FIRST — it outputs ProvisionAccountRoleArn needed by the org admin deploy.
#
# Usage:
#   eval $(isengardcli credentials amirbo+3@amazon.com)
#   ./scripts/02-domain-account/deploy/01-deploy.sh               # full deploy
#   ./scripts/02-domain-account/deploy/01-deploy.sh --lambdas-only # Lambda code only

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
echo "Region:         $REGION"
echo "Domain Account: $DOMAIN_ACCOUNT_ID"
echo "Domain ID:      $DOMAIN_ID"
echo "Pools:          $POOL_NAMES"
echo "Project Role:   $PROJECT_ROLE_ENABLED ($PROJECT_ROLE_NAME)"
echo "Lambdas only:   $LAMBDAS_ONLY"
echo ""

# ── Step 1: CloudFormation stack ─────────────────────────────────────────────

if [ "$LAMBDAS_ONLY" = "false" ]; then
    # Resolve org admin account ID — may be empty on first deploy (before org stack exists)
    # That's fine: ProvisionAccountRoleArn is what the org admin needs, not the other way around.
    ORG_ADMIN_ACCOUNT_ID_PARAM="${ORG_ADMIN_ACCOUNT_ID:-000000000000}"
    ACCOUNT_CREATION_ROLE_ARN_PARAM="${ACCOUNT_CREATION_ROLE_ARN:-arn:aws:iam::000000000000:role/placeholder}"
    EXTERNAL_ID_PARAM="${EXTERNAL_ID:-AccountPoolFactory-${DOMAIN_ACCOUNT_ID}}"

    echo "📦 Step 1: Deploying infrastructure stack..."
    aws cloudformation deploy \
        --template-file templates/cloudformation/02-domain-account/deploy/01-infrastructure.yaml \
        --stack-name AccountPoolFactory-Infrastructure \
        --parameter-overrides \
            DomainId="$DOMAIN_ID" \
            DomainAccountId="$DOMAIN_ACCOUNT_ID" \
            RootDomainUnitId="$ROOT_DOMAIN_UNIT_ID" \
            OrgAdminAccountId="$ORG_ADMIN_ACCOUNT_ID_PARAM" \
            AccountCreationRoleArn="$ACCOUNT_CREATION_ROLE_ARN_PARAM" \
            ExternalId="$EXTERNAL_ID_PARAM" \
            OrganizationId="$ORG_ID" \
            ProjectRoleEnabled="$PROJECT_ROLE_ENABLED" \
            ProjectRoleName="$PROJECT_ROLE_NAME" \
            ProjectRoleManagedPolicyArn="$PROJECT_ROLE_POLICY" \
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

    # Resolve ProvisionAccountRoleArn from stack output
    PROVISION_ACCOUNT_ROLE_ARN=$(aws cloudformation describe-stacks \
        --stack-name AccountPoolFactory-Infrastructure \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`ProvisionAccountRoleArn`].OutputValue' \
        --output text)

    echo ""
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║  Hand this to the Org Admin for their deploy step:              ║"
    echo "║                                                                  ║"
    echo "║  ProvisionAccountRoleArn:                                        ║"
    echo "║  $PROVISION_ACCOUNT_ROLE_ARN"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""
fi

# ── Step 2: Write per-pool SSM parameters (domain side) ──────────────────────

if [ "$LAMBDAS_ONLY" = "false" ]; then
    echo "🔧 Step 2: Writing per-pool SSM parameters (domain account)..."
    for pool_name in $POOL_NAMES; do
        KEY=$(echo "$pool_name" | tr '[:lower:]-' '[:upper:]_')
        eval "min_size=\$POOL_${KEY}_MIN_SIZE"
        eval "target_size=\$POOL_${KEY}_TARGET_SIZE"
        eval "reclaim=\$POOL_${KEY}_RECLAIM_STRATEGY"
        eval "profile=\$POOL_${KEY}_PROJECT_PROFILE_NAME"

        aws ssm put-parameter --name "/AccountPoolFactory/Pools/${pool_name}/MinimumPoolSize" \
            --value "$min_size" --type String --overwrite --region "$REGION"  > /dev/null
        aws ssm put-parameter --name "/AccountPoolFactory/Pools/${pool_name}/TargetPoolSize" \
            --value "$target_size" --type String --overwrite --region "$REGION"  > /dev/null
        aws ssm put-parameter --name "/AccountPoolFactory/Pools/${pool_name}/ReclaimStrategy" \
            --value "$reclaim" --type String --overwrite --region "$REGION"  > /dev/null
        aws ssm put-parameter --name "/AccountPoolFactory/Pools/${pool_name}/ProjectProfileName" \
            --value "$profile" --type String --overwrite --region "$REGION"  > /dev/null

        echo "   ✓ SSM params written for pool: $pool_name"
    done

    # Legacy single-pool SSM params (backward compat for Lambdas not yet updated)
    FIRST_POOL=$(echo "$POOL_NAMES" | awk '{print $1}')
    FIRST_KEY=$(echo "$FIRST_POOL" | tr '[:lower:]-' '[:upper:]_')
    eval "first_min=\$POOL_${FIRST_KEY}_MIN_SIZE"
    eval "first_target=\$POOL_${FIRST_KEY}_TARGET_SIZE"
    eval "first_reclaim=\$POOL_${FIRST_KEY}_RECLAIM_STRATEGY"

    aws ssm put-parameter --name "/AccountPoolFactory/PoolManager/MinimumPoolSize" \
        --value "$first_min" --type String --overwrite --region "$REGION"  > /dev/null
    aws ssm put-parameter --name "/AccountPoolFactory/PoolManager/TargetPoolSize" \
        --value "$first_target" --type String --overwrite --region "$REGION"  > /dev/null
    aws ssm put-parameter --name "/AccountPoolFactory/PoolManager/ReclaimStrategy" \
        --value "$first_reclaim" --type String --overwrite --region "$REGION"  > /dev/null
    aws ssm put-parameter --name "/AccountPoolFactory/PoolManager/PoolName" \
        --value "$FIRST_POOL" --type String --overwrite --region "$REGION"  > /dev/null
    aws ssm put-parameter --name "/AccountPoolFactory/PoolManager/NamePrefix" \
        --value "DataZone-Pool" --type String --overwrite --region "$REGION"  > /dev/null
    aws ssm put-parameter --name "/AccountPoolFactory/PoolManager/MaxConcurrentSetups" \
        --value "3" --type String --overwrite --region "$REGION"  > /dev/null
    aws ssm put-parameter --name "/AccountPoolFactory/PoolManager/MaxRecycleRetries" \
        --value "3" --type String --overwrite --region "$REGION"  > /dev/null
    aws ssm put-parameter --name "/AccountPoolFactory/PoolManager/MaxConcurrentRecycles" \
        --value "10" --type String --overwrite --region "$REGION"  > /dev/null
    echo "   ✓ Legacy SSM params written"
    echo ""
fi

# ── Step 3: Lambda packaging & deployment ────────────────────────────────────

echo "📦 Step 3: Packaging Lambda functions..."

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
    echo "Next steps:"
    echo "  1. Give ProvisionAccountRoleArn (shown above) to the Org Admin"
    echo "  2. Org Admin runs: ./scripts/01-org-mgmt-account/deploy/01-deploy.sh $DOMAIN_ACCOUNT_ID $DOMAIN_ID <provision-account-role-arn>"
    echo "  3. Then: ./scripts/02-domain-account/deploy/02-deploy-project-profile.sh"
    echo "  4. Then: ./scripts/02-domain-account/deploy/03-verify.sh"
fi

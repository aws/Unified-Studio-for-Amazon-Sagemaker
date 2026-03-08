#!/bin/bash
set -e

# Deploy ProvisionAccount stack + DomainAccess StackSet to Org Admin Account
# This deploys: AccountCreation role, ProvisionAccount Lambda + role, DomainAccess StackSet
#
# Usage:
#   ./02-deploy-provision-account.sh               # full deploy (CFN + StackSet + Lambda)
#   ./02-deploy-provision-account.sh --lambdas-only  # Lambda code only

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
ORG_ADMIN_ACCOUNT_ID=$(grep "account_id:" config.yaml | head -1 | awk '{print $2}' | tr -d '"')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')
DOMAIN_ID=$(grep "domain_id:" config.yaml | awk '{print $2}')

echo "🚀 Deploy ProvisionAccount + AccountCreation + DomainAccess StackSet"
echo "====================================================================="
echo "Org Admin Account: $ORG_ADMIN_ACCOUNT_ID"
echo "Domain Account:    $DOMAIN_ACCOUNT_ID"
echo "Domain ID:         $DOMAIN_ID"
echo "Region:            $REGION"
echo "Lambdas only:      $LAMBDAS_ONLY"
echo ""

# Verify correct account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "$ORG_ADMIN_ACCOUNT_ID" ]; then
    echo "❌ Must run in Org Admin account ($ORG_ADMIN_ACCOUNT_ID), currently in $CURRENT_ACCOUNT"
    exit 1
fi
echo "✅ Running in correct account"
echo ""

if [ "$LAMBDAS_ONLY" = "false" ]; then
    # Step 1: Deploy CloudFormation stack
    echo "📦 Step 1: Deploying CloudFormation stack..."
    STACK_NAME="AccountPoolFactory-ProvisionAccount"

    aws cloudformation deploy \
        --template-file templates/cloudformation/01-org-mgmt-account/deploy/02-provision-account.yaml \
        --stack-name "$STACK_NAME" \
        --parameter-overrides \
            DomainAccountId="$DOMAIN_ACCOUNT_ID" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION" \
        --no-fail-on-empty-changeset

    echo "✅ CloudFormation stack deployed"
    echo ""

    # Step 2: Create or update DomainAccess StackSet
    echo "📦 Step 2: Creating/updating DomainAccess StackSet..."
    STACKSET_NAME="SMUS-AccountPoolFactory-DomainAccess"
    STACKSET_TEMPLATE="templates/cloudformation/01-org-mgmt-account/deploy/03-domain-access-stackset.yaml"

    if aws cloudformation describe-stack-set \
        --stack-set-name "$STACKSET_NAME" \
        --region "$REGION" &>/dev/null; then
        echo "   StackSet exists, updating..."
        aws cloudformation update-stack-set \
            --stack-set-name "$STACKSET_NAME" \
            --template-body "file://$STACKSET_TEMPLATE" \
            --parameters \
                ParameterKey=DomainAccountId,ParameterValue="$DOMAIN_ACCOUNT_ID" \
                ParameterKey=DomainId,ParameterValue="$DOMAIN_ID" \
            --capabilities CAPABILITY_NAMED_IAM \
            --region "$REGION" 2>/dev/null || echo "   No changes needed"
    else
        echo "   Creating new StackSet..."
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
fi

# Step 3: Deploy Lambda code
echo "🚀 Step 3: Deploying ProvisionAccount Lambda code..."
TEMP_DIR=$(mktemp -d)
cp "$PROJECT_ROOT/src/provision-account/lambda_function.py" "$TEMP_DIR/"
zip -q "$TEMP_DIR/lambda.zip" -j "$PROJECT_ROOT/src/provision-account/lambda_function.py"

aws lambda update-function-code \
    --function-name ProvisionAccount \
    --zip-file "fileb://$TEMP_DIR/lambda.zip" \
    --region "$REGION" \
    --query 'LastModified' --output text

echo "⏳ Waiting for Lambda update..."
aws lambda wait function-updated \
    --function-name ProvisionAccount \
    --region "$REGION"

rm -rf "$TEMP_DIR"
echo "✅ Lambda code deployed"
echo ""

if [ "$LAMBDAS_ONLY" = "false" ]; then
    STACK_NAME="AccountPoolFactory-ProvisionAccount"
    echo "📊 Stack Outputs:"
    ROLE_ARN=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`AccountCreationRoleArn`].OutputValue' \
        --output text)
    EXTERNAL_ID=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`ExternalId`].OutputValue' \
        --output text)
    FUNCTION_ARN=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`ProvisionAccountFunctionArn`].OutputValue' \
        --output text)

    echo "  AccountCreation Role ARN: $ROLE_ARN"
    echo "  External ID:              $EXTERNAL_ID"
    echo "  ProvisionAccount Lambda:  $FUNCTION_ARN"
    echo ""
    echo "Next: Switch to Domain account and update SSM parameters:"
    echo "  aws ssm put-parameter --name /AccountPoolFactory/PoolManager/OrgAdminRoleArn --value '$ROLE_ARN' --type String --overwrite --region $REGION"
    echo "  aws ssm put-parameter --name /AccountPoolFactory/PoolManager/ExternalId --value '$EXTERNAL_ID' --type String --overwrite --region $REGION"
fi

echo "✅ Deployment complete!"

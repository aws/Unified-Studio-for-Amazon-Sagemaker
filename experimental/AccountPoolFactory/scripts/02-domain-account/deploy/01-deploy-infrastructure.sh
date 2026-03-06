#!/bin/bash
set -e

# Deploy Account Pool Factory Infrastructure
# This script deploys all infrastructure components in the domain account

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

# Load configuration
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

# Extract values from config.yaml
REGION=$(grep "region:" config.yaml | awk '{print $2}')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')
ORG_ADMIN_ACCOUNT_ID=$(grep "account_id:" config.yaml | head -1 | awk '{print $2}' | tr -d '"')
DOMAIN_ID=$(grep "domain_id:" config.yaml | awk '{print $2}')
ROOT_DOMAIN_UNIT_ID=$(grep "root_domain_unit_id:" config.yaml | awk '{print $2}')
EMAIL_PREFIX=$(grep "email_prefix:" config.yaml | awk '{print $2}')
EMAIL_DOMAIN=$(grep "email_domain:" config.yaml | awk '{print $2}')
TARGET_OU_ID=$(grep "target_ou_id:" config.yaml | awk '{print $2}')

# Extract project role config
PROJECT_ROLE_ENABLED=$(python3 -c "import yaml; c=yaml.safe_load(open('config.yaml')); print(str(c.get('project_role',{}).get('enabled', True)).lower())" 2>/dev/null || echo "true")
PROJECT_ROLE_NAME=$(python3 -c "import yaml; c=yaml.safe_load(open('config.yaml')); print(c.get('project_role',{}).get('role_name', 'AmazonSageMakerProjectRole'))" 2>/dev/null || echo "AmazonSageMakerProjectRole")
PROJECT_ROLE_POLICY=$(python3 -c "import yaml; c=yaml.safe_load(open('config.yaml')); print(c.get('project_role',{}).get('managed_policy_arn', 'arn:aws:iam::aws:policy/AmazonSageMakerFullAccess'))" 2>/dev/null || echo "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess")

echo "🚀 Deploying Account Pool Factory Infrastructure"
echo "================================================"
echo "Region: $REGION"
echo "Domain Account: $DOMAIN_ACCOUNT_ID"
echo "Org Admin Account: $ORG_ADMIN_ACCOUNT_ID"
echo "Domain ID: $DOMAIN_ID"
echo "Root Domain Unit ID: $ROOT_DOMAIN_UNIT_ID"
echo "Target OU ID: $TARGET_OU_ID"
echo "Project Role: $PROJECT_ROLE_ENABLED ($PROJECT_ROLE_NAME)"
echo ""

# Verify we're in the correct account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "$DOMAIN_ACCOUNT_ID" ]; then
    echo "❌ Error: Must run in Domain account ($DOMAIN_ACCOUNT_ID), currently in $CURRENT_ACCOUNT"
    exit 1
fi
echo "✅ Running in correct account"
echo ""

# Deploy infrastructure stack
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
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION"

echo "✅ Infrastructure stack deployed"

# Get stack outputs
echo ""
echo "📊 Stack Outputs:"
aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-Infrastructure \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

# Package and deploy Lambda functions
echo ""
echo "📦 Packaging Lambda functions..."

# Create deployment package for Pool Manager
cd src/pool-manager
zip -r ../../pool-manager.zip lambda_function.py
cd ../..

# Create deployment package for Setup Orchestrator
cd src/setup-orchestrator
zip -r ../../setup-orchestrator.zip lambda_function.py
cd ../..

# Add CloudFormation templates to Setup Orchestrator package
cd templates/cloudformation/03-project-account/deploy
zip -r ../../../../setup-orchestrator.zip *.yaml
cd ../../../..

echo "✅ Lambda packages created"

# Update Lambda function code
echo ""
echo "🔄 Updating Pool Manager Lambda code..."
aws lambda update-function-code \
    --function-name PoolManager \
    --zip-file fileb://pool-manager.zip \
    --region "$REGION" \
    > /dev/null

echo "✅ Pool Manager code updated"

echo ""
echo "🔄 Updating Setup Orchestrator Lambda code..."
aws lambda update-function-code \
    --function-name SetupOrchestrator \
    --zip-file fileb://setup-orchestrator.zip \
    --region "$REGION" \
    > /dev/null

echo "✅ Setup Orchestrator code updated"

echo ""
echo "🔄 Updating DeprovisionAccount Lambda code..."
cd src/deprovision-account
zip -q ../../deprovision-account.zip lambda_function.py
cd ../..

aws lambda update-function-code \
    --function-name DeprovisionAccount \
    --zip-file fileb://deprovision-account.zip \
    --region "$REGION" \
    > /dev/null

echo "✅ DeprovisionAccount code updated"

echo ""
echo "🔄 Updating AccountProvider Lambda code..."
cd src/account-provider
zip -q ../../account-provider.zip lambda_function_prod.py
cd ../..

aws lambda update-function-code \
    --function-name AccountProvider \
    --zip-file fileb://account-provider.zip \
    --region "$REGION" \
    > /dev/null

echo "✅ AccountProvider code updated"

# Clean up zip files
rm -f pool-manager.zip setup-orchestrator.zip deprovision-account.zip account-provider.zip

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Deployed resources:"
echo "  - CloudFormation stack: AccountPoolFactory-Infrastructure"
echo "  - Lambda functions: PoolManager, SetupOrchestrator, DeprovisionAccount, AccountProvider"
echo ""
echo "Next step: Deploy project profile"
echo "  ./scripts/02-domain-account/deploy/02-deploy-project-profile.sh"

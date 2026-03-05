#!/bin/bash
set -e

# Deploy Account Pool Factory Infrastructure
# This script deploys all infrastructure components in the domain account

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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
EMAIL_DOMAIN=$(grep "email_domain:" config.yaml | awk '{print $2}')
TARGET_OU_ID=$(grep "target_ou_id:" config.yaml | awk '{print $2}')

echo "🚀 Deploying Account Pool Factory Infrastructure"
echo "================================================"
echo "Region: $REGION"
echo "Domain Account: $DOMAIN_ACCOUNT_ID"
echo "Org Admin Account: $ORG_ADMIN_ACCOUNT_ID"
echo "Domain ID: $DOMAIN_ID"
echo "Root Domain Unit ID: $ROOT_DOMAIN_UNIT_ID"
echo "Target OU ID: $TARGET_OU_ID"
echo ""

# Deploy infrastructure stack
echo "📦 Deploying infrastructure stack..."
aws cloudformation deploy \
    --template-file templates/cloudformation/02-domain-account/infrastructure.yaml \
    --stack-name AccountPoolFactory-Infrastructure \
    --parameter-overrides \
        DomainId="$DOMAIN_ID" \
        DomainAccountId="$DOMAIN_ACCOUNT_ID" \
        RootDomainUnitId="$ROOT_DOMAIN_UNIT_ID" \
        OrgAdminAccountId="$ORG_ADMIN_ACCOUNT_ID" \
        TargetOUId="$TARGET_OU_ID" \
        EmailDomain="$EMAIL_DOMAIN" \
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
cd templates/cloudformation/03-project-account
zip -r ../../../setup-orchestrator.zip *.yaml
cd ../../..

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

# Clean up zip files
rm -f pool-manager.zip setup-orchestrator.zip

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Subscribe to SNS alerts:"
echo "   aws sns subscribe --topic-arn \$(aws cloudformation describe-stacks --stack-name AccountPoolFactory-Infrastructure --query 'Stacks[0].Outputs[?OutputKey==\`SNSTopicArn\`].OutputValue' --output text --region $REGION) --protocol email --notification-endpoint YOUR_EMAIL --region $REGION"
echo ""
echo "2. Seed initial pool:"
echo "   ./seed-initial-pool.sh"
echo ""
echo "3. Monitor pool status:"
echo "   aws cloudwatch get-dashboard --dashboard-name AccountPoolFactory-Overview --region $REGION"

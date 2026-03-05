#!/bin/bash
set -e

# Deploy Account Provider Lambda
# This Lambda handles DataZone account pool requests

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

# Load configuration
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

REGION=$(grep "region:" config.yaml | awk '{print $2}')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')
DOMAIN_ID=$(grep "domain_id:" config.yaml | awk '{print $2}')

echo "🚀 Deploying Account Provider Lambda"
echo "====================================="
echo "Region: $REGION"
echo "Domain Account: $DOMAIN_ACCOUNT_ID"
echo "Domain ID: $DOMAIN_ID"
echo ""

# Verify we're in the correct account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "$DOMAIN_ACCOUNT_ID" ]; then
    echo "❌ Error: This script must be run in the Domain account ($DOMAIN_ACCOUNT_ID)"
    echo "   Current account: $CURRENT_ACCOUNT"
    exit 1
fi

echo "✅ Running in correct account"
echo ""

# Deploy AccountProvider Lambda using CloudFormation
echo "📦 Deploying AccountProvider Lambda stack..."
aws cloudformation deploy \
    --template-file templates/cloudformation/02-domain-account/deploy/02-account-provider-lambda.yaml \
    --stack-name AccountPoolFactory-AccountProvider \
    --parameter-overrides DomainId="$DOMAIN_ID" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION"

echo "✅ AccountProvider Lambda stack deployed"
echo ""

# Get stack outputs
LAMBDA_ARN=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-AccountProvider \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionArn`].OutputValue' \
    --output text)

ACCOUNT_RESOLUTION_ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-AccountProvider \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`AccountResolutionRoleArn`].OutputValue' \
    --output text)

echo "📊 Stack Outputs:"
echo "  Lambda ARN: $LAMBDA_ARN"
echo "  Account Resolution Role ARN: $ACCOUNT_RESOLUTION_ROLE_ARN"
echo ""

# Update Lambda function code (if needed)
LAMBDA_FUNCTION_NAME="AccountProvider-${DOMAIN_ID}"

if aws lambda get-function --function-name "$LAMBDA_FUNCTION_NAME" --region "$REGION" 2>/dev/null; then
    echo "🔄 Updating Lambda function code..."
    
    # The Lambda code is embedded in the CloudFormation template
    # To update it, we need to redeploy the stack or update via Lambda API
    
    # Check if there's production code to deploy
    if [ -f "src/account-provider/lambda_function_prod.py" ]; then
        echo "📦 Creating deployment package from production code..."
        cd src/account-provider
        cp lambda_function_prod.py lambda_function.py
        zip -r ../../account-provider.zip lambda_function.py
        rm lambda_function.py
        cd ../..
        
        aws lambda update-function-code \
            --function-name "$LAMBDA_FUNCTION_NAME" \
            --zip-file fileb://account-provider.zip \
            --region "$REGION" \
            > /dev/null
        
        rm -f account-provider.zip
        echo "✅ Lambda function code updated"
    else
        echo "ℹ️  No production code found, using template's embedded code"
    fi
else
    echo "ℹ️  Lambda function will be created by CloudFormation stack"
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Resources created:"
echo "  - Lambda Function: $LAMBDA_FUNCTION_NAME"
echo "  - Lambda Execution Role: AccountProviderLambdaRole-${DOMAIN_ID}"
echo "  - Account Resolution Role: AccountResolutionRole-${DOMAIN_ID}"
echo ""
echo "Next steps:"
echo "1. Create Account Pool in DataZone using the Account Resolution Role ARN"
echo "2. The Account Pool will automatically use this Lambda"
echo ""

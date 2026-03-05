#!/bin/bash

# Deploy ProvisionAccount Lambda to Organization Management Account
# This Lambda handles secure account provisioning with proper role setup

set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Source configuration
if [ ! -f "$PROJECT_ROOT/config.yaml" ]; then
    echo "❌ Error: config.yaml not found at $PROJECT_ROOT/config.yaml"
    echo "   Please copy config.yaml.template to config.yaml and update with your values"
    exit 1
fi

# Parse config.yaml
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" "$PROJECT_ROOT/config.yaml" | awk '{print $2}' | tr -d '"')
REGION=$(grep "region:" "$PROJECT_ROOT/config.yaml" | awk '{print $2}' | tr -d '"')

if [ -z "$DOMAIN_ACCOUNT_ID" ] || [ -z "$REGION" ]; then
    echo "❌ Error: Missing required configuration"
    echo "   domain_account_id: $DOMAIN_ACCOUNT_ID"
    echo "   region: $REGION"
    exit 1
fi

echo "========================================="
echo "Deploy ProvisionAccount Lambda"
echo "========================================="
echo ""
echo "Configuration:"
echo "  Domain Account ID: $DOMAIN_ACCOUNT_ID"
echo "  Region: $REGION"
echo ""

# Verify we're in the correct account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
if [ -z "$CURRENT_ACCOUNT" ]; then
    echo "❌ Error: Unable to get current AWS account"
    echo "   Please ensure AWS credentials are configured"
    exit 1
fi

echo "Current AWS Account: $CURRENT_ACCOUNT"
echo ""

# Step 1: Deploy CloudFormation stack
echo "📦 Step 1: Deploying CloudFormation stack..."
echo ""

TEMPLATE_PATH="$PROJECT_ROOT/templates/cloudformation/01-org-mgmt-account/deploy/05-provision-account-lambda.yaml"
STACK_NAME="AccountPoolFactory-ProvisionAccount"

aws cloudformation deploy \
    --template-file "$TEMPLATE_PATH" \
    --stack-name "$STACK_NAME" \
    --parameter-overrides \
        DomainAccountId="$DOMAIN_ACCOUNT_ID" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    --no-fail-on-empty-changeset

echo ""
echo "✅ CloudFormation stack deployed"
echo ""

# Step 2: Get Lambda function name
echo "📝 Step 2: Getting Lambda function details..."
echo ""

FUNCTION_NAME=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`ProvisionAccountFunctionArn`].OutputValue' \
    --output text | awk -F: '{print $NF}')

if [ -z "$FUNCTION_NAME" ]; then
    echo "❌ Error: Unable to get Lambda function name from stack outputs"
    exit 1
fi

echo "Lambda Function: $FUNCTION_NAME"
echo ""

# Step 3: Package and deploy Lambda code
echo "🚀 Step 3: Deploying Lambda code..."
echo ""

LAMBDA_SRC="$PROJECT_ROOT/src/provision-account"
TEMP_DIR=$(mktemp -d)

# Copy Lambda code to temp directory
cp "$LAMBDA_SRC/lambda_function.py" "$TEMP_DIR/"

# Create deployment package
cd "$TEMP_DIR"
zip -q lambda.zip lambda_function.py

# Deploy Lambda code
aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file fileb://lambda.zip \
    --region "$REGION" \
    > /dev/null

# Wait for update to complete
echo "⏳ Waiting for Lambda update to complete..."
aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"

# Cleanup
cd - > /dev/null
rm -rf "$TEMP_DIR"

echo ""
echo "✅ Lambda code deployed"
echo ""

# Step 4: Verify deployment
echo "🔍 Step 4: Verifying deployment..."
echo ""

FUNCTION_INFO=$(aws lambda get-function \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Configuration.[FunctionName,Runtime,Timeout,MemorySize,LastModified]' \
    --output text)

echo "Function Details:"
echo "$FUNCTION_INFO" | awk '{print "  Name: " $1 "\n  Runtime: " $2 "\n  Timeout: " $3 "s\n  Memory: " $4 "MB\n  Last Modified: " $5}'
echo ""

# Get function ARN
FUNCTION_ARN=$(aws lambda get-function \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Configuration.FunctionArn' \
    --output text)

echo "✅ Deployment complete!"
echo ""
echo "========================================="
echo "Next Steps"
echo "========================================="
echo ""
echo "1. Update Domain account infrastructure to use this Lambda"
echo "   Run: scripts/02-domain-account/deploy/01-deploy-infrastructure.sh"
echo ""
echo "2. Update PoolManager Lambda code to invoke ProvisionAccount"
echo "   Run: scripts/02-domain-account/deploy/02-deploy-lambdas.sh"
echo ""
echo "Function ARN: $FUNCTION_ARN"
echo ""

#!/bin/bash
set -e

# Create DataZone Account Pool with Account Provider Lambda
# This script creates the account pool and registers the Lambda

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load configuration
REGION=$(grep "region:" config.yaml | awk '{print $2}')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')
DOMAIN_ID=$(grep "domain_id:" config.yaml | awk '{print $2}')

echo "🚀 Creating DataZone Account Pool"
echo "=================================="
echo "Domain ID: $DOMAIN_ID"
echo "Domain Account: $DOMAIN_ACCOUNT_ID"
echo "Region: $REGION"
echo ""

# Get Lambda ARN
LAMBDA_ARN=$(aws lambda get-function \
    --function-name AccountProvider \
    --region "$REGION" \
    --query 'Configuration.FunctionArn' \
    --output text)

# Get Lambda Role ARN
LAMBDA_ROLE_ARN=$(aws lambda get-function \
    --function-name AccountProvider \
    --region "$REGION" \
    --query 'Configuration.Role' \
    --output text)

echo "Lambda Function ARN: $LAMBDA_ARN"
echo "Lambda Role ARN: $LAMBDA_ROLE_ARN"
echo ""

# Account Pool Configuration
POOL_NAME="AccountPoolFactory"
POOL_DESCRIPTION="Automated account pool managed by Account Pool Factory"
RESOLUTION_STRATEGY="MANUAL"

# Check if account pool already exists
echo "Checking if account pool already exists..."
EXISTING_POOL=$(aws datazone list-account-pools \
    --domain-identifier "$DOMAIN_ID" \
    --region "$REGION" \
    --query "items[?name=='$POOL_NAME'].id" \
    --output text 2>/dev/null || echo "")

if [ -n "$EXISTING_POOL" ]; then
    echo "⚠️  Account pool already exists with ID: $EXISTING_POOL"
    echo ""
    echo "Do you want to delete and recreate it? (y/n)"
    read -r RESPONSE
    if [ "$RESPONSE" = "y" ]; then
        echo "Deleting existing account pool..."
        aws datazone delete-account-pool \
            --domain-identifier "$DOMAIN_ID" \
            --identifier "$EXISTING_POOL" \
            --region "$REGION"
        echo "✅ Deleted account pool: $EXISTING_POOL"
        echo "⏳ Waiting 5 seconds before recreating..."
        sleep 5
    else
        echo "Keeping existing account pool. Exiting."
        exit 0
    fi
fi

# Create account pool
echo "📦 Creating account pool..."
POOL_OUTPUT=$(aws datazone create-account-pool \
    --domain-identifier "$DOMAIN_ID" \
    --name "$POOL_NAME" \
    --description "$POOL_DESCRIPTION" \
    --account-source "{
        \"customAccountPoolHandler\": {
            \"lambdaFunctionArn\": \"$LAMBDA_ARN\",
            \"lambdaExecutionRoleArn\": \"$LAMBDA_ROLE_ARN\"
        }
    }" \
    --resolution-strategy "$RESOLUTION_STRATEGY" \
    --region "$REGION" \
    --output json)

POOL_ID=$(echo "$POOL_OUTPUT" | jq -r '.id')
POOL_ARN=$(echo "$POOL_OUTPUT" | jq -r '.arn')

echo ""
echo "✅ Account pool created successfully!"
echo ""
echo "Pool ID: $POOL_ID"
echo "Pool ARN: $POOL_ARN"
echo "Pool Name: $POOL_NAME"
echo "Resolution Strategy: $RESOLUTION_STRATEGY"
echo ""

# Save pool details to file
echo "$POOL_OUTPUT" | jq '.' > account-pool-details.json
echo "📄 Pool details saved to: account-pool-details.json"
echo ""

# Get pool details
echo "📊 Account pool details:"
aws datazone get-account-pool \
    --domain-identifier "$DOMAIN_ID" \
    --identifier "$POOL_ID" \
    --region "$REGION" \
    --output json | jq '.'

echo ""
echo "✅ Account pool setup complete!"
echo ""
echo "Next steps:"
echo "1. Create a project profile that uses this account pool"
echo "2. Seed the initial pool with accounts"
echo "3. Create a test project"
echo ""

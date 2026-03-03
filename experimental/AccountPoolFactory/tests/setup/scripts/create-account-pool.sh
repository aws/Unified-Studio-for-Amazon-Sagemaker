#!/bin/bash
set -e

# Create DataZone Account Pool with placeholder Lambda ARNs
# This validates that the account pool can be created before implementing the Lambda

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load configuration
CONFIG_FILE="$PROJECT_ROOT/config.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Parse configuration using Python
read -r DOMAIN_ID DOMAIN_ACCOUNT_ID REGION < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['domain_account_id'], config['aws']['region'])
EOF
)

echo "=== Creating DataZone Account Pool ==="
echo "Domain ID: $DOMAIN_ID"
echo "Domain Account: $DOMAIN_ACCOUNT_ID"
echo "Region: $REGION"
echo ""

# Account Pool Configuration
POOL_NAME="AccountPoolFactory-CustomPool"
POOL_DESCRIPTION="Custom account pool managed by Account Pool Factory"
RESOLUTION_STRATEGY="MANUAL"

# Placeholder Lambda ARNs (will be replaced when Lambda is created)
LAMBDA_FUNCTION_ARN="arn:aws:lambda:${REGION}:${DOMAIN_ACCOUNT_ID}:function:AccountProvider-${DOMAIN_ID}"
LAMBDA_ROLE_ARN="arn:aws:iam::${DOMAIN_ACCOUNT_ID}:role/AccountProviderLambdaRole-${DOMAIN_ID}"

echo "Pool Name: $POOL_NAME"
echo "Resolution Strategy: $RESOLUTION_STRATEGY"
echo "Lambda Function ARN (placeholder): $LAMBDA_FUNCTION_ARN"
echo "Lambda Role ARN (placeholder): $LAMBDA_ROLE_ARN"
echo ""

# Check if account pool already exists
echo "Checking if account pool already exists..."
EXISTING_POOL=$(aws datazone list-account-pools \
    --domain-identifier "$DOMAIN_ID" \
    --region "$REGION" \
    --query "items[?name=='$POOL_NAME'].id" \
    --output text 2>/dev/null || echo "")

if [ -n "$EXISTING_POOL" ]; then
    echo "Account pool already exists with ID: $EXISTING_POOL"
    echo ""
    echo "Do you want to delete and recreate it? (y/n)"
    read -r RESPONSE
    if [ "$RESPONSE" = "y" ]; then
        echo "Deleting existing account pool..."
        aws datazone delete-account-pool \
            --domain-identifier "$DOMAIN_ID" \
            --identifier "$EXISTING_POOL" \
            --region "$REGION"
        echo "Deleted account pool: $EXISTING_POOL"
        echo "Waiting 5 seconds before recreating..."
        sleep 5
    else
        echo "Keeping existing account pool. Exiting."
        exit 0
    fi
fi

# Create account pool
echo "Creating account pool..."
POOL_OUTPUT=$(aws datazone create-account-pool \
    --domain-identifier "$DOMAIN_ID" \
    --name "$POOL_NAME" \
    --description "$POOL_DESCRIPTION" \
    --account-source '{
        "customAccountPoolHandler": {
            "lambdaFunctionArn": "'"$LAMBDA_FUNCTION_ARN"'",
            "lambdaExecutionRoleArn": "'"$LAMBDA_ROLE_ARN"'"
        }
    }' \
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
POOL_FILE="$PROJECT_ROOT/account-pool-details.json"
echo "$POOL_OUTPUT" | jq '.' > "$POOL_FILE"
echo "Pool details saved to: $POOL_FILE"
echo ""

# Get pool details
echo "Retrieving account pool details..."
aws datazone get-account-pool \
    --domain-identifier "$DOMAIN_ID" \
    --identifier "$POOL_ID" \
    --region "$REGION" \
    --output json | jq '.'

echo ""
echo "=== Next Steps ==="
echo "1. Create the Account Provider Lambda function with ARN: $LAMBDA_FUNCTION_ARN"
echo "2. Create the Lambda execution role with ARN: $LAMBDA_ROLE_ARN"
echo "3. Update the account pool to use the real Lambda ARNs"
echo "4. Test the account pool by creating a DataZone project"
echo ""
echo "Note: The Lambda ARNs are placeholders. The account pool will not work until the Lambda is created."

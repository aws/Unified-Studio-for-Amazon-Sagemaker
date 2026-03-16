#!/bin/bash
set -e

# Deploy Account Provider Lambda
# This Lambda returns a hardcoded test account for the account pool

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load configuration
CONFIG_FILE="$PROJECT_ROOT/config.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Parse configuration
read -r DOMAIN_ID REGION < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['region'])
EOF
)

echo "=== Deploying Account Provider Lambda ==="
echo "Domain ID: $DOMAIN_ID"
echo "Region: $REGION"
echo ""

# Deploy CloudFormation stack
STACK_NAME="AccountPoolFactory-AccountProvider-Test"
TEMPLATE_FILE="$PROJECT_ROOT/02-domain-account/templates/cloudformation/01-infrastructure.yaml"

echo "Deploying CloudFormation stack: $STACK_NAME"
aws cloudformation deploy \
    --template-file "$TEMPLATE_FILE" \
    --stack-name "$STACK_NAME" \
    --parameter-overrides \
        DomainId="$DOMAIN_ID" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    --no-fail-on-empty-changeset

echo ""
echo "✅ Lambda deployed successfully!"
echo ""

# Get stack outputs
LAMBDA_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionArn`].OutputValue' \
    --output text)

ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`LambdaRoleArn`].OutputValue' \
    --output text)

LOG_GROUP=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`LogGroupName`].OutputValue' \
    --output text)

echo "Lambda Function ARN: $LAMBDA_ARN"
echo "Lambda Role ARN: $ROLE_ARN"
echo "Log Group: $LOG_GROUP"
echo ""

# Save Lambda details
LAMBDA_FILE="$PROJECT_ROOT/account-provider-lambda-details.json"
cat > "$LAMBDA_FILE" <<EOF
{
  "functionArn": "$LAMBDA_ARN",
  "roleArn": "$ROLE_ARN",
  "logGroup": "$LOG_GROUP",
  "stackName": "$STACK_NAME",
  "domainId": "$DOMAIN_ID"
}
EOF

echo "Lambda details saved to: $LAMBDA_FILE"
echo ""

# Test the Lambda function
echo "=== Testing Lambda Function ==="
echo "Invoking Lambda with test event..."

# Create temp file for test event
TEST_EVENT_FILE=$(mktemp)
cat > "$TEST_EVENT_FILE" <<EOF
{
  "domainId": "$DOMAIN_ID",
  "projectId": "test-project-id",
  "environmentBlueprintId": "test-blueprint-id",
  "requestId": "test-request-id"
}
EOF

# Create temp file for response
RESPONSE_FILE=$(mktemp)
trap "rm -f $TEST_EVENT_FILE $RESPONSE_FILE" EXIT

aws lambda invoke \
    --function-name "AccountProvider-$DOMAIN_ID" \
    --payload file://"$TEST_EVENT_FILE" \
    --region "$REGION" \
    "$RESPONSE_FILE" > /dev/null

RESPONSE=$(cat "$RESPONSE_FILE")
echo "Lambda Response: $RESPONSE"
echo ""

# Check if response is valid
ACCOUNT_ID=$(echo "$RESPONSE" | jq -r '.accountId // empty')
REGION_RESPONSE=$(echo "$RESPONSE" | jq -r '.region // empty')

if [ -n "$ACCOUNT_ID" ] && [ -n "$REGION_RESPONSE" ]; then
    echo "✅ Lambda test successful!"
    echo "   Account ID: $ACCOUNT_ID"
    echo "   Region: $REGION_RESPONSE"
else
    echo "❌ Lambda test failed - invalid response format"
    exit 1
fi

echo ""
echo "=== Next Steps ==="
echo "1. Update account pool with Lambda ARNs"
echo "2. Create a DataZone project using the profile"
echo "3. Verify account assignment"
echo ""
echo "To view Lambda logs:"
echo "  aws logs tail $LOG_GROUP --follow --region $REGION"

#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

CONFIG_FILE="$PROJECT_ROOT/config.yaml"

read -r DOMAIN_ID REGION < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['region'])
EOF
)

FUNCTION_NAME="AccountProvider-${DOMAIN_ID}"
SOURCE_FILE="$PROJECT_ROOT/src/account-provider/lambda_function.py"

echo "=== Updating Lambda Code ==="
echo "Function: $FUNCTION_NAME"
echo "Source: $SOURCE_FILE"
echo ""

# Create zip in project directory
cd "$PROJECT_ROOT/src/account-provider"
zip -q lambda.zip lambda_function.py

# Update function
aws lambda update-function-code \
  --function-name "$FUNCTION_NAME" \
  --zip-file fileb://lambda.zip \
  --region "$REGION" \
  --query '{FunctionName:FunctionName, LastModified:LastModified, CodeSize:CodeSize}' \
  --output json

echo ""
echo "✅ Lambda code updated!"

# Cleanup
rm -f lambda.zip

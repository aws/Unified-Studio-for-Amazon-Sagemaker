#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

CONFIG_FILE="$PROJECT_ROOT/config.yaml"
DOMAIN_ID=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['datazone']['domain_id'])")
REGION=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['aws']['region'])")

echo "Updating Lambda code..."

# Create zip file
cd "$PROJECT_ROOT/src/account-provider"
zip -q lambda.zip lambda_function.py

# Update Lambda
aws lambda update-function-code \
    --function-name "AccountProvider-$DOMAIN_ID" \
    --zip-file fileb://lambda.zip \
    --region "$REGION" > /dev/null

rm lambda.zip

echo "✅ Lambda updated"

# Wait for update to complete
sleep 5

# Test Lambda
cd "$PROJECT_ROOT"
./tests/setup/scripts/test-lambda-direct.sh

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
TEMPLATE_FILE="$PROJECT_ROOT/02-domain-account/templates/cloudformation/01-infrastructure.yaml"
TEMP_FILE="/tmp/index.py"

echo "=== Updating Lambda Code ==="
echo "Function: $FUNCTION_NAME"
echo ""

# Extract Lambda code from template
python3 <<PYEOF > "$TEMP_FILE"
import yaml
with open('$TEMPLATE_FILE', 'r') as f:
    template = yaml.safe_load(f)
code = template['Resources']['AccountProviderFunction']['Properties']['Code']['ZipFile']
print(code)
PYEOF

echo "Extracted code to: $TEMP_FILE"

# Create zip
cd /tmp
zip -q lambda.zip index.py

# Update function
aws lambda update-function-code \
  --function-name "$FUNCTION_NAME" \
  --zip-file fileb:///tmp/lambda.zip \
  --region "$REGION" \
  --query '{FunctionName:FunctionName, LastModified:LastModified, CodeSize:CodeSize}' \
  --output json

echo ""
echo "✅ Lambda code updated!"

# Cleanup
rm -f /tmp/index.py /tmp/lambda.zip

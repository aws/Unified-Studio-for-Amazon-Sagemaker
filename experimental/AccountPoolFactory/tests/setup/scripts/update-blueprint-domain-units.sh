#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

CONFIG_FILE="$PROJECT_ROOT/config.yaml"

# Parse configuration
read -r DOMAIN_ID REGION ROOT_DOMAIN_UNIT < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['region'], config['datazone']['root_domain_unit_id'])
EOF
)

TARGET_ACCOUNT="004878717744"

echo "=== Updating Blueprint Domain Unit Authorization ==="
echo "Domain ID: $DOMAIN_ID"
echo "Root Domain Unit: $ROOT_DOMAIN_UNIT"
echo "Target Account: $TARGET_ACCOUNT"
echo "Region: $REGION"
echo ""

# Get org admin credentials to assume role in target account
eval "$(isengardcli creds amirbo+1 --role Admin)"

# Assume role in target account
CREDS=$(aws sts assume-role \
  --role-arn "arn:aws:iam::$TARGET_ACCOUNT:role/OrganizationAccountAccessRole" \
  --role-session-name "UpdateBlueprints" \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text)

export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | awk '{print $1}')
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | awk '{print $2}')
export AWS_SESSION_TOKEN=$(echo "$CREDS" | awk '{print $3}')

# Get all blueprint IDs
echo "Step 1: Getting blueprint configurations..."
BLUEPRINT_IDS=$(aws datazone list-environment-blueprint-configurations \
  --domain-identifier "$DOMAIN_ID" \
  --region "$REGION" \
  --query 'items[].environmentBlueprintId' \
  --output json)

BLUEPRINT_COUNT=$(echo "$BLUEPRINT_IDS" | jq 'length')
echo "Found $BLUEPRINT_COUNT blueprints"
echo ""

# Update each blueprint with domain unit authorization
echo "Step 2: Updating blueprints with domain unit authorization..."
UPDATE_COUNT=0

for BLUEPRINT_ID in $(echo "$BLUEPRINT_IDS" | jq -r '.[]'); do
  echo "  Updating blueprint: $BLUEPRINT_ID"
  
  # Get current configuration
  CONFIG=$(aws datazone get-environment-blueprint-configuration \
    --domain-identifier "$DOMAIN_ID" \
    --environment-blueprint-identifier "$BLUEPRINT_ID" \
    --region "$REGION" \
    --output json)
  
  # Extract current values
  MANAGE_ROLE=$(echo "$CONFIG" | jq -r '.manageAccessRoleArn')
  PROVISIONING_ROLE=$(echo "$CONFIG" | jq -r '.provisioningRoleArn')
  ENABLED_REGIONS=$(echo "$CONFIG" | jq -r '.enabledRegions | join(",")')
  
  # Check if regional parameters exist
  HAS_PARAMS=$(echo "$CONFIG" | jq -r '.regionalParameters | length')
  
  if [ "$HAS_PARAMS" -gt 0 ]; then
    # Has regional parameters - need to include them
    REGIONAL_PARAMS=$(echo "$CONFIG" | jq -c '.regionalParameters')
    
    aws datazone put-environment-blueprint-configuration \
      --domain-identifier "$DOMAIN_ID" \
      --environment-blueprint-identifier "$BLUEPRINT_ID" \
      --enabled-regions "$ENABLED_REGIONS" \
      --manage-access-role-arn "$MANAGE_ROLE" \
      --provisioning-role-arn "$PROVISIONING_ROLE" \
      --regional-parameters "$REGIONAL_PARAMS" \
      --provisioning-configurations "[{\"domainUnitId\": \"$ROOT_DOMAIN_UNIT\"}]" \
      --region "$REGION" \
      --output json > /dev/null
  else
    # No regional parameters
    aws datazone put-environment-blueprint-configuration \
      --domain-identifier "$DOMAIN_ID" \
      --environment-blueprint-identifier "$BLUEPRINT_ID" \
      --enabled-regions "$ENABLED_REGIONS" \
      --manage-access-role-arn "$MANAGE_ROLE" \
      --provisioning-role-arn "$PROVISIONING_ROLE" \
      --provisioning-configurations "[{\"domainUnitId\": \"$ROOT_DOMAIN_UNIT\"}]" \
      --region "$REGION" \
      --output json > /dev/null
  fi
  
  ((UPDATE_COUNT++))
done

echo ""
echo "✅ Updated $UPDATE_COUNT blueprint configurations with domain unit authorization!"
echo ""
echo "All blueprints are now authorized for the root domain unit: $ROOT_DOMAIN_UNIT"

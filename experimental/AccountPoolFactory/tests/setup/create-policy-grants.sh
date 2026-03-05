#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

CONFIG_FILE="$PROJECT_ROOT/config.yaml"
PROFILE_FILE="$PROJECT_ROOT/project-profile-details.json"

# Parse configuration
read -r DOMAIN_ID REGION < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['region'])
EOF
)

PROFILE_ID=$(jq -r '.profileId' "$PROFILE_FILE")
TARGET_ACCOUNT="004878717744"

echo "=== Creating Policy Grants for Project Profile ==="
echo "Domain ID: $DOMAIN_ID"
echo "Profile ID: $PROFILE_ID"
echo "Target Account: $TARGET_ACCOUNT"
echo "Region: $REGION"
echo ""

# Get all blueprint configurations from the target account
echo "Step 1: Getting blueprint configurations from account $TARGET_ACCOUNT..."

# Need to use org admin credentials to assume role in target account
# Save current domain credentials
DOMAIN_ACCESS_KEY=$AWS_ACCESS_KEY_ID
DOMAIN_SECRET_KEY=$AWS_SECRET_ACCESS_KEY
DOMAIN_SESSION_TOKEN=$AWS_SESSION_TOKEN

# Get org admin credentials
eval "$(isengardcli creds amirbo+1 --role Admin)"

# Assume role in target account
CREDS=$(aws sts assume-role \
  --role-arn "arn:aws:iam::$TARGET_ACCOUNT:role/OrganizationAccountAccessRole" \
  --role-session-name "GetBlueprints" \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text)

export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | awk '{print $1}')
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | awk '{print $2}')
export AWS_SESSION_TOKEN=$(echo "$CREDS" | awk '{print $3}')

BLUEPRINT_IDS=$(aws datazone list-environment-blueprint-configurations \
  --domain-identifier "$DOMAIN_ID" \
  --region "$REGION" \
  --query 'items[].environmentBlueprintId' \
  --output json)

echo "Found $(echo "$BLUEPRINT_IDS" | jq 'length') blueprints"
echo ""

# Restore domain account credentials
export AWS_ACCESS_KEY_ID=$DOMAIN_ACCESS_KEY
export AWS_SECRET_ACCESS_KEY=$DOMAIN_SECRET_KEY
export AWS_SESSION_TOKEN=$DOMAIN_SESSION_TOKEN

# Create policy grants for each blueprint
echo "Step 2: Creating policy grants in domain account..."
GRANT_COUNT=0

# Get the root domain unit ID from config
ROOT_DOMAIN_UNIT=$(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['root_domain_unit_id'])
EOF
)

for BLUEPRINT_ID in $(echo "$BLUEPRINT_IDS" | jq -r '.[]'); do
  echo "  Creating grant for blueprint: $BLUEPRINT_ID"
  
  # Entity identifier format: awsAccountId:blueprintId
  ENTITY_ID="${TARGET_ACCOUNT}:${BLUEPRINT_ID}"
  
  aws datazone add-policy-grant \
    --domain-identifier "$DOMAIN_ID" \
    --entity-type ENVIRONMENT_BLUEPRINT_CONFIGURATION \
    --entity-identifier "$ENTITY_ID" \
    --principal "{\"project\": {\"projectDesignation\": \"CONTRIBUTOR\", \"projectGrantFilter\": {\"domainUnitFilter\": {\"domainUnit\": \"$ROOT_DOMAIN_UNIT\", \"includeChildDomainUnits\": true}}}}" \
    --policy-type CREATE_ENVIRONMENT_FROM_BLUEPRINT \
    --detail "{\"createEnvironmentFromBlueprint\": {}}" \
    --region "$REGION" \
    --output json 2>&1 | grep -v "ConflictException" || echo "    (grant already exists)"
  
  ((GRANT_COUNT++))
done

echo ""
echo "✅ Created $GRANT_COUNT policy grants for project profile $PROFILE_ID"
echo ""
echo "Project profile can now create environments from all enabled blueprints!"

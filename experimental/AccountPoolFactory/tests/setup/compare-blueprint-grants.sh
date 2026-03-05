#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

CONFIG_FILE="$PROJECT_ROOT/config.yaml"

# Parse configuration
read -r DOMAIN_ID REGION DOMAIN_ACCOUNT < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['region'], config['aws']['domain_account_id'])
EOF
)

PROJECT_ACCOUNT="004878717744"

echo "=== Comparing Blueprint Configurations ==="
echo "Domain ID: $DOMAIN_ID"
echo "Domain Account: $DOMAIN_ACCOUNT"
echo "Project Account: $PROJECT_ACCOUNT"
echo "Region: $REGION"
echo ""

# Get domain account blueprints
echo "=== Domain Account ($DOMAIN_ACCOUNT) Blueprints ==="
eval "$(isengardcli creds amirbo+3 --role Admin)"

aws datazone list-environment-blueprint-configurations \
  --domain-identifier "$DOMAIN_ID" \
  --region "$REGION" \
  --output json | jq -r '.items[] | "\(.environmentBlueprintId) - \(.provisioningConfigurationDomainUnitId // "null")"'

echo ""
echo "=== Project Account ($PROJECT_ACCOUNT) Blueprints ==="

# Switch to project account
eval "$(isengardcli creds amirbo+1 --role Admin)"
CREDS=$(aws sts assume-role \
  --role-arn "arn:aws:iam::$PROJECT_ACCOUNT:role/OrganizationAccountAccessRole" \
  --role-session-name "GetBlueprints" \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text)

export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | awk '{print $1}')
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | awk '{print $2}')
export AWS_SESSION_TOKEN=$(echo "$CREDS" | awk '{print $3}')

aws datazone list-environment-blueprint-configurations \
  --domain-identifier "$DOMAIN_ID" \
  --region "$REGION" \
  --output json | jq -r '.items[] | "\(.environmentBlueprintId) - \(.provisioningConfigurationDomainUnitId // "null")"'

echo ""
echo "=== Getting Policy Grants for Domain Account Blueprints ==="
eval "$(isengardcli creds amirbo+3 --role Admin)"

# Get one blueprint ID from domain account
SAMPLE_BLUEPRINT=$(aws datazone list-environment-blueprint-configurations \
  --domain-identifier "$DOMAIN_ID" \
  --region "$REGION" \
  --output json | jq -r '.items[0].environmentBlueprintId')

echo "Sample Blueprint ID: $SAMPLE_BLUEPRINT"
echo "Checking policy grants..."

aws datazone list-policy-grants \
  --domain-identifier "$DOMAIN_ID" \
  --entity-type ENVIRONMENT_BLUEPRINT_CONFIGURATION \
  --entity-identifier "$DOMAIN_ACCOUNT:$SAMPLE_BLUEPRINT" \
  --policy-type CREATE_ENVIRONMENT_FROM_BLUEPRINT \
  --region "$REGION" \
  --output json | jq '.'

echo ""
echo "=== Getting Policy Grants for Project Account Blueprints ==="

# Switch to project account
eval "$(isengardcli creds amirbo+1 --role Admin)"
CREDS=$(aws sts assume-role \
  --role-arn "arn:aws:iam::$PROJECT_ACCOUNT:role/OrganizationAccountAccessRole" \
  --role-session-name "GetGrants" \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text)

export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | awk '{print $1}')
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | awk '{print $2}')
export AWS_SESSION_TOKEN=$(echo "$CREDS" | awk '{print $3}')

# Get one blueprint ID from project account
SAMPLE_PROJECT_BLUEPRINT=$(aws datazone list-environment-blueprint-configurations \
  --domain-identifier "$DOMAIN_ID" \
  --region "$REGION" \
  --output json | jq -r '.items[0].environmentBlueprintId')

echo "Sample Blueprint ID: $SAMPLE_PROJECT_BLUEPRINT"
echo "Checking policy grants (without account prefix)..."

aws datazone list-policy-grants \
  --domain-identifier "$DOMAIN_ID" \
  --entity-type ENVIRONMENT_BLUEPRINT_CONFIGURATION \
  --entity-identifier "$SAMPLE_PROJECT_BLUEPRINT" \
  --policy-type CREATE_ENVIRONMENT_FROM_BLUEPRINT \
  --region "$REGION" \
  --output json | jq '.'

echo ""
echo "Checking policy grants (with account prefix)..."

aws datazone list-policy-grants \
  --domain-identifier "$DOMAIN_ID" \
  --entity-type ENVIRONMENT_BLUEPRINT_CONFIGURATION \
  --entity-identifier "$PROJECT_ACCOUNT:$SAMPLE_PROJECT_BLUEPRINT" \
  --policy-type CREATE_ENVIRONMENT_FROM_BLUEPRINT \
  --region "$REGION" \
  --output json | jq '.'

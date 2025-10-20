#!/bin/bash
set -euo pipefail

# Modified bootstrap script for existing cicd-test-domain
# Account: 588738596778
# Domain: cicd-test-domain (dzd_629k4alubnlko9)
# Region: us-east-2

# 0. Set project owners (using current assumed role ARN)
PROJECT_OWNERS='["arn:aws:sts::588738596778:assumed-role/Admin/amirbo-Isengard"]'

# 1. Use existing domain
DOMAIN_IDENTIFIER="dzd_629k4alubnlko9"
echo "Using existing domain: $DOMAIN_IDENTIFIER (cicd-test-domain)"

# 2. List managed environment blueprints and filter for LakehouseAdmin
BLUEPRINTS_JSON=$(aws datazone list-environment-blueprints \
  --domain-identifier "$DOMAIN_IDENTIFIER" \
  --managed \
  --region us-east-2 \
  --output json)

ADMIN_BLUEPRINT_ID=$(echo "$BLUEPRINTS_JSON" | jq -r '.items[] | select(.name=="LakehouseAdmin") | .id')

if [[ -z "$ADMIN_BLUEPRINT_ID" || "$ADMIN_BLUEPRINT_ID" == "null" ]]; then
  echo "Error: No LakehouseAdmin blueprint found." >&2
  exit 1
fi

echo "Selected LakehouseAdmin blueprint: $ADMIN_BLUEPRINT_ID"

# 3. Define other inputs - using the domain's execution role
PROVISIONING_ROLE_ARN="arn:aws:iam::588738596778:role/cicd-test-domain-DomainExecutionRole"
ACTION="ADD_RESOURCE_TYPE"
CLIENT_TOKEN=$(uuidgen)

# 4. Build BootstrapConfiguration JSON (without projectName)
BOOTSTRAP_CONFIGURATION=$(cat <<EOF
[
  {
    "environmentBlueprintId": "$ADMIN_BLUEPRINT_ID",
    "projectOwners": $PROJECT_OWNERS,
    "environmentConfiguration": [
      {
        "key": "autoPublish",
        "value": "false"
      }
    ]
  }
]
EOF
)

echo "Bootstrap configuration:"
echo "$BOOTSTRAP_CONFIGURATION"

# 5. Call start-account-bootstrap-action
echo "Starting account bootstrap action..."
aws datazone start-account-bootstrap-action \
  --domain-identifier "$DOMAIN_IDENTIFIER" \
  --provisioning-role-arn "$PROVISIONING_ROLE_ARN" \
  --action "$ACTION" \
  --client-token "$CLIENT_TOKEN" \
  --bootstrap-configuration "$BOOTSTRAP_CONFIGURATION" \
  --region us-east-2

echo "Account bootstrap action initiated successfully!"

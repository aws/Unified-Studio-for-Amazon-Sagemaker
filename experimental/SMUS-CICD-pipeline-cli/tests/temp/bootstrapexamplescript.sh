#!/bin/bash
set -euo pipefail

# 0. Set project owners (comma-separated ARNs)
PROJECT_OWNERS='["arn:aws:iam::123456789012:user/ProjectOwnerUser"]'

# 1. Create the domain and capture the domain identifier
CREATE_DOMAIN_OUTPUT=$(aws datazone create-domain \
  --name "my-domain" \
  --description "Demo domain" \
  --output json)

DOMAIN_IDENTIFIER=$(echo "$CREATE_DOMAIN_OUTPUT" | jq -r '.id')

echo "Created domain with ID: $DOMAIN_IDENTIFIER"

# 2. List managed environment blueprints and filter for LakehouseAdmin
BLUEPRINTS_JSON=$(aws datazone list-environment-blueprints \
  --domain-identifier "$DOMAIN_IDENTIFIER" \
  --managed \
  --output json)

ADMIN_BLUEPRINT_ID=$(echo "$BLUEPRINTS_JSON" | jq -r '.items[] | select(.name=="LakehouseAdmin") | .id')

if [[ -z "$ADMIN_BLUEPRINT_ID" || "$ADMIN_BLUEPRINT_ID" == "null" ]]; then
  echo "Error: No LakehouseAdmin blueprint found." >&2
  exit 1
fi

echo "Selected LakehouseAdmin blueprint: $ADMIN_BLUEPRINT_ID"

# 3. Define other inputs
PROVISIONING_ROLE_ARN="arn:aws:iam::123456789012:role/YourProvisioningRole"
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

# 5. Call start-account-bootstrap-action
aws datazone start-account-bootstrap-action \
  --domain-identifier "$DOMAIN_IDENTIFIER" \
  --provisioning-role-arn "$PROVISIONING_ROLE_ARN" \
  --action "$ACTION" \
  --client-token "$CLIENT_TOKEN" \
  --bootstrap-configuration "$BOOTSTRAP_CONFIGURATION"
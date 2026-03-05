#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

CONFIG_FILE="$PROJECT_ROOT/config.yaml"
POOL_FILE="$PROJECT_ROOT/account-pool-details.json"
PROFILE_FILE="$PROJECT_ROOT/project-profile-details.json"

# Parse configuration
read -r DOMAIN_ID REGION DEFAULT_OWNER < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['region'], config['datazone']['default_project_owner'])
EOF
)

POOL_ID=$(jq -r '.id' "$POOL_FILE")
PROFILE_ID=$(jq -r '.profileId' "$PROFILE_FILE")

echo "=== Testing Complete Account Pool Flow ==="
echo "Domain ID: $DOMAIN_ID"
echo "Pool ID: $POOL_ID"
echo "Profile ID: $PROFILE_ID"
echo "Region: $REGION"
echo ""

# Step 1: List accounts in pool
echo "Step 1: Listing accounts in pool..."
ACCOUNTS_JSON=$(aws datazone list-accounts-in-account-pool \
  --domain-identifier "$DOMAIN_ID" \
  --identifier "$POOL_ID" \
  --region "$REGION" \
  --output json)

echo "$ACCOUNTS_JSON" | jq '.'

# Extract first account
ACCOUNT_ID=$(echo "$ACCOUNTS_JSON" | jq -r '.items[0].awsAccountId')
ACCOUNT_NAME=$(echo "$ACCOUNTS_JSON" | jq -r '.items[0].awsAccountName')
FIRST_REGION=$(echo "$ACCOUNTS_JSON" | jq -r '.items[0].supportedRegions[0]')

echo ""
echo "Selected account:"
echo "  Account ID: $ACCOUNT_ID"
echo "  Account Name: $ACCOUNT_NAME"
echo "  Region: $FIRST_REGION"
echo ""

# Step 2: Create project with account from pool
PROJECT_NAME="test-pool-project-$(date +%s)"

echo "Step 2: Creating project with account pool..."
echo "  Project Name: $PROJECT_NAME"
echo "  Profile ID: $PROFILE_ID"
echo "  Owner: $DEFAULT_OWNER"
echo "  Account from pool: $ACCOUNT_ID"
echo ""
echo "Note: ON_CREATE environments should be created automatically"
echo ""

PROJECT_JSON=$(aws datazone create-project \
  --domain-identifier "$DOMAIN_ID" \
  --name "$PROJECT_NAME" \
  --project-profile-id "$PROFILE_ID" \
  --region "$REGION" \
  --output json)

PROJECT_ID=$(echo "$PROJECT_JSON" | jq -r '.id')
echo "✅ Project created: $PROJECT_ID"
echo ""

# Save project details
echo "$PROJECT_JSON" > "$PROJECT_ROOT/test-project-pool-details.json"

# Step 3: Wait for project to become ACTIVE
echo "Step 3: Waiting for project to become ACTIVE..."
for i in {1..30}; do
  STATUS=$(aws datazone get-project \
    --domain-identifier "$DOMAIN_ID" \
    --identifier "$PROJECT_ID" \
    --region "$REGION" \
    --query 'projectStatus' \
    --output text)
  
  echo "  Attempt $i/30: Status = $STATUS"
  
  if [ "$STATUS" = "ACTIVE" ]; then
    echo "✅ Project is ACTIVE!"
    break
  fi
  
  sleep 2
done

echo ""

# Step 4: Check if environments were created
echo "Step 4: Checking for ON_CREATE environments..."
ENV_COUNT=$(aws datazone list-environments \
  --domain-identifier "$DOMAIN_ID" \
  --project-identifier "$PROJECT_ID" \
  --region "$REGION" \
  --query 'length(items)' \
  --output text)

echo "Number of environments: $ENV_COUNT"
echo ""

if [ "$ENV_COUNT" -gt 0 ]; then
  echo "✅ Environments created!"
  aws datazone list-environments \
    --domain-identifier "$DOMAIN_ID" \
    --project-identifier "$PROJECT_ID" \
    --region "$REGION" \
    --output json | jq '.items[] | {name, status, awsAccountId, awsAccountRegion}'
else
  echo "⚠️  No environments created automatically"
fi

echo ""
echo "=== Summary ==="
echo "Project ID: $PROJECT_ID"
echo "Project Name: $PROJECT_NAME"
echo "Account Used: $ACCOUNT_ID ($ACCOUNT_NAME)"
echo "Region: $FIRST_REGION"
echo "Environments: $ENV_COUNT"

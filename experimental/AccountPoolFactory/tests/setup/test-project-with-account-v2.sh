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

echo "=== Testing Account Pool with Resolved Account ==="
echo "Domain ID: $DOMAIN_ID"
echo "Pool ID: $POOL_ID"
echo "Profile ID: $PROFILE_ID"
echo "Region: $REGION"
echo ""

# Set credentials for domain account
echo "Setting credentials for domain account..."
eval "$(isengardcli creds amirbo+3 --role Admin)"
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

# Step 2: Create project with resolved account
PROJECT_NAME="test-pool-project-$(date +%s)-$RANDOM-$RANDOM"

echo "Step 2: Creating project with resolved account from pool..."
echo "  Project Name: $PROJECT_NAME"
echo "  Profile ID: $PROFILE_ID"
echo "  Owner: $DEFAULT_OWNER"
echo "  Resolved Account: $ACCOUNT_ID"
echo "  Resolved Region: $FIRST_REGION"
echo ""

# Pass resolved account for ALL environments (required when using account pools)
# ON_CREATE will be created immediately, ON_DEMAND will be created later
PROJECT_JSON=$(aws datazone create-project \
  --domain-identifier "$DOMAIN_ID" \
  --name "$PROJECT_NAME" \
  --project-profile-id "$PROFILE_ID" \
  --user-parameters "[
    {
      \"environmentConfigurationName\": \"Tooling\",
      \"environmentResolvedAccount\": {
        \"awsAccountId\": \"$ACCOUNT_ID\",
        \"regionName\": \"$FIRST_REGION\",
        \"sourceAccountPoolId\": \"$POOL_ID\"
      }
    },
    {
      \"environmentConfigurationName\": \"Lakehouse Database\",
      \"environmentResolvedAccount\": {
        \"awsAccountId\": \"$ACCOUNT_ID\",
        \"regionName\": \"$FIRST_REGION\",
        \"sourceAccountPoolId\": \"$POOL_ID\"
      }
    },
    {
      \"environmentConfigurationName\": \"Lakehouse Catalog\",
      \"environmentResolvedAccount\": {
        \"awsAccountId\": \"$ACCOUNT_ID\",
        \"regionName\": \"$FIRST_REGION\",
        \"sourceAccountPoolId\": \"$POOL_ID\"
      }
    },
    {
      \"environmentConfigurationName\": \"RedshiftServerless\",
      \"environmentResolvedAccount\": {
        \"awsAccountId\": \"$ACCOUNT_ID\",
        \"regionName\": \"$FIRST_REGION\",
        \"sourceAccountPoolId\": \"$POOL_ID\"
      }
    },
    {
      \"environmentConfigurationName\": \"OnDemand Workflows\",
      \"environmentResolvedAccount\": {
        \"awsAccountId\": \"$ACCOUNT_ID\",
        \"regionName\": \"$FIRST_REGION\",
        \"sourceAccountPoolId\": \"$POOL_ID\"
      }
    },
    {
      \"environmentConfigurationName\": \"OnDemand MLExperiments\",
      \"environmentResolvedAccount\": {
        \"awsAccountId\": \"$ACCOUNT_ID\",
        \"regionName\": \"$FIRST_REGION\",
        \"sourceAccountPoolId\": \"$POOL_ID\"
      }
    },
    {
      \"environmentConfigurationName\": \"OnDemand EMR on EC2 Memory-Optimized\",
      \"environmentResolvedAccount\": {
        \"awsAccountId\": \"$ACCOUNT_ID\",
        \"regionName\": \"$FIRST_REGION\",
        \"sourceAccountPoolId\": \"$POOL_ID\"
      }
    },
    {
      \"environmentConfigurationName\": \"OnDemand EMRServerless\",
      \"environmentResolvedAccount\": {
        \"awsAccountId\": \"$ACCOUNT_ID\",
        \"regionName\": \"$FIRST_REGION\",
        \"sourceAccountPoolId\": \"$POOL_ID\"
      }
    }
  ]" \
  --region "$REGION" \
  --output json)

PROJECT_ID=$(echo "$PROJECT_JSON" | jq -r '.id')
echo "✅ Project created: $PROJECT_ID"
echo ""

# Save project details
echo "$PROJECT_JSON" > "$PROJECT_ROOT/test-project-details.json"

# Step 2b: Add analyst1-amirbo as project owner
echo "Step 2b: Adding $DEFAULT_OWNER as project owner..."
aws datazone create-project-membership \
  --domain-identifier "$DOMAIN_ID" \
  --project-identifier "$PROJECT_ID" \
  --designation PROJECT_OWNER \
  --member "{\"userIdentifier\": \"$DEFAULT_OWNER\"}" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ Added $DEFAULT_OWNER as project owner"
echo ""

# Step 3: Wait for environment deployment to complete
echo "Step 3: Waiting for environment deployment..."
for i in {1..60}; do
  PROJECT_STATUS=$(aws datazone get-project \
    --domain-identifier "$DOMAIN_ID" \
    --identifier "$PROJECT_ID" \
    --region "$REGION" \
    --output json)
  
  STATUS=$(echo "$PROJECT_STATUS" | jq -r '.projectStatus')
  DEPLOYMENT_STATUS=$(echo "$PROJECT_STATUS" | jq -r '.environmentDeploymentDetails.overallDeploymentStatus // "NONE"')
  
  echo "  Attempt $i/60: projectStatus=$STATUS, deploymentStatus=$DEPLOYMENT_STATUS"
  
  # Check if deployment completed (success or failure)
  if [ "$DEPLOYMENT_STATUS" = "COMPLETED" ] || [ "$DEPLOYMENT_STATUS" = "FAILED_DEPLOYMENT" ] || [ "$DEPLOYMENT_STATUS" = "FAILED_VALIDATION" ]; then
    echo ""
    echo "Deployment finished with status: $DEPLOYMENT_STATUS"
    
    # Check for failure reasons
    FAILURE_REASONS=$(echo "$PROJECT_STATUS" | jq -r '.environmentDeploymentDetails.environmentFailureReasons // {}')
    if [ "$FAILURE_REASONS" != "{}" ]; then
      echo ""
      echo "⚠️  Deployment failures:"
      echo "$FAILURE_REASONS" | jq '.'
    fi
    break
  fi
  
  sleep 3
done

echo ""

# Step 4: Check if environments were created
echo "Step 4: Checking for environments..."
ENVS_JSON=$(aws datazone list-environments \
  --domain-identifier "$DOMAIN_ID" \
  --project-identifier "$PROJECT_ID" \
  --region "$REGION" \
  --output json)

ENV_COUNT=$(echo "$ENVS_JSON" | jq '.items | length')

echo "Number of environments: $ENV_COUNT"
echo ""

if [ "$ENV_COUNT" -gt 0 ]; then
  echo "✅ Environments created!"
  echo "$ENVS_JSON" | jq '.items[] | {name, status, awsAccountId, awsAccountRegion}'
else
  echo "⚠️  No environments created"
fi

echo ""
echo "=== Summary ==="
echo "Project ID: $PROJECT_ID"
echo "Project Name: $PROJECT_NAME"
echo "Account Used: $ACCOUNT_ID ($ACCOUNT_NAME)"
echo "Region: $FIRST_REGION"
echo "Environments: $ENV_COUNT"

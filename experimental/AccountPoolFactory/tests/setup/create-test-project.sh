#!/bin/bash
set -e

# Create a test DataZone project using the account pool profile
#
# Flow:
#   1. Look up profile and pool IDs
#   2. Call list-accounts-in-account-pool to resolve an account from the pool
#   3. Fetch profile environment configurations dynamically
#   4. If ToolingLite blueprint detected, create project execution role in pool account
#   5. Create project with environmentResolvedAccount for each config
#   6. Wait for project + environments to deploy
#
# Usage:
#   ./create-test-project.sh [project-owner] [--role-arn <arn>]
#
# Arguments:
#   project-owner   DataZone user identifier (default: from config.yaml)
#   --role-arn       Existing IAM role ARN to use for ToolingLite (skips role creation)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

CONFIG_FILE="$PROJECT_ROOT/config.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

# Parse arguments
ROLE_ARN=""
POSITIONAL_ARGS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --role-arn)
            ROLE_ARN="$2"
            shift 2
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

# Parse configuration
eval "$(python3 - <<EOF
import yaml, os
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
default_owner = os.environ.get('PROJECT_OWNER', config.get('datazone', {}).get('default_project_owner', 'analyst1-amirbo'))
profile_name = config.get('account_pool', {}).get('project_profile_name', 'All Capabilities - Account Pool')
print(f"DOMAIN_ID='{config['datazone']['domain_id']}'")
print(f"REGION='{config['aws']['region']}'")
print(f"DOMAIN_ACCOUNT_ID='{config['aws']['domain_account_id']}'")
print(f"PROFILE_NAME='{profile_name}'")
print(f"DEFAULT_OWNER='{default_owner}'")
EOF
)"

# Verify correct account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "$DOMAIN_ACCOUNT_ID" ]; then
    echo "❌ Must run in Domain account ($DOMAIN_ACCOUNT_ID), currently in $CURRENT_ACCOUNT"
    exit 1
fi

# Allow override via positional parameter
PROJECT_OWNER="${POSITIONAL_ARGS[0]:-$DEFAULT_OWNER}"
TIMESTAMP=$(date +%s)
PROJECT_NAME="test-project-pool-$TIMESTAMP"

echo "🚀 Creating DataZone Test Project"
echo "=================================="
echo "Domain ID:     $DOMAIN_ID"
echo "Region:        $REGION"
echo "Profile Name:  $PROFILE_NAME"
echo "Project Name:  $PROJECT_NAME"
echo "Project Owner: $PROJECT_OWNER"
if [ -n "$ROLE_ARN" ]; then
    echo "Role ARN:      $ROLE_ARN (provided)"
fi
echo ""

# --- Step 1: Look up profile ID ---
echo "📋 Step 1: Looking up project profile..."
PROFILE_ID=$(aws datazone list-project-profiles \
    --domain-identifier "$DOMAIN_ID" \
    --region "$REGION" \
    --query "items[?name=='$PROFILE_NAME'].id" \
    --output text 2>/dev/null || echo "")

if [ -z "$PROFILE_ID" ] || [ "$PROFILE_ID" = "None" ]; then
    echo "❌ Project profile '$PROFILE_NAME' not found"
    echo "   Deploy it first: ./02-domain-account/scripts/deploy/02-deploy-project-profile.sh"
    exit 1
fi
echo "  Profile ID: $PROFILE_ID"
echo ""

# --- Step 2: Get account pool ID ---
echo "📋 Step 2: Getting account pool..."
POOL_FILE="$PROJECT_ROOT/account-pool-details.json"
if [ -f "$POOL_FILE" ]; then
    POOL_ID=$(python3 -c "import json; print(json.load(open('$POOL_FILE'))['id'])")
else
    POOL_ID=$(aws datazone list-account-pools \
        --domain-identifier "$DOMAIN_ID" \
        --region "$REGION" \
        --query 'items[0].id' \
        --output text)
fi

if [ -z "$POOL_ID" ] || [ "$POOL_ID" = "None" ]; then
    echo "❌ No account pool found"
    exit 1
fi
echo "  Pool ID: $POOL_ID"
echo ""

# --- Step 3: Resolve account from pool ---
echo "📋 Step 3: Resolving account from pool (list-accounts-in-account-pool)..."
ACCOUNTS_JSON=$(aws datazone list-accounts-in-account-pool \
    --domain-identifier "$DOMAIN_ID" \
    --identifier "$POOL_ID" \
    --region "$REGION" \
    --output json)

ACCOUNT_ID=$(echo "$ACCOUNTS_JSON" | python3 -c "import json,sys; items=json.loads(sys.stdin.read()).get('items',[]); print(items[0]['awsAccountId'] if items else '')")
ACCOUNT_REGION=$(echo "$ACCOUNTS_JSON" | python3 -c "import json,sys; items=json.loads(sys.stdin.read()).get('items',[]); print(items[0]['supportedRegions'][0] if items and items[0].get('supportedRegions') else '$REGION')")

if [ -z "$ACCOUNT_ID" ]; then
    echo "❌ No accounts available in pool"
    echo "   Seed the pool first: ./tests/setup/03-seed-test-accounts.sh"
    exit 1
fi
echo "  Resolved Account: $ACCOUNT_ID"
echo "  Resolved Region:  $ACCOUNT_REGION"
echo ""

# --- Step 4: Fetch environment config names from profile ---
echo "📋 Step 4: Fetching environment configurations from profile..."
PROFILE_JSON=$(aws datazone get-project-profile \
    --domain-identifier "$DOMAIN_ID" \
    --identifier "$PROFILE_ID" \
    --region "$REGION" \
    --output json)

# Build --user-parameters dynamically from profile environment configurations
USER_PARAMS=$(echo "$PROFILE_JSON" | python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
pool_id = '$POOL_ID'
account_id = '$ACCOUNT_ID'
region = '$ACCOUNT_REGION'
configs = data.get('environmentConfigurations', [])
params = []
for cfg in configs:
    params.append({
        'environmentConfigurationName': cfg['name'],
        'environmentResolvedAccount': {
            'awsAccountId': account_id,
            'regionName': region,
            'sourceAccountPoolId': pool_id
        }
    })
print(json.dumps(params))
")

ENV_COUNT=$(echo "$USER_PARAMS" | python3 -c "import json,sys; print(len(json.loads(sys.stdin.read())))")
echo "  Environment configurations: $ENV_COUNT"
echo "$USER_PARAMS" | python3 -c "
import json, sys
params = json.loads(sys.stdin.read())
for p in params:
    print(f\"    - {p['environmentConfigurationName']}\")
"
echo ""

# --- Step 5: Check for ToolingLite blueprint and resolve project role ---
HAS_TOOLING_LITE=$(echo "$PROFILE_JSON" | python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
configs = data.get('environmentConfigurations', [])
for cfg in configs:
    name = cfg.get('name', '')
    if 'toolinglite' in name.lower():
        print('true')
        sys.exit(0)
print('false')
")

if [ "$HAS_TOOLING_LITE" = "true" ]; then
    echo "📋 Step 5: ToolingLite blueprint detected — project execution role required"

    if [ -n "$ROLE_ARN" ]; then
        echo "  Using provided role ARN: $ROLE_ARN"
    else
        # Read role name from config.yaml
        PROJECT_ROLE_NAME=$(python3 -c "import yaml; c=yaml.safe_load(open('$CONFIG_FILE')); print(c.get('project_role',{}).get('role_name', 'AmazonSageMakerProjectRole'))")
        ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/service-role/${PROJECT_ROLE_NAME}"
        echo "  Using role from config: $ROLE_ARN"
        echo "  (deployed by SetupOrchestrator Wave 1)"
    fi
    echo ""
else
    echo "📋 Step 5: No ToolingLite blueprint — skipping project role"
    echo ""
fi

# --- Step 6: Create project ---
echo "📋 Step 6: Creating project..."

if [ -n "$ROLE_ARN" ]; then
    ROLE_CONFIGS=$(python3 -c "
import json
configs = [{'roleArn': '$ROLE_ARN', 'roleDesignation': 'PROJECT_CONTRIBUTOR'}]
print(json.dumps(configs))
")
    echo "  Including customerProvidedRoleConfigs: $ROLE_ARN"
    PROJECT_RESPONSE=$(aws datazone create-project \
        --domain-identifier "$DOMAIN_ID" \
        --name "$PROJECT_NAME" \
        --description "Test project to verify account pool integration" \
        --project-profile-id "$PROFILE_ID" \
        --user-parameters "$USER_PARAMS" \
        --customer-provided-role-configs "$ROLE_CONFIGS" \
        --region "$REGION" \
        --output json)
else
    PROJECT_RESPONSE=$(aws datazone create-project \
        --domain-identifier "$DOMAIN_ID" \
        --name "$PROJECT_NAME" \
        --description "Test project to verify account pool integration" \
        --project-profile-id "$PROFILE_ID" \
        --user-parameters "$USER_PARAMS" \
        --region "$REGION" \
        --output json)
fi

PROJECT_ID=$(echo "$PROJECT_RESPONSE" | jq -r '.id')
PROJECT_STATUS=$(echo "$PROJECT_RESPONSE" | jq -r '.projectStatus')

echo "  ✅ Project created!"
echo "  Project ID:     $PROJECT_ID"
echo "  Project Status: $PROJECT_STATUS"
echo ""

# Save project details
cat > "$PROJECT_ROOT/test-project-details.json" <<EOJSON
{
  "projectId": "$PROJECT_ID",
  "projectName": "$PROJECT_NAME",
  "profileId": "$PROFILE_ID",
  "domainId": "$DOMAIN_ID",
  "resolvedAccountId": "$ACCOUNT_ID",
  "resolvedRegion": "$ACCOUNT_REGION",
  "poolId": "$POOL_ID",
  "roleArn": "$ROLE_ARN",
  "createdAt": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOJSON

# --- Step 7: Wait for deployment ---
echo "📋 Step 7: Waiting for environment deployment..."
MAX_ATTEMPTS=60

for i in $(seq 1 $MAX_ATTEMPTS); do
    PROJECT_STATUS_JSON=$(aws datazone get-project \
        --domain-identifier "$DOMAIN_ID" \
        --identifier "$PROJECT_ID" \
        --region "$REGION" \
        --output json)

    STATUS=$(echo "$PROJECT_STATUS_JSON" | jq -r '.projectStatus')
    DEPLOYMENT_STATUS=$(echo "$PROJECT_STATUS_JSON" | jq -r '.environmentDeploymentDetails.overallDeploymentStatus // "PENDING"')

    echo "  Attempt $i/$MAX_ATTEMPTS: projectStatus=$STATUS, deploymentStatus=$DEPLOYMENT_STATUS"

    if [ "$DEPLOYMENT_STATUS" = "COMPLETED" ] || [ "$DEPLOYMENT_STATUS" = "FAILED_DEPLOYMENT" ] || [ "$DEPLOYMENT_STATUS" = "FAILED_VALIDATION" ]; then
        echo ""
        if [ "$DEPLOYMENT_STATUS" = "COMPLETED" ]; then
            echo "  ✅ Deployment completed!"
        else
            echo "  ❌ Deployment failed: $DEPLOYMENT_STATUS"
            FAILURE_REASONS=$(echo "$PROJECT_STATUS_JSON" | jq '.environmentDeploymentDetails.environmentFailureReasons // {}')
            if [ "$FAILURE_REASONS" != "{}" ]; then
                echo "  Failure reasons:"
                echo "$FAILURE_REASONS" | jq '.'
            fi
        fi
        break
    fi

    if [ "$STATUS" = "CREATE_FAILED" ]; then
        echo ""
        echo "  ❌ Project creation failed!"
        echo "$PROJECT_STATUS_JSON" | jq '{id, name, projectStatus, failureReasons}'
        exit 1
    fi

    sleep 3
done

if [ "$i" = "$MAX_ATTEMPTS" ]; then
    echo ""
    echo "  ⚠️  Timeout waiting for deployment (status: $DEPLOYMENT_STATUS)"
fi

echo ""

# --- Step 8: Check environments ---
echo "📋 Step 8: Checking environments..."
ENVIRONMENTS=$(aws datazone list-environments \
    --domain-identifier "$DOMAIN_ID" \
    --project-identifier "$PROJECT_ID" \
    --region "$REGION" \
    --output json)

ACTUAL_ENV_COUNT=$(echo "$ENVIRONMENTS" | jq '.items | length')
echo "  Environments created: $ACTUAL_ENV_COUNT"

if [ "$ACTUAL_ENV_COUNT" -gt 0 ]; then
    echo ""
    echo "$ENVIRONMENTS" | jq -r '.items[] | "  - \(.name): \(.status) (Account: \(.awsAccountId // "pending"), Region: \(.awsAccountRegion // "pending"))"'
fi

echo ""

# --- Summary ---
echo "=================================="
echo "Project ID:       $PROJECT_ID"
echo "Project Name:     $PROJECT_NAME"
echo "Resolved Account: $ACCOUNT_ID"
echo "Resolved Region:  $ACCOUNT_REGION"
echo "Pool ID:          $POOL_ID"
if [ -n "$ROLE_ARN" ]; then
    echo "Role ARN:         $ROLE_ARN"
fi
echo "Environments:     $ACTUAL_ENV_COUNT"
echo ""
echo "To delete this project:"
echo "  aws datazone delete-project --domain-identifier $DOMAIN_ID --identifier $PROJECT_ID --region $REGION --skip-deletion-check"

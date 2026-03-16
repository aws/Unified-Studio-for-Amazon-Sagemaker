#!/bin/bash
set -e

# Deploy Project Profile with Account Pool
# Clones an existing profile's environment configurations and replaces
# static account references with the account pool.
#
# Usage:
#   ./02-domain-account/scripts/deploy/02-deploy-project-profile.sh [source-profile-name]
#
# Arguments:
#   source-profile-name  Name of existing profile to clone (default: "Default Project Profile")
#
# The new profile name is read from 02-domain-account/config.yaml (project_profile_name)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

source "$SCRIPT_DIR/../resolve-config.sh"

SOURCE_PROFILE_NAME="${1:-Default Project Profile}"
TARGET_PROFILE_NAME="$PROJECT_PROFILE_NAME"

echo "🚀 Deploying Project Profile with Account Pool"
echo "================================================"
echo "Region: $REGION  |  Domain: $DOMAIN_ID"
echo "Source Profile: $SOURCE_PROFILE_NAME"
echo "Target Profile: $TARGET_PROFILE_NAME"
echo ""

# Get Account Pool ID
POOL_FILE="$PROJECT_ROOT/account-pool-details.json"
if [ -f "$POOL_FILE" ]; then
    ACCOUNT_POOL_ID=$(python3 -c "import json; print(json.load(open('$POOL_FILE'))['id'])")
else
    echo "📋 Fetching account pool ID from DataZone..."
    ACCOUNT_POOL_ID=$(aws datazone list-account-pools \
        --domain-identifier "$DOMAIN_ID" \
        --region "$REGION" \
        --query 'items[0].id' \
        --output text)
fi

if [ -z "$ACCOUNT_POOL_ID" ] || [ "$ACCOUNT_POOL_ID" = "None" ]; then
    echo "❌ No account pool found. Create one first."
    exit 1
fi
echo "Account Pool ID: $ACCOUNT_POOL_ID"
echo ""

# Find source profile
echo "📋 Looking up source profile: $SOURCE_PROFILE_NAME"
SOURCE_PROFILE_ID=$(aws datazone list-project-profiles \
    --domain-identifier "$DOMAIN_ID" \
    --region "$REGION" \
    --query "items[?name=='$SOURCE_PROFILE_NAME'].id" \
    --output text 2>/dev/null || echo "")

if [ -z "$SOURCE_PROFILE_ID" ] || [ "$SOURCE_PROFILE_ID" = "None" ]; then
    echo "❌ Source profile '$SOURCE_PROFILE_NAME' not found"
    echo "   Available profiles:"
    aws datazone list-project-profiles \
        --domain-identifier "$DOMAIN_ID" \
        --region "$REGION" \
        --query "items[*].name" \
        --output text
    exit 1
fi
echo "  Source Profile ID: $SOURCE_PROFILE_ID"
echo ""

# Fetch source profile environment configurations
echo "📋 Fetching source profile environment configurations..."
SOURCE_PROFILE_JSON=$(aws datazone get-project-profile \
    --domain-identifier "$DOMAIN_ID" \
    --identifier "$SOURCE_PROFILE_ID" \
    --region "$REGION" \
    --output json)

# Build new environment configurations: clone source, replace awsAccount with accountPools
ENV_CONFIGS=$(echo "$SOURCE_PROFILE_JSON" | python3 -c "
import json, sys

data = json.load(sys.stdin)
pool_id = '$ACCOUNT_POOL_ID'
configs = data.get('environmentConfigurations', [])

new_configs = []
for cfg in configs:
    new_cfg = {
        'name': cfg['name'],
        'environmentBlueprintId': cfg['environmentBlueprintId'],
        'accountPools': [pool_id],
    }
    # Do NOT include awsAccount or awsRegion — not allowed with accountPools
    if 'description' in cfg:
        new_cfg['description'] = cfg['description']
    if 'deploymentMode' in cfg:
        new_cfg['deploymentMode'] = cfg['deploymentMode']
    if 'deploymentOrder' in cfg and cfg['deploymentOrder'] is not None:
        new_cfg['deploymentOrder'] = cfg['deploymentOrder']
    if 'configurationParameters' in cfg:
        params = cfg['configurationParameters']
        if 'parameterOverrides' in params and params['parameterOverrides']:
            new_cfg['configurationParameters'] = {
                'parameterOverrides': params['parameterOverrides']
            }
    new_configs.append(new_cfg)

print(json.dumps(new_configs))
")

ENV_COUNT=$(echo "$ENV_CONFIGS" | python3 -c "import json,sys; print(len(json.loads(sys.stdin.read())))")
echo "  Cloned $ENV_COUNT environment configurations"
echo ""

# Check if target profile already exists
echo "📋 Checking if target profile already exists..."
EXISTING_PROFILE_ID=$(aws datazone list-project-profiles \
    --domain-identifier "$DOMAIN_ID" \
    --region "$REGION" \
    --query "items[?name=='$TARGET_PROFILE_NAME'].id" \
    --output text 2>/dev/null || echo "")

if [ -n "$EXISTING_PROFILE_ID" ] && [ "$EXISTING_PROFILE_ID" != "None" ]; then
    echo "  Found existing profile: $EXISTING_PROFILE_ID — updating..."
    echo ""

    RESULT=$(aws datazone update-project-profile \
        --domain-identifier "$DOMAIN_ID" \
        --identifier "$EXISTING_PROFILE_ID" \
        --environment-configurations "$ENV_CONFIGS" \
        --status ENABLED \
        --region "$REGION" \
        --output json)

    PROFILE_ID=$(echo "$RESULT" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['id'])")
    echo "✅ Project profile updated!"
else
    echo "  No existing profile found — creating new..."
    echo ""

    RESULT=$(aws datazone create-project-profile \
        --domain-identifier "$DOMAIN_ID" \
        --name "$TARGET_PROFILE_NAME" \
        --description "Cloned from '$SOURCE_PROFILE_NAME' with account pool for dynamic account assignment." \
        --domain-unit-identifier "$ROOT_DOMAIN_UNIT_ID" \
        --environment-configurations "$ENV_CONFIGS" \
        --status ENABLED \
        --region "$REGION" \
        --output json)

    PROFILE_ID=$(echo "$RESULT" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['id'])")
    echo "✅ Project profile created!"
fi

echo ""
echo "Profile ID: $PROFILE_ID"
echo "Profile Name: $TARGET_PROFILE_NAME"
echo "Source: $SOURCE_PROFILE_NAME"
echo "Account Pool: $ACCOUNT_POOL_ID"
echo "Environments: $ENV_COUNT"

#!/bin/bash
set -e

# Create Open Project Profile with Account Pool (for IAM-based domains)
# Open projects use ToolingLite blueprint and simpler configurations

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load configuration
REGION=$(grep "region:" config.yaml | awk '{print $2}')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')
DOMAIN_ID=$(grep "domain_id:" config.yaml | awk '{print $2}')
DOMAIN_UNIT_ID=$(grep "root_domain_unit_id:" config.yaml | awk '{print $2}')

echo "🚀 Creating Open Project Profile with Account Pool (IAM Domain)"
echo "=============================================================="
echo "Domain ID: $DOMAIN_ID"
echo "Domain Unit ID: $DOMAIN_UNIT_ID"
echo "Domain Account: $DOMAIN_ACCOUNT_ID"
echo "Region: $REGION"
echo ""

# Check if account pool details exist
if [ ! -f "account-pool-details.json" ]; then
    echo "❌ Error: account-pool-details.json not found"
    echo "Please run ./create-account-pool.sh first"
    exit 1
fi

# Get account pool ID
ACCOUNT_POOL_ID=$(jq -r '.id' account-pool-details.json)
echo "Account Pool ID: $ACCOUNT_POOL_ID"
echo ""

# Fetch blueprint IDs
echo "📋 Fetching blueprint IDs from domain..."
BLUEPRINT_MAP_FILE=$(mktemp)
trap "rm -f $BLUEPRINT_MAP_FILE" EXIT

aws datazone list-environment-blueprint-configurations \
    --domain-identifier "$DOMAIN_ID" \
    --region "$REGION" \
    --output json | jq -r '.items[].environmentBlueprintId' | while read bp_id; do
    bp_name=$(aws datazone get-environment-blueprint \
        --domain-identifier "$DOMAIN_ID" \
        --identifier "$bp_id" \
        --region "$REGION" \
        --query 'name' \
        --output text 2>/dev/null)
    echo "$bp_name=$bp_id" >> "$BLUEPRINT_MAP_FILE"
done

# Function to get blueprint ID by name
get_bp_id() {
    grep "^$1=" "$BLUEPRINT_MAP_FILE" | cut -d'=' -f2 || echo ""
}

# Map blueprint names to IDs (IAM domain blueprints)
TOOLING_LITE_ID=$(get_bp_id "ToolingLite")
S3_BUCKET_ID=$(get_bp_id "S3Bucket")
S3_TABLE_CATALOG_ID=$(get_bp_id "S3TableCatalog")
LAKEHOUSE_ADMIN_ID=$(get_bp_id "LakehouseAdmin")

echo "Blueprint IDs (IAM Domain):"
echo "  ToolingLite: $TOOLING_LITE_ID"
echo "  S3Bucket: $S3_BUCKET_ID"
echo "  S3TableCatalog: $S3_TABLE_CATALOG_ID"
echo "  LakehouseAdmin: $LAKEHOUSE_ADMIN_ID"
echo ""

# Validate required blueprints
if [ -z "$TOOLING_LITE_ID" ]; then
    echo "❌ Error: Required blueprint (ToolingLite) not found"
    echo "Please enable it in the DataZone domain first"
    exit 1
fi

# Build environment configurations for IAM domain (open projects)
echo "🔧 Building environment configurations for open projects..."
ENV_CONFIGS='[
    {
      "name": "ToolingLite",
      "environmentBlueprintId": "'$TOOLING_LITE_ID'",
      "description": "Lightweight tooling environment for open projects",
      "deploymentOrder": 0,
      "deploymentMode": "ON_CREATE",
      "accountPools": ["'$ACCOUNT_POOL_ID'"],
      "configurationParameters": {
        "parameterOverrides": [
          {
            "name": "s3BucketLocation",
            "value": "",
            "isEditable": true
          }
        ]
      }
    }'

# Add optional blueprints if they exist
if [ -n "$S3_BUCKET_ID" ]; then
  ENV_CONFIGS="$ENV_CONFIGS"',
    {
      "name": "S3Bucket",
      "environmentBlueprintId": "'$S3_BUCKET_ID'",
      "description": "S3 bucket for data storage",
      "deploymentMode": "ON_DEMAND",
      "accountPools": ["'$ACCOUNT_POOL_ID'"],
      "configurationParameters": {
        "parameterOverrides": [
          {
            "name": "bucketName",
            "isEditable": true
          }
        ]
      }
    }'
fi

if [ -n "$S3_TABLE_CATALOG_ID" ]; then
  ENV_CONFIGS="$ENV_CONFIGS"',
    {
      "name": "S3TableCatalog",
      "environmentBlueprintId": "'$S3_TABLE_CATALOG_ID'",
      "description": "S3 table catalog for data discovery",
      "deploymentMode": "ON_DEMAND",
      "accountPools": ["'$ACCOUNT_POOL_ID'"],
      "configurationParameters": {
        "parameterOverrides": [
          {
            "name": "catalogName",
            "value": "",
            "isEditable": true
          },
          {
            "name": "databaseName",
            "value": "",
            "isEditable": true
          }
        ]
      }
    }'
fi

ENV_CONFIGS="$ENV_CONFIGS"']'

# Create profile JSON
PROFILE_JSON=$(mktemp)
cat > "$PROFILE_JSON" <<EOF
{
  "name": "Open Project - Account Pool",
  "description": "Open project profile for IAM-based domains. Uses ToolingLite and account pool for dynamic account assignment.",
  "status": "ENABLED",
  "domainIdentifier": "$DOMAIN_ID",
  "domainUnitIdentifier": "$DOMAIN_UNIT_ID",
  "environmentConfigurations": $ENV_CONFIGS
}
EOF

echo "📦 Creating open project profile..."
PROFILE_RESPONSE=$(aws datazone create-project-profile \
    --cli-input-json file://"$PROFILE_JSON" \
    --region "$REGION" \
    --output json)

rm -f "$PROFILE_JSON"

PROFILE_ID=$(echo "$PROFILE_RESPONSE" | jq -r '.id')
PROFILE_NAME=$(echo "$PROFILE_RESPONSE" | jq -r '.name')

echo ""
echo "✅ Open project profile created successfully!"
echo ""
echo "Profile ID: $PROFILE_ID"
echo "Profile Name: $PROFILE_NAME"
echo ""

# Save profile details
cat > open-project-profile-details.json <<EOF
{
  "profileId": "$PROFILE_ID",
  "profileName": "$PROFILE_NAME",
  "profileType": "open",
  "domainType": "IAM",
  "accountPoolId": "$ACCOUNT_POOL_ID",
  "domainId": "$DOMAIN_ID",
  "domainUnitId": "$DOMAIN_UNIT_ID",
  "createdAt": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

echo "📄 Profile details saved to: open-project-profile-details.json"
echo ""

# Add policy grants
echo "🔐 Adding policy grants..."
echo ""

add_policy_grant() {
    local bp_name=$1
    local bp_id=$2
    
    if [ -z "$bp_id" ]; then
        echo "⊘ Skipping $bp_name (not enabled)"
        return
    fi
    
    echo "Adding policy grant for $bp_name..."
    aws datazone add-policy-grant \
        --domain-identifier "$DOMAIN_ID" \
        --entity-type "EnvironmentBlueprintConfiguration" \
        --entity-identifier "${DOMAIN_ACCOUNT_ID}:${bp_id}" \
        --policy-type "CREATE_ENVIRONMENT_FROM_BLUEPRINT" \
        --principal '{"project":{"projectGrantFilter":{"domainUnitFilter":{"domainUnit":"'$DOMAIN_UNIT_ID'","includeChildDomainUnits":true}},"projectDesignation":"CONTRIBUTOR"}}' \
        --detail '{"createEnvironmentFromBlueprint":{}}' \
        --region "$REGION" \
        --output json > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        echo "✅ Policy grant added for $bp_name"
    else
        echo "⚠️  Policy grant for $bp_name (may already exist)"
    fi
}

# Add grants for all blueprints
add_policy_grant "ToolingLite" "$TOOLING_LITE_ID"
add_policy_grant "S3Bucket" "$S3_BUCKET_ID"
add_policy_grant "S3TableCatalog" "$S3_TABLE_CATALOG_ID"

echo ""
echo "Adding policy grant for Project Profile..."
aws datazone add-policy-grant \
    --domain-identifier "$DOMAIN_ID" \
    --entity-type "DomainUnit" \
    --entity-identifier "$DOMAIN_UNIT_ID" \
    --policy-type "CREATE_PROJECT_FROM_PROJECT_PROFILE" \
    --principal '{"user":{"allUsersGrantFilter":{}}}' \
    --detail '{"createProjectFromProjectProfile":{"includeChildDomainUnits":true,"projectProfiles":["'$PROFILE_ID'"]}}' \
    --region "$REGION" \
    --output json > /dev/null 2>&1

echo "✅ Policy grant added for Project Profile"
echo ""

echo "✅ Open project profile setup complete!"
echo ""
echo "Profile Type: Open (IAM Domain)"
echo "Blueprints: ToolingLite (ON_CREATE), S3Bucket, S3TableCatalog (ON_DEMAND)"
echo ""
echo "Next steps:"
echo "1. Seed the initial pool with accounts: ./seed-initial-pool.sh"
echo "2. Create a test project using this profile"
echo "3. Verify account assignment from pool"
echo ""

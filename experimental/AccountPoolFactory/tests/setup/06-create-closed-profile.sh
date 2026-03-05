#!/bin/bash
set -e

# Create Closed Project Profile with Account Pool (for IDC-based domains)
# Closed projects use Tooling, DataLake, and full enterprise blueprints

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load configuration
REGION=$(grep "region:" config.yaml | awk '{print $2}')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')
DOMAIN_ID=$(grep "domain_id:" config.yaml | awk '{print $2}')
DOMAIN_UNIT_ID=$(grep "root_domain_unit_id:" config.yaml | awk '{print $2}')

echo "🚀 Creating Closed Project Profile with Account Pool (IDC Domain)"
echo "==============================================================="
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

# Map blueprint names to IDs (IDC domain blueprints - full enterprise)
TOOLING_ID=$(get_bp_id "Tooling")
DATA_LAKE_ID=$(get_bp_id "DataLake")
LAKEHOUSE_CATALOG_ID=$(get_bp_id "LakehouseCatalog")
WORKFLOWS_ID=$(get_bp_id "Workflows")
REDSHIFT_SERVERLESS_ID=$(get_bp_id "RedshiftServerless")
EMR_SERVERLESS_ID=$(get_bp_id "EmrServerless")
ML_EXPERIMENTS_ID=$(get_bp_id "MLflowApp")
EMR_ON_EC2_ID=$(get_bp_id "EmrOnEc2")

echo "Blueprint IDs (IDC Domain):"
echo "  Tooling: $TOOLING_ID"
echo "  DataLake: $DATA_LAKE_ID"
echo "  LakehouseCatalog: $LAKEHOUSE_CATALOG_ID"
echo "  Workflows: $WORKFLOWS_ID"
echo "  RedshiftServerless: $REDSHIFT_SERVERLESS_ID"
echo "  EmrServerless: $EMR_SERVERLESS_ID"
echo "  MLExperiments: $ML_EXPERIMENTS_ID"
echo "  EmrOnEc2: $EMR_ON_EC2_ID"
echo ""

# Validate required blueprints
if [ -z "$TOOLING_ID" ] || [ -z "$DATA_LAKE_ID" ]; then
    echo "❌ Error: Required blueprints (Tooling, DataLake) not found"
    echo "Please enable them in the DataZone domain first"
    exit 1
fi

# Build environment configurations for IDC domain (closed projects)
echo "🔧 Building environment configurations for closed projects..."
ENV_CONFIGS='[
    {
      "name": "Tooling",
      "environmentBlueprintId": "'$TOOLING_ID'",
      "description": "Configuration for the Tooling environment",
      "deploymentOrder": 0,
      "deploymentMode": "ON_CREATE",
      "accountPools": ["'$ACCOUNT_POOL_ID'"],
      "configurationParameters": {
        "parameterOverrides": [
          {
            "name": "enableSpaces",
            "value": "true",
            "isEditable": false
          },
          {
            "name": "enableAmazonBedrockPermissions",
            "value": "true",
            "isEditable": false
          }
        ]
      }
    },
    {
      "name": "Lakehouse Database",
      "environmentBlueprintId": "'$DATA_LAKE_ID'",
      "description": "Creates databases for storing tables in S3 and Athena resources",
      "deploymentOrder": 1,
      "deploymentMode": "ON_CREATE",
      "accountPools": ["'$ACCOUNT_POOL_ID'"],
      "configurationParameters": {
        "parameterOverrides": [
          {
            "name": "glueDbName",
            "value": "marketing_db",
            "isEditable": true
          }
        ]
      }
    }'

# Add optional blueprints if they exist
if [ -n "$LAKEHOUSE_CATALOG_ID" ]; then
  ENV_CONFIGS="$ENV_CONFIGS"',
    {
      "name": "Lakehouse Catalog",
      "environmentBlueprintId": "'$LAKEHOUSE_CATALOG_ID'",
      "description": "Configuration for data cataloging",
      "deploymentOrder": 1,
      "deploymentMode": "ON_CREATE",
      "accountPools": ["'$ACCOUNT_POOL_ID'"]
    }'
fi

if [ -n "$REDSHIFT_SERVERLESS_ID" ]; then
  ENV_CONFIGS="$ENV_CONFIGS"',
    {
      "name": "RedshiftServerless",
      "environmentBlueprintId": "'$REDSHIFT_SERVERLESS_ID'",
      "description": "Creates an Amazon Redshift Serverless workgroup for SQL workloads",
      "deploymentOrder": 1,
      "deploymentMode": "ON_CREATE",
      "accountPools": ["'$ACCOUNT_POOL_ID'"],
      "configurationParameters": {
        "parameterOverrides": [
          {
            "name": "redshiftDbName",
            "value": "dev",
            "isEditable": true
          },
          {
            "name": "connectToRMSCatalog",
            "value": "true",
            "isEditable": false
          },
          {
            "name": "redshiftMaxCapacity",
            "value": "512",
            "isEditable": false
          }
        ]
      }
    }'
fi

if [ -n "$WORKFLOWS_ID" ]; then
  ENV_CONFIGS="$ENV_CONFIGS"',
    {
      "name": "OnDemand Workflows",
      "environmentBlueprintId": "'$WORKFLOWS_ID'",
      "description": "Enables you to create Airflow workflows",
      "deploymentMode": "ON_DEMAND",
      "accountPools": ["'$ACCOUNT_POOL_ID'"],
      "configurationParameters": {
        "parameterOverrides": [
          {
            "name": "environmentClass",
            "value": "mw1.micro",
            "isEditable": false
          }
        ]
      }
    }'
fi

if [ -n "$ML_EXPERIMENTS_ID" ]; then
  ENV_CONFIGS="$ENV_CONFIGS"',
    {
      "name": "OnDemand MLExperiments",
      "environmentBlueprintId": "'$ML_EXPERIMENTS_ID'",
      "description": "Enables you to create Amazon SageMaker MLflow",
      "deploymentMode": "ON_DEMAND",
      "accountPools": ["'$ACCOUNT_POOL_ID'"]
    }'
fi

if [ -n "$EMR_ON_EC2_ID" ]; then
  ENV_CONFIGS="$ENV_CONFIGS"',
    {
      "name": "OnDemand EMR on EC2 Memory-Optimized",
      "environmentBlueprintId": "'$EMR_ON_EC2_ID'",
      "description": "Memory optimized Amazon EMR on EC2",
      "deploymentMode": "ON_DEMAND",
      "accountPools": ["'$ACCOUNT_POOL_ID'"],
      "configurationParameters": {
        "parameterOverrides": [
          {
            "name": "emrRelease",
            "value": "emr-7.5.0",
            "isEditable": true
          },
          {
            "name": "clusterName",
            "value": "emr-ec2-cluster",
            "isEditable": true
          },
          {
            "name": "primaryInstanceType",
            "value": "r6g.xlarge",
            "isEditable": true
          },
          {
            "name": "coreInstanceType",
            "value": "r6g.xlarge",
            "isEditable": true
          }
        ]
      }
    }'
fi

if [ -n "$EMR_SERVERLESS_ID" ]; then
  ENV_CONFIGS="$ENV_CONFIGS"',
    {
      "name": "OnDemand EMRServerless",
      "environmentBlueprintId": "'$EMR_SERVERLESS_ID'",
      "description": "Amazon EMR Serverless for Spark workloads",
      "deploymentMode": "ON_DEMAND",
      "accountPools": ["'$ACCOUNT_POOL_ID'"],
      "configurationParameters": {
        "parameterOverrides": [
          {
            "name": "releaseLabel",
            "value": "emr-7.5.0",
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
  "name": "Closed Project - Account Pool",
  "description": "Closed project profile for IDC-based domains. Uses full enterprise blueprints and account pool for dynamic account assignment.",
  "status": "ENABLED",
  "domainIdentifier": "$DOMAIN_ID",
  "domainUnitIdentifier": "$DOMAIN_UNIT_ID",
  "environmentConfigurations": $ENV_CONFIGS
}
EOF

echo "📦 Creating project profile..."
PROFILE_RESPONSE=$(aws datazone create-project-profile \
    --cli-input-json file://"$PROFILE_JSON" \
    --region "$REGION" \
    --output json)

rm -f "$PROFILE_JSON"

PROFILE_ID=$(echo "$PROFILE_RESPONSE" | jq -r '.id')
PROFILE_NAME=$(echo "$PROFILE_RESPONSE" | jq -r '.name')

echo ""
echo "✅ Closed project profile created successfully!"
echo ""
echo "Profile ID: $PROFILE_ID"
echo "Profile Name: $PROFILE_NAME"
echo ""

# Save profile details
cat > closed-project-profile-details.json <<EOF
{
  "profileId": "$PROFILE_ID",
  "profileName": "$PROFILE_NAME",
  "profileType": "closed",
  "domainType": "IDC",
  "accountPoolId": "$ACCOUNT_POOL_ID",
  "domainId": "$DOMAIN_ID",
  "domainUnitId": "$DOMAIN_UNIT_ID",
  "createdAt": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

echo "📄 Profile details saved to: closed-project-profile-details.json"
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
add_policy_grant "Tooling" "$TOOLING_ID"
add_policy_grant "DataLake" "$DATA_LAKE_ID"
add_policy_grant "LakehouseCatalog" "$LAKEHOUSE_CATALOG_ID"
add_policy_grant "RedshiftServerless" "$REDSHIFT_SERVERLESS_ID"
add_policy_grant "Workflows" "$WORKFLOWS_ID"
add_policy_grant "MLExperiments" "$ML_EXPERIMENTS_ID"
add_policy_grant "EmrOnEc2" "$EMR_ON_EC2_ID"
add_policy_grant "EmrServerless" "$EMR_SERVERLESS_ID"

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

echo "✅ Closed project profile setup complete!"
echo ""
echo "Profile Type: Closed (IDC Domain)"
echo "Blueprints: Tooling, DataLake (ON_CREATE), RedshiftServerless, Workflows, MLExperiments, EmrOnEc2, EmrServerless (ON_DEMAND)"
echo ""
echo "Next steps:"
echo "1. Seed the initial pool with accounts: ./seed-initial-pool.sh"
echo "2. Create a test project using this profile"
echo "3. Verify account assignment from pool"
echo ""

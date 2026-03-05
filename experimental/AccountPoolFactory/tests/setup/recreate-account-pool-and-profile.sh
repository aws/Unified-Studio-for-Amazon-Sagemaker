#!/bin/bash
set -e

# Recreate account pool and profile to ensure proper Lambda integration

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load configuration
CONFIG_FILE="$PROJECT_ROOT/config.yaml"
PROJECT_FILE="$PROJECT_ROOT/test-project-details.json"
POOL_FILE="$PROJECT_ROOT/account-pool-details.json"
PROFILE_FILE="$PROJECT_ROOT/project-profile-details.json"
LAMBDA_FILE="$PROJECT_ROOT/account-provider-lambda-details.json"

# Parse configuration
read -r DOMAIN_ID REGION < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['region'])
EOF
)

# Get Lambda ARNs
LAMBDA_ARN=$(jq -r '.functionArn' "$LAMBDA_FILE")
LAMBDA_ROLE_ARN=$(jq -r '.roleArn' "$LAMBDA_FILE")

echo "=== Step 1: Delete Old Project ==="
if [ -f "$PROJECT_FILE" ]; then
    PROJECT_ID=$(jq -r '.projectId' "$PROJECT_FILE")
    echo "Deleting project: $PROJECT_ID"
    
    aws datazone delete-project \
        --domain-identifier "$DOMAIN_ID" \
        --identifier "$PROJECT_ID" \
        --region "$REGION" || echo "Project already deleted or doesn't exist"
    
    echo "✅ Project deleted"
    rm -f "$PROJECT_FILE"
else
    echo "No project file found, skipping"
fi

echo ""
echo "=== Step 2: Delete Old Project Profile ==="
if [ -f "$PROFILE_FILE" ]; then
    PROFILE_ID=$(jq -r '.profileId' "$PROFILE_FILE")
    echo "Deleting profile: $PROFILE_ID"
    
    aws datazone delete-project-profile \
        --domain-identifier "$DOMAIN_ID" \
        --identifier "$PROFILE_ID" \
        --region "$REGION" || echo "Profile already deleted or doesn't exist"
    
    echo "✅ Profile deleted"
    rm -f "$PROFILE_FILE"
    rm -f "$PROJECT_ROOT/project-profile-full-details.json"
else
    echo "No profile file found, skipping"
fi

echo ""
echo "=== Step 3: Delete Old Account Pool ==="
if [ -f "$POOL_FILE" ]; then
    POOL_ID=$(jq -r '.id' "$POOL_FILE")
    echo "Deleting account pool: $POOL_ID"
    
    aws datazone delete-account-pool \
        --domain-identifier "$DOMAIN_ID" \
        --identifier "$POOL_ID" \
        --region "$REGION" || echo "Pool already deleted or doesn't exist"
    
    echo "✅ Account pool deleted"
    rm -f "$POOL_FILE"
else
    echo "No pool file found, skipping"
fi

echo ""
echo "Waiting 10 seconds for cleanup to complete..."
sleep 10

echo ""
echo "=== Step 4: Create New Account Pool ==="
echo "Lambda ARN: $LAMBDA_ARN"
echo "Lambda Role ARN: $LAMBDA_ROLE_ARN"
echo ""

POOL_RESPONSE=$(aws datazone create-account-pool \
    --domain-identifier "$DOMAIN_ID" \
    --name "AccountPoolFactory-CustomPool-v2" \
    --description "Custom account pool managed by Account Pool Factory (recreated)" \
    --resolution-strategy "MANUAL" \
    --account-source "{
        \"customAccountPoolHandler\": {
            \"lambdaFunctionArn\": \"$LAMBDA_ARN\",
            \"lambdaExecutionRoleArn\": \"$LAMBDA_ROLE_ARN\"
        }
    }" \
    --region "$REGION" \
    --output json)

NEW_POOL_ID=$(echo "$POOL_RESPONSE" | jq -r '.id')
echo "✅ New account pool created: $NEW_POOL_ID"
echo ""

# Save pool details
echo "$POOL_RESPONSE" > "$POOL_FILE"
echo "Pool details saved to: $POOL_FILE"

echo ""
echo "=== Step 5: Create New Project Profile ==="

# Create profile with all 8 blueprints
PROFILE_RESPONSE=$(aws datazone create-project-profile \
    --domain-identifier "$DOMAIN_ID" \
    --name "All capabilities - Account Pool v2" \
    --description "Analyze data and build machine learning models with all capabilities. Uses Account Pool for dynamic account assignment (recreated)." \
    --environment-configurations "[
        {
            \"name\": \"Tooling\",
            \"environmentBlueprintId\": \"3owsbi7jjppvc9\",
            \"description\": \"Configuration for the Tooling environment\",
            \"deploymentMode\": \"ON_CREATE\",
            \"deploymentOrder\": 0,
            \"accountPools\": [\"$NEW_POOL_ID\"],
            \"configurationParameters\": {
                \"parameterOverrides\": [
                    {\"name\": \"enableSpaces\", \"value\": \"true\", \"isEditable\": false},
                    {\"name\": \"enableAmazonBedrockPermissions\", \"value\": \"true\", \"isEditable\": false}
                ]
            }
        },
        {
            \"name\": \"Lakehouse Database\",
            \"environmentBlueprintId\": \"6bbrztdwfxomeh\",
            \"description\": \"Creates databases for storing tables in S3 and Athena resources\",
            \"deploymentMode\": \"ON_CREATE\",
            \"deploymentOrder\": 1,
            \"accountPools\": [\"$NEW_POOL_ID\"],
            \"configurationParameters\": {
                \"parameterOverrides\": [
                    {\"name\": \"glueDbName\", \"value\": \"marketing_db\", \"isEditable\": true}
                ]
            }
        },
        {
            \"name\": \"Lakehouse Catalog\",
            \"environmentBlueprintId\": \"6vtt2ycs570ezt\",
            \"description\": \"Configuration for data cataloging\",
            \"deploymentMode\": \"ON_CREATE\",
            \"deploymentOrder\": 1,
            \"accountPools\": [\"$NEW_POOL_ID\"]
        },
        {
            \"name\": \"RedshiftServerless\",
            \"environmentBlueprintId\": \"5zux18nxyx6pd5\",
            \"description\": \"Creates an Amazon Redshift Serverless workgroup for SQL workloads\",
            \"deploymentMode\": \"ON_CREATE\",
            \"deploymentOrder\": 1,
            \"accountPools\": [\"$NEW_POOL_ID\"],
            \"configurationParameters\": {
                \"parameterOverrides\": [
                    {\"name\": \"redshiftDbName\", \"value\": \"dev\", \"isEditable\": true},
                    {\"name\": \"connectToRMSCatalog\", \"value\": \"true\", \"isEditable\": false},
                    {\"name\": \"redshiftMaxCapacity\", \"value\": \"512\", \"isEditable\": false}
                ]
            }
        },
        {
            \"name\": \"OnDemand Workflows\",
            \"environmentBlueprintId\": \"b0eis75ozsqhd5\",
            \"description\": \"Enables you to create Airflow workflows\",
            \"deploymentMode\": \"ON_DEMAND\",
            \"accountPools\": [\"$NEW_POOL_ID\"],
            \"configurationParameters\": {
                \"parameterOverrides\": [
                    {\"name\": \"environmentClass\", \"value\": \"mw1.micro\", \"isEditable\": false}
                ]
            }
        },
        {
            \"name\": \"OnDemand MLExperiments\",
            \"environmentBlueprintId\": \"6r38ttlmkm3isp\",
            \"description\": \"Enables you to create Amazon SageMaker MLflow\",
            \"deploymentMode\": \"ON_DEMAND\",
            \"accountPools\": [\"$NEW_POOL_ID\"]
        },
        {
            \"name\": \"OnDemand EMR on EC2 Memory-Optimized\",
            \"environmentBlueprintId\": \"atyconez9k8zjd\",
            \"description\": \"Memory optimized Amazon EMR on EC2\",
            \"deploymentMode\": \"ON_DEMAND\",
            \"accountPools\": [\"$NEW_POOL_ID\"],
            \"configurationParameters\": {
                \"parameterOverrides\": [
                    {\"name\": \"emrRelease\", \"value\": \"emr-7.5.0\", \"isEditable\": true},
                    {\"name\": \"clusterName\", \"value\": \"emr-ec2-cluster\", \"isEditable\": true},
                    {\"name\": \"primaryInstanceType\", \"value\": \"r6g.xlarge\", \"isEditable\": true},
                    {\"name\": \"coreInstanceType\", \"value\": \"r6g.xlarge\", \"isEditable\": true}
                ]
            }
        },
        {
            \"name\": \"OnDemand EMRServerless\",
            \"environmentBlueprintId\": \"c1vpqx2w5jxsh5\",
            \"description\": \"Amazon EMR Serverless for Spark workloads\",
            \"deploymentMode\": \"ON_DEMAND\",
            \"accountPools\": [\"$NEW_POOL_ID\"],
            \"configurationParameters\": {
                \"parameterOverrides\": [
                    {\"name\": \"releaseLabel\", \"value\": \"emr-7.5.0\", \"isEditable\": true}
                ]
            }
        }
    ]" \
    --region "$REGION" \
    --output json)

NEW_PROFILE_ID=$(echo "$PROFILE_RESPONSE" | jq -r '.id')
echo "✅ New project profile created: $NEW_PROFILE_ID"
echo ""

# Save profile details
cat > "$PROFILE_FILE" <<EOF
{
  "profileId": "$NEW_PROFILE_ID",
  "profileName": "All capabilities - Account Pool v2",
  "accountPoolId": "$NEW_POOL_ID",
  "domainId": "$DOMAIN_ID",
  "createdAt": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

echo "Profile details saved to: $PROFILE_FILE"

echo ""
echo "=== Step 6: Add Policy Grants ==="

BLUEPRINTS=(
    "3owsbi7jjppvc9:Tooling"
    "6bbrztdwfxomeh:DataLake"
    "6vtt2ycs570ezt:LakehouseCatalog"
    "5zux18nxyx6pd5:RedshiftServerless"
    "b0eis75ozsqhd5:Workflows"
    "6r38ttlmkm3isp:MLExperiments"
    "atyconez9k8zjd:EmrOnEc2"
    "c1vpqx2w5jxsh5:EMRServerless"
)

for BP in "${BLUEPRINTS[@]}"; do
    BP_ID="${BP%%:*}"
    BP_NAME="${BP##*:}"
    
    echo "Adding policy grant for $BP_NAME..."
    aws datazone add-policy-grant \
        --domain-identifier "$DOMAIN_ID" \
        --entity-type "ENVIRONMENT_BLUEPRINT_CONFIGURATION" \
        --entity-identifier "$BP_ID" \
        --principal "{\"project\":{\"projectDesignation\":\"OWNER\",\"projectIdentifier\":\"$NEW_PROFILE_ID\"}}" \
        --policy-type "CREATE_ENVIRONMENT_PROFILE" \
        --region "$REGION" \
        --output json > /dev/null || echo "  (grant may already exist)"
done

echo "✅ Policy grants added"

echo ""
echo "=== Summary ==="
echo "New Account Pool ID: $NEW_POOL_ID"
echo "New Profile ID: $NEW_PROFILE_ID"
echo ""
echo "=== Next Steps ==="
echo "1. Create a new project using the new profile"
echo "2. Add analyst1-amirbo as project member"
echo "3. Try creating an environment through the portal"
echo "4. Check Lambda logs for invocation"
echo ""
echo "To create project:"
echo "  ./tests/setup/scripts/create-test-project.sh"

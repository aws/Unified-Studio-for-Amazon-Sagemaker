#!/bin/bash
set -e

# Update profile to have only Tooling as ON_CREATE, rest as ON_DEMAND

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load configuration
CONFIG_FILE="$PROJECT_ROOT/config.yaml"
PROFILE_FILE="$PROJECT_ROOT/project-profile-details.json"

# Parse configuration
read -r DOMAIN_ID REGION < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['region'])
EOF
)

PROFILE_ID=$(jq -r '.profileId' "$PROFILE_FILE")
POOL_ID=$(jq -r '.accountPoolId' "$PROFILE_FILE")

echo "=== Updating Project Profile Deployment Modes ==="
echo "Profile ID: $PROFILE_ID"
echo "Account Pool ID: $POOL_ID"
echo ""
echo "Changes:"
echo "  - Tooling: ON_CREATE (unchanged)"
echo "  - Lakehouse Database: ON_CREATE → ON_DEMAND"
echo "  - Lakehouse Catalog: ON_CREATE → ON_DEMAND"
echo "  - RedshiftServerless: ON_CREATE → ON_DEMAND"
echo "  - All others: ON_DEMAND (unchanged)"
echo ""

# Update profile with new deployment modes
PROFILE_RESPONSE=$(aws datazone update-project-profile \
    --domain-identifier "$DOMAIN_ID" \
    --identifier "$PROFILE_ID" \
    --environment-configurations "[
        {
            \"name\": \"Tooling\",
            \"environmentBlueprintId\": \"3owsbi7jjppvc9\",
            \"description\": \"Configuration for the Tooling environment\",
            \"deploymentMode\": \"ON_CREATE\",
            \"deploymentOrder\": 0,
            \"accountPools\": [\"$POOL_ID\"],
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
            \"deploymentMode\": \"ON_DEMAND\",
            \"accountPools\": [\"$POOL_ID\"],
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
            \"deploymentMode\": \"ON_DEMAND\",
            \"accountPools\": [\"$POOL_ID\"]
        },
        {
            \"name\": \"RedshiftServerless\",
            \"environmentBlueprintId\": \"5zux18nxyx6pd5\",
            \"description\": \"Creates an Amazon Redshift Serverless workgroup for SQL workloads\",
            \"deploymentMode\": \"ON_DEMAND\",
            \"accountPools\": [\"$POOL_ID\"],
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
            \"accountPools\": [\"$POOL_ID\"],
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
            \"accountPools\": [\"$POOL_ID\"]
        },
        {
            \"name\": \"OnDemand EMR on EC2 Memory-Optimized\",
            \"environmentBlueprintId\": \"atyconez9k8zjd\",
            \"description\": \"Memory optimized Amazon EMR on EC2\",
            \"deploymentMode\": \"ON_DEMAND\",
            \"accountPools\": [\"$POOL_ID\"],
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
            \"accountPools\": [\"$POOL_ID\"],
            \"configurationParameters\": {
                \"parameterOverrides\": [
                    {\"name\": \"releaseLabel\", \"value\": \"emr-7.5.0\", \"isEditable\": true}
                ]
            }
        }
    ]" \
    --region "$REGION" \
    --output json)

echo "✅ Profile updated successfully!"
echo ""

# Save updated profile
echo "$PROFILE_RESPONSE" > "$PROJECT_ROOT/project-profile-full-details.json"
echo "Full profile details saved to: project-profile-full-details.json"

echo ""
echo "=== Updated Deployment Modes ==="
echo "$PROFILE_RESPONSE" | jq -r '.environmentConfigurations[] | "  - \(.name): \(.deploymentMode)"'

echo ""
echo "=== Next Steps ==="
echo "1. Delete the current test project"
echo "2. Create a new project with the updated profile"
echo "3. Check if Tooling environment is created automatically"
echo "4. Verify Lambda is invoked"
echo ""
echo "To delete current project:"
echo "  aws datazone delete-project --domain-identifier $DOMAIN_ID --identifier \$(jq -r '.projectId' $PROJECT_ROOT/test-project-details.json) --region $REGION"

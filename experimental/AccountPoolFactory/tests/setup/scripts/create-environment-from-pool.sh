#!/bin/bash
set -e

# Create an environment in the test project to trigger the account pool Lambda

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load configuration
CONFIG_FILE="$PROJECT_ROOT/config.yaml"
PROJECT_FILE="$PROJECT_ROOT/test-project-details.json"

if [ ! -f "$PROJECT_FILE" ]; then
    echo "Error: Project details not found: $PROJECT_FILE"
    echo "Run create-test-project.sh first"
    exit 1
fi

# Parse configuration
read -r DOMAIN_ID REGION < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['region'])
EOF
)

PROJECT_ID=$(jq -r '.projectId' "$PROJECT_FILE")
PROJECT_NAME=$(jq -r '.projectName' "$PROJECT_FILE")

# Get available blueprints for the project
echo "=== Getting Available Blueprints ==="
echo "Domain ID: $DOMAIN_ID"
echo "Project ID: $PROJECT_ID"
echo ""

BLUEPRINTS=$(aws datazone list-environment-blueprints \
    --domain-identifier "$DOMAIN_ID" \
    --managed \
    --region "$REGION" \
    --output json)

echo "Available blueprints:"
echo "$BLUEPRINTS" | jq -r '.items[] | "  - \(.name) (\(.id))"'
echo ""

# Use DataLake blueprint which is in our project profile
BLUEPRINT_ID="6bbrztdwfxomeh"
BLUEPRINT_NAME="DataLake"

# Verify it exists
if ! echo "$BLUEPRINTS" | jq -e ".items[] | select(.id == \"$BLUEPRINT_ID\")" > /dev/null; then
    echo "❌ DataLake blueprint not found in domain"
    exit 1
fi

echo "Using blueprint: $BLUEPRINT_NAME ($BLUEPRINT_ID)"
echo ""

# Generate unique environment name
TIMESTAMP=$(date +%s)
ENV_NAME="test-env-pool-$TIMESTAMP"

echo "=== Creating Environment ==="
echo "Environment Name: $ENV_NAME"
echo "Blueprint: $BLUEPRINT_NAME"
echo ""
echo "⚠️  This should trigger the Account Provider Lambda!"
echo ""

# Create environment
# Note: We don't specify awsAccount or awsRegion - they come from the account pool
ENV_RESPONSE=$(aws datazone create-environment \
    --domain-identifier "$DOMAIN_ID" \
    --project-identifier "$PROJECT_ID" \
    --name "$ENV_NAME" \
    --description "Test environment to verify account pool Lambda invocation" \
    --environment-blueprint-identifier "$BLUEPRINT_ID" \
    --region "$REGION" \
    --output json)

ENV_ID=$(echo "$ENV_RESPONSE" | jq -r '.id')
ENV_STATUS=$(echo "$ENV_RESPONSE" | jq -r '.status')

echo "✅ Environment creation initiated!"
echo "Environment ID: $ENV_ID"
echo "Initial Status: $ENV_STATUS"
echo ""

# Save environment details
ENV_FILE="$PROJECT_ROOT/test-environment-details.json"
cat > "$ENV_FILE" <<EOF
{
  "environmentId": "$ENV_ID",
  "environmentName": "$ENV_NAME",
  "projectId": "$PROJECT_ID",
  "blueprintId": "$BLUEPRINT_ID",
  "blueprintName": "$BLUEPRINT_NAME",
  "domainId": "$DOMAIN_ID",
  "status": "$ENV_STATUS",
  "createdAt": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

echo "Environment details saved to: $ENV_FILE"
echo ""

# Wait a moment for Lambda to be invoked
echo "Waiting 10 seconds for Lambda invocation..."
sleep 10

echo ""
echo "=== Checking Lambda Logs ==="
LOG_GROUP="/aws/lambda/AccountProvider-$DOMAIN_ID"

echo "Recent Lambda logs:"
aws logs tail "$LOG_GROUP" \
    --since 2m \
    --format short \
    --region "$REGION" 2>/dev/null || echo "No recent logs found"

echo ""
echo "=== Monitoring Environment Status ==="
echo "Waiting for environment to be provisioned..."
MAX_ATTEMPTS=60
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    ENV_DETAILS=$(aws datazone get-environment \
        --domain-identifier "$DOMAIN_ID" \
        --identifier "$ENV_ID" \
        --region "$REGION" \
        --output json)
    
    CURRENT_STATUS=$(echo "$ENV_DETAILS" | jq -r '.status')
    AWS_ACCOUNT=$(echo "$ENV_DETAILS" | jq -r '.awsAccountId // "pending"')
    AWS_REGION=$(echo "$ENV_DETAILS" | jq -r '.awsAccountRegion // "pending"')
    
    echo "  Attempt $((ATTEMPT+1))/$MAX_ATTEMPTS: Status = $CURRENT_STATUS, Account = $AWS_ACCOUNT, Region = $AWS_REGION"
    
    if [ "$CURRENT_STATUS" = "ACTIVE" ]; then
        echo ""
        echo "✅ Environment is ACTIVE!"
        echo ""
        echo "=== Environment Details ==="
        echo "$ENV_DETAILS" | jq '{
            id,
            name,
            status,
            awsAccountId,
            awsAccountRegion,
            environmentBlueprintId,
            projectId
        }'
        
        # Verify account assignment
        EXPECTED_ACCOUNT="004878717744"
        if [ "$AWS_ACCOUNT" = "$EXPECTED_ACCOUNT" ]; then
            echo ""
            echo "✅ Account assignment VERIFIED!"
            echo "   Expected: $EXPECTED_ACCOUNT"
            echo "   Assigned: $AWS_ACCOUNT"
            echo ""
            echo "🎉 Lambda successfully provided account from pool!"
        else
            echo ""
            echo "⚠️  Account mismatch!"
            echo "   Expected: $EXPECTED_ACCOUNT"
            echo "   Assigned: $AWS_ACCOUNT"
        fi
        
        break
    elif [ "$CURRENT_STATUS" = "CREATE_FAILED" ] || [ "$CURRENT_STATUS" = "FAILED" ]; then
        echo ""
        echo "❌ Environment creation FAILED!"
        echo ""
        echo "Full details:"
        echo "$ENV_DETAILS" | jq '.'
        exit 1
    fi
    
    ATTEMPT=$((ATTEMPT+1))
    sleep 10
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo ""
    echo "⚠️  Timeout waiting for environment to become ACTIVE"
    echo "Current status: $CURRENT_STATUS"
    echo ""
    echo "Check environment details:"
    echo "  aws datazone get-environment --domain-identifier $DOMAIN_ID --identifier $ENV_ID --region $REGION"
fi

echo ""
echo "=== Final Lambda Log Check ==="
aws logs tail "$LOG_GROUP" \
    --since 5m \
    --format short \
    --region "$REGION" 2>/dev/null || echo "No logs found"

echo ""
echo "=== Summary ==="
echo "Environment ID: $ENV_ID"
echo "Environment Name: $ENV_NAME"
echo "Project ID: $PROJECT_ID"
echo "Blueprint: $BLUEPRINT_NAME"
echo ""
echo "To view environment details:"
echo "  aws datazone get-environment --domain-identifier $DOMAIN_ID --identifier $ENV_ID --region $REGION"
echo ""
echo "To view Lambda logs:"
echo "  aws logs tail $LOG_GROUP --follow --region $REGION"
echo ""
echo "To delete environment:"
echo "  aws datazone delete-environment --domain-identifier $DOMAIN_ID --identifier $ENV_ID --region $REGION"

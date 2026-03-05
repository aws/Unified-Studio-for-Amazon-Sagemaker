#!/bin/bash
set -e

# Complete test: Create project as domain admin, create environment, verify Lambda invocation

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load configuration
CONFIG_FILE="$PROJECT_ROOT/config.yaml"
PROFILE_FILE="$PROJECT_ROOT/project-profile-details.json"

if [ ! -f "$PROFILE_FILE" ]; then
    echo "Error: Project profile details not found: $PROFILE_FILE"
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

PROFILE_ID=$(jq -r '.profileId' "$PROFILE_FILE")

# Generate unique names
TIMESTAMP=$(date +%s)
PROJECT_NAME="lambda-test-$TIMESTAMP"
ENV_NAME="test-env-$TIMESTAMP"

echo "=== Step 1: Create Test Project (as domain admin) ==="
echo "Domain ID: $DOMAIN_ID"
echo "Profile ID: $PROFILE_ID"
echo "Project Name: $PROJECT_NAME"
echo ""

# Create project without specifying owner (will use current user)
PROJECT_RESPONSE=$(aws datazone create-project \
    --domain-identifier "$DOMAIN_ID" \
    --name "$PROJECT_NAME" \
    --description "Test project for Lambda verification" \
    --project-profile-id "$PROFILE_ID" \
    --region "$REGION" \
    --output json)

PROJECT_ID=$(echo "$PROJECT_RESPONSE" | jq -r '.id')
echo "✅ Project created: $PROJECT_ID"
echo ""

# Wait for project to be active
echo "Waiting for project to become ACTIVE..."
MAX_ATTEMPTS=30
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    PROJECT_STATUS=$(aws datazone get-project \
        --domain-identifier "$DOMAIN_ID" \
        --identifier "$PROJECT_ID" \
        --region "$REGION" \
        --query 'projectStatus' \
        --output text)
    
    if [ "$PROJECT_STATUS" = "ACTIVE" ]; then
        echo "✅ Project is ACTIVE"
        break
    fi
    
    ATTEMPT=$((ATTEMPT+1))
    sleep 5
done

echo ""
echo "=== Step 2: Create Environment (should trigger Lambda) ==="
echo "Environment Name: $ENV_NAME"
echo "Blueprint: DataLake (6bbrztdwfxomeh)"
echo ""

# Create environment - this should trigger the account pool Lambda
ENV_RESPONSE=$(aws datazone create-environment \
    --domain-identifier "$DOMAIN_ID" \
    --project-identifier "$PROJECT_ID" \
    --name "$ENV_NAME" \
    --description "Test environment to verify Lambda invocation" \
    --environment-blueprint-identifier "6bbrztdwfxomeh" \
    --user-parameters '[{"name":"glueDbName","value":"test_db"}]' \
    --region "$REGION" \
    --output json)

ENV_ID=$(echo "$ENV_RESPONSE" | jq -r '.id')
ENV_STATUS=$(echo "$ENV_RESPONSE" | jq -r '.status')

echo "✅ Environment creation initiated!"
echo "Environment ID: $ENV_ID"
echo "Initial Status: $ENV_STATUS"
echo ""

# Wait for Lambda to be invoked
echo "Waiting 15 seconds for Lambda invocation..."
sleep 15

echo ""
echo "=== Step 3: Check Lambda Logs ==="
LOG_GROUP="/aws/lambda/AccountProvider-$DOMAIN_ID"

echo "Checking for recent Lambda invocations..."
RECENT_LOGS=$(aws logs tail "$LOG_GROUP" \
    --since 2m \
    --format short \
    --region "$REGION" 2>/dev/null || echo "")

if echo "$RECENT_LOGS" | grep -q "Account Provider Lambda INVOKED"; then
    echo "🎉 SUCCESS! Lambda was invoked by DataZone!"
    echo ""
    echo "Lambda logs:"
    echo "$RECENT_LOGS"
else
    echo "⚠️  Lambda not invoked yet or no logs found"
    echo ""
    echo "Recent logs:"
    echo "$RECENT_LOGS"
fi

echo ""
echo "=== Step 4: Monitor Environment Status ==="
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
    
    echo "  Attempt $((ATTEMPT+1))/$MAX_ATTEMPTS: Status=$CURRENT_STATUS, Account=$AWS_ACCOUNT, Region=$AWS_REGION"
    
    if [ "$CURRENT_STATUS" = "ACTIVE" ]; then
        echo ""
        echo "✅ Environment is ACTIVE!"
        echo ""
        
        # Verify account assignment
        EXPECTED_ACCOUNT="004878717744"
        if [ "$AWS_ACCOUNT" = "$EXPECTED_ACCOUNT" ]; then
            echo "🎉 SUCCESS! Account assignment verified!"
            echo "   Expected: $EXPECTED_ACCOUNT"
            echo "   Assigned: $AWS_ACCOUNT"
            echo ""
            echo "✅ Lambda successfully provided account from pool!"
        else
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
        break
    fi
    
    ATTEMPT=$((ATTEMPT+1))
    sleep 10
done

echo ""
echo "=== Final Lambda Log Check ==="
aws logs tail "$LOG_GROUP" \
    --since 5m \
    --format short \
    --region "$REGION" 2>/dev/null | grep -A 20 "Account Provider Lambda INVOKED" || echo "No Lambda invocation logs found"

echo ""
echo "=== Summary ==="
echo "Project ID: $PROJECT_ID"
echo "Environment ID: $ENV_ID"
echo "Environment Status: $CURRENT_STATUS"
echo ""
echo "To view full Lambda logs:"
echo "  aws logs tail $LOG_GROUP --follow --region $REGION"
echo ""
echo "To cleanup:"
echo "  aws datazone delete-environment --domain-identifier $DOMAIN_ID --identifier $ENV_ID --region $REGION"
echo "  aws datazone delete-project --domain-identifier $DOMAIN_ID --identifier $PROJECT_ID --region $REGION"

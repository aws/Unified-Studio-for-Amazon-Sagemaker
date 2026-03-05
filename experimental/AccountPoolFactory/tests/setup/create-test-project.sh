#!/bin/bash
set -e

# Create a test DataZone project using the account pool profile

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load files
CONFIG_FILE="$PROJECT_ROOT/config.yaml"
PROFILE_FILE="$PROJECT_ROOT/project-profile-details.json"

if [ ! -f "$PROFILE_FILE" ]; then
    echo "Error: Project profile details not found: $PROFILE_FILE"
    exit 1
fi

# Parse configuration
read -r DOMAIN_ID REGION DEFAULT_OWNER < <(python3 - <<EOF
import yaml
import os
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
default_owner = os.environ.get('PROJECT_OWNER', 'analyst1-amirbo')
print(config['datazone']['domain_id'], config['aws']['region'], default_owner)
EOF
)

PROFILE_ID=$(jq -r '.profileId' "$PROFILE_FILE")
PROFILE_NAME=$(jq -r '.profileName' "$PROFILE_FILE")

# Allow override via environment variable or parameter
PROJECT_OWNER="${1:-$DEFAULT_OWNER}"

# Generate unique project name
TIMESTAMP=$(date +%s)
PROJECT_NAME="test-project-pool-$TIMESTAMP"

echo "=== Creating DataZone Test Project ==="
echo "Domain ID: $DOMAIN_ID"
echo "Profile ID: $PROFILE_ID"
echo "Profile Name: $PROFILE_NAME"
echo "Project Name: $PROJECT_NAME"
echo "Project Owner: $PROJECT_OWNER"
echo "Region: $REGION"
echo ""

# Create project (without userParameters - that's for environments, not projects)
echo "Creating project..."
PROJECT_RESPONSE=$(aws datazone create-project \
    --domain-identifier "$DOMAIN_ID" \
    --name "$PROJECT_NAME" \
    --description "Test project to verify account pool integration" \
    --project-profile-id "$PROFILE_ID" \
    --region "$REGION" \
    --output json)

PROJECT_ID=$(echo "$PROJECT_RESPONSE" | jq -r '.id')
PROJECT_STATUS=$(echo "$PROJECT_RESPONSE" | jq -r '.projectStatus')

echo "✅ Project created!"
echo "Project ID: $PROJECT_ID"
echo "Project Status: $PROJECT_STATUS"
echo ""

# Save project details
PROJECT_FILE="$PROJECT_ROOT/test-project-details.json"
cat > "$PROJECT_FILE" <<EOF
{
  "projectId": "$PROJECT_ID",
  "projectName": "$PROJECT_NAME",
  "profileId": "$PROFILE_ID",
  "domainId": "$DOMAIN_ID",
  "status": "$PROJECT_STATUS",
  "createdAt": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

echo "Project details saved to: $PROJECT_FILE"
echo ""

# Wait for project to be active
echo "Waiting for project to become ACTIVE..."
MAX_ATTEMPTS=30
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    CURRENT_STATUS=$(aws datazone get-project \
        --domain-identifier "$DOMAIN_ID" \
        --identifier "$PROJECT_ID" \
        --region "$REGION" \
        --query 'projectStatus' \
        --output text)
    
    echo "  Attempt $((ATTEMPT+1))/$MAX_ATTEMPTS: Status = $CURRENT_STATUS"
    
    if [ "$CURRENT_STATUS" = "ACTIVE" ]; then
        echo ""
        echo "✅ Project is ACTIVE!"
        break
    elif [ "$CURRENT_STATUS" = "CREATE_FAILED" ]; then
        echo ""
        echo "❌ Project creation FAILED!"
        
        # Get failure reason
        aws datazone get-project \
            --domain-identifier "$DOMAIN_ID" \
            --identifier "$PROJECT_ID" \
            --region "$REGION" \
            --output json | jq '{id, name, projectStatus, failureReasons}'
        
        exit 1
    fi
    
    ATTEMPT=$((ATTEMPT+1))
    sleep 10
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo ""
    echo "⚠️  Timeout waiting for project to become ACTIVE"
    echo "Current status: $CURRENT_STATUS"
    exit 1
fi

echo ""
echo "=== Checking Project Environments ==="

# List environments for the project
ENVIRONMENTS=$(aws datazone list-environments \
    --domain-identifier "$DOMAIN_ID" \
    --project-identifier "$PROJECT_ID" \
    --region "$REGION" \
    --output json)

ENV_COUNT=$(echo "$ENVIRONMENTS" | jq '.items | length')
echo "Number of environments: $ENV_COUNT"
echo ""

if [ "$ENV_COUNT" -gt 0 ]; then
    echo "Environment Details:"
    echo "$ENVIRONMENTS" | jq -r '.items[] | "  - \(.name): \(.status) (Account: \(.awsAccountId // "pending"), Region: \(.awsAccountRegion // "pending"))"'
    echo ""
    
    # Check if any environment has the expected account
    EXPECTED_ACCOUNT="004878717744"
    ASSIGNED_ACCOUNT=$(echo "$ENVIRONMENTS" | jq -r '.items[0].awsAccountId // empty')
    
    if [ "$ASSIGNED_ACCOUNT" = "$EXPECTED_ACCOUNT" ]; then
        echo "✅ Account assignment verified!"
        echo "   Expected: $EXPECTED_ACCOUNT"
        echo "   Assigned: $ASSIGNED_ACCOUNT"
    elif [ -n "$ASSIGNED_ACCOUNT" ]; then
        echo "⚠️  Account mismatch!"
        echo "   Expected: $EXPECTED_ACCOUNT"
        echo "   Assigned: $ASSIGNED_ACCOUNT"
    else
        echo "⏳ Account assignment pending..."
    fi
else
    echo "⚠️  No environments created yet"
fi

echo ""
echo "=== Checking Lambda Logs ==="
echo "Fetching recent Lambda invocations..."

LOG_GROUP="/aws/lambda/AccountProvider-$DOMAIN_ID"

# Get recent log events
aws logs tail "$LOG_GROUP" \
    --since 5m \
    --format short \
    --region "$REGION" 2>/dev/null || echo "No recent logs found"

echo ""
echo "=== Summary ==="
echo "Project ID: $PROJECT_ID"
echo "Project Name: $PROJECT_NAME"
echo "Project Status: ACTIVE"
echo "Environments: $ENV_COUNT"
echo ""
echo "To view full project details:"
echo "  aws datazone get-project --domain-identifier $DOMAIN_ID --identifier $PROJECT_ID --region $REGION"
echo ""
echo "To view Lambda logs:"
echo "  aws logs tail $LOG_GROUP --follow --region $REGION"
echo ""
echo "To delete project:"
echo "  aws datazone delete-project --domain-identifier $DOMAIN_ID --identifier $PROJECT_ID --region $REGION"

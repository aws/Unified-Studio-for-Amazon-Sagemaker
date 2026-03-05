#!/bin/bash
set -e

# Check project members and their designations

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load configuration
CONFIG_FILE="$PROJECT_ROOT/config.yaml"
PROJECT_FILE="$PROJECT_ROOT/test-project-details.json"

if [ ! -f "$PROJECT_FILE" ]; then
    echo "Error: Project details not found: $PROJECT_FILE"
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

echo "=== Project Information ==="
echo "Project ID: $PROJECT_ID"
echo "Project Name: $PROJECT_NAME"
echo "Domain ID: $DOMAIN_ID"
echo ""

# Get project details
echo "=== Project Details ==="
PROJECT_DETAILS=$(aws datazone get-project \
    --domain-identifier "$DOMAIN_ID" \
    --identifier "$PROJECT_ID" \
    --region "$REGION" \
    --output json)

echo "$PROJECT_DETAILS" | jq '{
    id,
    name,
    projectStatus,
    createdBy,
    createdAt,
    lastUpdatedAt,
    domainId
}'

echo ""
echo "=== Project Members ==="

# List project memberships
MEMBERSHIPS=$(aws datazone list-project-memberships \
    --domain-identifier "$DOMAIN_ID" \
    --project-identifier "$PROJECT_ID" \
    --region "$REGION" \
    --output json)

MEMBER_COUNT=$(echo "$MEMBERSHIPS" | jq '.members | length')
echo "Total members: $MEMBER_COUNT"
echo ""

if [ "$MEMBER_COUNT" -gt 0 ]; then
    echo "Member details:"
    echo "$MEMBERSHIPS" | jq -r '.members[] | "
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Member Type: \(.memberDetails.type // "N/A")
User ID: \(.memberDetails.user.userId // "N/A")
User Type: \(.memberDetails.user.userType // "N/A")
Designation: \(.designation)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"'
    
    echo ""
    echo "=== Member Summary ==="
    echo "$MEMBERSHIPS" | jq -r '.members[] | "\(.designation): \(.memberDetails.user.userId // .memberDetails.group.groupId // "unknown")"'
else
    echo "⚠️  No members found in project"
fi

echo ""
echo "=== Checking Project Owner ==="
CREATED_BY=$(echo "$PROJECT_DETAILS" | jq -r '.createdBy')
echo "Created by user ID: $CREATED_BY"

# Try to get user details (may not work with IAM credentials)
echo ""
echo "Note: To see full user details (names, emails), you need DataZone SSO user credentials"
echo "Current IAM role may only see user IDs"

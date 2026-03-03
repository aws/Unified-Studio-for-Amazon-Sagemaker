#!/bin/bash
set -e

# Add SSO user as project member

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

# SSO user details from our verification
SSO_USER_ID="9a6721e929-dbb21836-b076-43bb-8239-6a4c0c814535"
SSO_USERNAME="analyst1-amirbo"

echo "=== Adding SSO User to Project ==="
echo "Domain ID: $DOMAIN_ID"
echo "Project ID: $PROJECT_ID"
echo "Project Name: $PROJECT_NAME"
echo "SSO User ID: $SSO_USER_ID"
echo "SSO Username: $SSO_USERNAME"
echo ""

# Add user as project contributor
echo "Adding user as PROJECT_CONTRIBUTOR..."
ADD_RESULT=$(aws datazone create-project-membership \
    --domain-identifier "$DOMAIN_ID" \
    --project-identifier "$PROJECT_ID" \
    --designation "PROJECT_CONTRIBUTOR" \
    --member "{\"userIdentifier\":\"$SSO_USER_ID\"}" \
    --region "$REGION" \
    --output json 2>&1)

if echo "$ADD_RESULT" | grep -q "error"; then
    echo "❌ Failed to add user:"
    echo "$ADD_RESULT"
    exit 1
else
    echo "✅ User added successfully!"
    echo "$ADD_RESULT" | jq '{designation, memberDetails}'
fi

echo ""
echo "=== Verifying Project Members ==="

# List all project members
MEMBERSHIPS=$(aws datazone list-project-memberships \
    --domain-identifier "$DOMAIN_ID" \
    --project-identifier "$PROJECT_ID" \
    --region "$REGION" \
    --output json)

MEMBER_COUNT=$(echo "$MEMBERSHIPS" | jq '.members | length')
echo "Total members: $MEMBER_COUNT"
echo ""

echo "All members:"
echo "$MEMBERSHIPS" | jq -r '.members[] | "
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Designation: \(.designation)
User Type: \(.memberDetails.type // "N/A")
User ID: \(.memberDetails.user.userId // .memberDetails.iam.principalId // "N/A")
Details: \(.memberDetails.user.username // .memberDetails.iam.arn // "N/A")
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"'

echo ""
echo "✅ SSO user $SSO_USERNAME is now a member of the project!"
echo ""
echo "Next steps:"
echo "1. The SSO user can now create environments in this project"
echo "2. Use SSO credentials (not IAM role) to create environment"
echo "3. Creating environment should trigger the Account Provider Lambda"

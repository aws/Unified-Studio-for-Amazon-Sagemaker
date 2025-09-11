#!/bin/bash

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${1:-$SCRIPT_DIR/config.yaml}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.yaml not found at $CONFIG_FILE"
    exit 1
fi

# Parse config
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(yq '.regions.primary.name' "$CONFIG_FILE")
DOMAIN_STACK_NAME=$(yq '.stacks.domain' "$CONFIG_FILE")
ADMIN_USERNAME=$(yq '.users.admin_username' "$CONFIG_FILE")

# Get owners array from config
OWNERS_JSON=$(yq '.users.owners' "$CONFIG_FILE" -o json)

echo "Deploying DataZone Project Memberships..."
echo "Account ID: $ACCOUNT_ID"
echo "Region: $REGION"
echo "Domain Stack: $DOMAIN_STACK_NAME"
echo "Admin Username: $ADMIN_USERNAME"
echo "Project Owners: $OWNERS_JSON"

# Get Domain ID from CloudFormation stack
echo ""
echo "=== Getting Domain ID from CloudFormation ===="
DOMAIN_ID=$(aws cloudformation describe-stacks \
  --stack-name "$DOMAIN_STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`DomainId`].OutputValue' \
  --output text \
  --region "$REGION")

if [ -z "$DOMAIN_ID" ] || [ "$DOMAIN_ID" = "None" ]; then
    echo "❌ Failed to get Domain ID from stack $DOMAIN_STACK_NAME"
    exit 1
fi

echo "✅ Domain ID: $DOMAIN_ID"

# Function to add project membership using DataZone API
add_project_membership() {
    local project_name=$1
    local owner_identifier=$2
    local designation=${3:-"PROJECT_CONTRIBUTOR"}
    
    # Get project ID by name
    PROJECT_ID=$(aws datazone list-projects \
        --domain-identifier "$DOMAIN_ID" \
        --region "$REGION" \
        --query "items[?name=='$project_name'].id" \
        --output text)
    
    if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "None" ]; then
        echo "⚠️  Project '$project_name' not found, skipping membership"
        return 0
    fi
    
    echo "Project '$project_name' ID: $PROJECT_ID"
    
    # Check if it's an IAM role ARN or user identifier
    if [[ "$owner_identifier" == arn:aws:iam::* ]]; then
        # IAM Role - extract role name
        ROLE_NAME=$(echo "$owner_identifier" | sed 's/.*role\///')
        echo "Adding IAM role membership: $ROLE_NAME"
        
        # Create project membership for IAM role
        aws datazone create-project-membership \
            --domain-identifier "$DOMAIN_ID" \
            --project-identifier "$PROJECT_ID" \
            --member "{\"groupIdentifier\":\"$ROLE_NAME\"}" \
            --designation "$designation" \
            --region "$REGION" 2>/dev/null || echo "  (Role may already be a member)"
    else
        # User identifier
        echo "Adding user membership: $owner_identifier"
        
        # Get user profile ID
        USER_PROFILE_ID=$(aws datazone get-user-profile \
            --domain-identifier "$DOMAIN_ID" \
            --user-identifier "$owner_identifier" \
            --region "$REGION" \
            --query 'id' \
            --output text 2>/dev/null)
        
        if [ -n "$USER_PROFILE_ID" ] && [ "$USER_PROFILE_ID" != "None" ]; then
            # Create project membership for user
            aws datazone create-project-membership \
                --domain-identifier "$DOMAIN_ID" \
                --project-identifier "$PROJECT_ID" \
                --member "{\"userIdentifier\":\"$USER_PROFILE_ID\"}" \
                --designation "$designation" \
                --region "$REGION" 2>/dev/null || echo "  (User may already be a member)"
        else
            echo "  ⚠️  User profile not found for: $owner_identifier"
        fi
    fi
}

echo ""
echo "=== Adding Project Memberships using DataZone API ==="

# Parse owners from JSON and add memberships to dev project
echo "$OWNERS_JSON" | jq -r '.[]' | while read -r owner; do
    echo "Adding owner: $owner"
    add_project_membership "dev-marketing" "$owner" "PROJECT_CONTRIBUTOR"
done

echo ""
echo "✅ Project memberships deployment complete!"
echo "All configured owners have been added to the dev-marketing project."

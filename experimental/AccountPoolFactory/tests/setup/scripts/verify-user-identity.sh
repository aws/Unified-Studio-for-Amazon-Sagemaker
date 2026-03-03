#!/bin/bash
set -e

# Verify the user identity by checking user profiles in DataZone

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load configuration
CONFIG_FILE="$PROJECT_ROOT/config.yaml"

read -r DOMAIN_ID REGION < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['region'])
EOF
)

USER_ID="4b89ed84-9842-45dd-a2e5-15e49eda2b03"

echo "=== Verifying User Identity ==="
echo "Domain ID: $DOMAIN_ID"
echo "User ID: $USER_ID"
echo ""

# Get user profile details
echo "=== User Profile Details ==="
USER_PROFILE=$(aws datazone get-user-profile \
    --domain-identifier "$DOMAIN_ID" \
    --user-identifier "$USER_ID" \
    --region "$REGION" \
    --output json 2>&1)

if echo "$USER_PROFILE" | grep -q "error"; then
    echo "❌ Failed to get user profile:"
    echo "$USER_PROFILE"
    echo ""
    echo "This might be because:"
    echo "1. IAM role doesn't have permission to view user profiles"
    echo "2. User ID is not a valid DataZone user"
else
    echo "$USER_PROFILE" | jq '{
        id,
        type,
        status,
        details
    }'
fi

echo ""
echo "=== Searching for analyst1-amirbo ==="

# Try to search for the user by name
SEARCH_RESULTS=$(aws datazone search-user-profiles \
    --domain-identifier "$DOMAIN_ID" \
    --user-type SSO_USER \
    --region "$REGION" \
    --output json 2>&1)

if echo "$SEARCH_RESULTS" | grep -q "error"; then
    echo "❌ Failed to search user profiles:"
    echo "$SEARCH_RESULTS"
else
    echo "All SSO users in domain:"
    echo "$SEARCH_RESULTS" | jq -r '.items[] | "  - ID: \(.id), Details: \(.details)"'
    
    echo ""
    echo "Checking if our user ID matches analyst1-amirbo:"
    MATCH=$(echo "$SEARCH_RESULTS" | jq -r ".items[] | select(.id == \"$USER_ID\") | .details")
    
    if [ -n "$MATCH" ] && [ "$MATCH" != "null" ]; then
        echo "✅ Found match!"
        echo "User details: $MATCH"
    else
        echo "⚠️  User ID $USER_ID not found in search results"
        echo ""
        echo "This could mean:"
        echo "1. The user was created with a different identifier"
        echo "2. The user type is not SSO_USER"
        echo "3. Search API has limitations"
    fi
fi

echo ""
echo "=== Alternative: Check via IAM Identity Center ==="
echo "The user ID format (UUID) suggests this is an IAM Identity Center (SSO) user"
echo "To verify the actual user name, you would need to:"
echo "1. Check IAM Identity Center console"
echo "2. Or use IAM Identity Center APIs with proper permissions"
echo "3. Or check DataZone portal as the domain admin"

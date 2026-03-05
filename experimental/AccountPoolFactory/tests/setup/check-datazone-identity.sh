#!/bin/bash
set -e

# Check current AWS identity and DataZone permissions

echo "=== Current AWS Identity ==="
aws sts get-caller-identity --output json | jq '{UserId, Account, Arn}'

echo ""
echo "=== Checking DataZone Domain Access ==="
DOMAIN_ID="dzd-4igt64u5j25ko9"
REGION="us-east-2"

# Try to list projects (this requires DataZone permissions)
echo "Attempting to list projects..."
if aws datazone list-projects \
    --domain-identifier "$DOMAIN_ID" \
    --region "$REGION" \
    --output json > /tmp/projects.json 2>&1; then
    echo "✅ Can list projects"
    jq '.items[] | {id, name, createdBy}' /tmp/projects.json
else
    echo "❌ Cannot list projects"
    cat /tmp/projects.json
fi

echo ""
echo "=== DataZone User Info ==="
# The issue is that DataZone uses SSO users, not IAM roles
# We need to check if the current identity is mapped to a DataZone user

echo "Note: DataZone requires SSO user identity, not IAM role"
echo "Current IAM role may not have DataZone user mapping"
echo ""
echo "To use DataZone APIs with proper permissions:"
echo "1. Ensure you're authenticated with SSO (mwinit)"
echo "2. Use AWS CLI with SSO profile"
echo "3. Or use DataZone portal for environment creation"

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

DEV_PROJECT_NAME=$(yq '.projects.dev.name' "$CONFIG_FILE")
DEV_PROJECT_DESC=$(yq '.projects.dev.description' "$CONFIG_FILE")
ADMIN_USERNAME=$(yq '.users.admin_username' "$CONFIG_FILE")

echo "=== Step 4: DataZone Project Setup ==="
echo "Account ID: $ACCOUNT_ID"
echo "Region: $REGION"
echo "Project Name: $DEV_PROJECT_NAME"
echo "Admin Username: $ADMIN_USERNAME"
echo ""

# Get domain ID directly from DataZone (look for domain matching 'Default*Domain' pattern)
echo "🔍 Discovering DataZone configuration..."
DOMAIN_ID=$(aws datazone list-domains --region "$REGION" --query 'items[?starts_with(name, `Default`) && ends_with(name, `Domain`)].id' --output text | head -1)

if [ -z "$DOMAIN_ID" ] || [ "$DOMAIN_ID" = "None" ]; then
    echo "❌ No DataZone domain matching 'Default*Domain' pattern found in region $REGION"
    echo "Available domains:"
    aws datazone list-domains --region "$REGION" --query 'items[].{Name:name,Id:id,Status:status}' --output table
    exit 1
fi

DOMAIN_NAME=$(aws datazone list-domains --region "$REGION" --query 'items[?starts_with(name, `Default`) && ends_with(name, `Domain`)].name' --output text | head -1)
echo "✅ Found DataZone domain: $DOMAIN_NAME (ID: $DOMAIN_ID)"

# Get project profile ID
PROJECT_PROFILE_ID=$(aws datazone list-project-profiles --domain-identifier "$DOMAIN_ID" --region "$REGION" --query 'items[?name==`Default Project Profile`].id' --output text)

if [ -z "$PROJECT_PROFILE_ID" ] || [ "$PROJECT_PROFILE_ID" = "None" ]; then
    PROJECT_PROFILE_ID=$(aws datazone list-project-profiles --domain-identifier "$DOMAIN_ID" --region "$REGION" --query 'items[?name==`All capabilities`].id' --output text)
    PROFILE_NAME="All capabilities"
else
    PROFILE_NAME="Default Project Profile"
fi

if [ -z "$PROJECT_PROFILE_ID" ] || [ "$PROJECT_PROFILE_ID" = "None" ]; then
    echo "❌ No suitable project profile found"
    echo "Available profiles:"
    aws datazone list-project-profiles --domain-identifier "$DOMAIN_ID" --region "$REGION" --query 'items[].{Name:name,Status:status}' --output table
    exit 1
fi

echo "✅ Using project profile: $PROFILE_NAME (ID: $PROJECT_PROFILE_ID)"
echo ""

# Check if project already exists
echo "🔍 Checking if project '$DEV_PROJECT_NAME' already exists..."
EXISTING_PROJECT=$(aws datazone list-projects --domain-identifier "$DOMAIN_ID" --region "$REGION" --query "items[?name=='$DEV_PROJECT_NAME'].id" --output text)

if [ -n "$EXISTING_PROJECT" ] && [ "$EXISTING_PROJECT" != "None" ]; then
    echo "✅ Project '$DEV_PROJECT_NAME' already exists with ID: $EXISTING_PROJECT"
    echo ""
    echo "🎉 Step 4 (Project Setup) Complete!"
    echo ""
    echo "Existing project details:"
    aws datazone list-projects --domain-identifier "$DOMAIN_ID" --region "$REGION" --query "items[?name=='$DEV_PROJECT_NAME']" --output table
    exit 0
fi

echo "🚀 Creating DataZone project using internal DataZone client..."
echo "   Project Name: $DEV_PROJECT_NAME"
echo "   Domain: $DOMAIN_NAME"

# Construct ARNs safely to avoid malformed ARNs
PROJECT_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/test-marketing-role"
OWNER_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/Admin"

echo "🔍 Verifying role ARNs..."
echo "   Project Role ARN: $PROJECT_ROLE_ARN"
echo "   Owner Role ARN: $OWNER_ROLE_ARN"

# Verify the roles exist before proceeding
if ! aws iam get-role --role-name "test-marketing-role" >/dev/null 2>&1; then
    echo "❌ Project role 'test-marketing-role' does not exist"
    echo "💡 Run Step 1 (account setup) to create required roles"
    exit 1
fi

if ! aws iam get-role --role-name "Admin" >/dev/null 2>&1; then
    echo "❌ Owner role 'Admin' does not exist"
    echo "💡 Ensure the Admin role exists in your account"
    exit 1
fi

echo "✅ Both roles exist and are accessible"
echo ""

# Use Python script with internal DataZone client for customerProvidedRoleConfigs support
python3 "$SCRIPT_DIR/create_project_with_roles.py" \
    --domain-name "$DOMAIN_NAME" \
    --project-name "$DEV_PROJECT_NAME" \
    --project-role-arn "$PROJECT_ROLE_ARN" \
    --owner-role-arn "$OWNER_ROLE_ARN" \
    --region "$REGION" \
    --wait-for-deployment

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Step 4 (Project Setup) Complete!"
    echo ""
    echo "📊 Project Summary:"
    echo "   Project Name: $DEV_PROJECT_NAME"
    echo "   Domain: $DOMAIN_NAME"
    echo "   Project Execution Role: $PROJECT_ROLE_ARN"
    echo "   Owner Role: $OWNER_ROLE_ARN"
    echo ""
    echo "🔗 All projects in domain:"
    aws datazone list-projects --domain-identifier "$DOMAIN_ID" --region "$REGION" --query 'items[].{Name:name,Id:id,Status:projectStatus}' --output table
    echo ""
    echo "➡️  Next: Run Step 5 to deploy testing infrastructure (MLflow, S3 buckets, test data)"
    
else
    echo ""
    echo "❌ Project creation failed"
    echo ""
    echo "💡 Troubleshooting tips:"
    echo "   1. Ensure the IAM role exists: $PROJECT_ROLE_ARN"
    echo "   2. Check if datazone-internal client is available"
    echo "   3. Verify domain permissions and project profile access"
    echo "   4. Check AWS credentials and region configuration"
    
    exit 1
fi
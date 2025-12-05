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

# Clean up any existing failed CloudFormation stacks
PROJECT_STACK_NAME="datazone-project-dev"
STACK_STATUS=$(aws cloudformation describe-stacks --stack-name "$PROJECT_STACK_NAME" --region "$REGION" --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DOES_NOT_EXIST")

if [ "$STACK_STATUS" != "DOES_NOT_EXIST" ] && [ "$STACK_STATUS" != "CREATE_COMPLETE" ] && [ "$STACK_STATUS" != "UPDATE_COMPLETE" ]; then
    echo "🧹 Cleaning up existing stack in $STACK_STATUS state..."
    aws cloudformation delete-stack --stack-name "$PROJECT_STACK_NAME" --region "$REGION"
    aws cloudformation wait stack-delete-complete --stack-name "$PROJECT_STACK_NAME" --region "$REGION"
    echo "✅ Stack cleanup completed"
fi

echo "🚀 Creating DataZone project via CloudFormation..."
echo "   Template: create_project.yaml"
echo "   Stack: $PROJECT_STACK_NAME"
echo "   Project Execution Role: arn:aws:iam::${ACCOUNT_ID}:role/test-marketing-role"
echo "   Owner Role: arn:aws:iam::${ACCOUNT_ID}:role/Admin"
echo ""

# Deploy CloudFormation stack with role configuration
aws cloudformation deploy \
  --template-file "$SCRIPT_DIR/create_project.yaml" \
  --stack-name "$PROJECT_STACK_NAME" \
  --parameter-overrides \
    DomainId="$DOMAIN_ID" \
    ProjectProfileId="$PROJECT_PROFILE_ID" \
    Name="$DEV_PROJECT_NAME" \
    ProjectRoleArn="arn:aws:iam::${ACCOUNT_ID}:role/test-marketing-role" \
    OwnerRoleArn="arn:aws:iam::${ACCOUNT_ID}:role/Admin" \
  --capabilities CAPABILITY_IAM \
  --region "$REGION" \
  --no-fail-on-empty-changeset

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ CloudFormation deployment successful!"
    
    # Get the project ID from the stack
    PROJECT_ID=$(aws cloudformation describe-stacks --stack-name "$PROJECT_STACK_NAME" --region "$REGION" --query 'Stacks[0].Outputs[?OutputKey==`ProjectId`].OutputValue' --output text)
    
    if [ -n "$PROJECT_ID" ] && [ "$PROJECT_ID" != "None" ]; then
        echo "📋 Project ID: $PROJECT_ID"
    else
        echo "⚠️  Could not retrieve Project ID from CloudFormation outputs"
    fi
    
    echo ""
    echo "🎉 Step 4 (Project Setup) Complete!"
    echo ""
    echo "📊 Project Summary:"
    echo "   Stack Name: $PROJECT_STACK_NAME"
    echo "   Project Name: $DEV_PROJECT_NAME"
    echo "   Project ID: $PROJECT_ID"
    echo "   Domain: $DOMAIN_NAME"
    echo "   Project Execution Role: arn:aws:iam::${ACCOUNT_ID}:role/test-marketing-role"
    echo "   Owner Role: arn:aws:iam::${ACCOUNT_ID}:role/Admin"
    echo ""
    echo "🔗 All projects in domain:"
    aws datazone list-projects --domain-identifier "$DOMAIN_ID" --region "$REGION" --query 'items[].{Name:name,Id:id,Status:projectStatus}' --output table
    echo ""
    echo "➡️  Next: Run Step 5 to deploy testing infrastructure (MLflow, S3 buckets, test data)"
    
else
    echo ""
    echo "❌ CloudFormation deployment failed"
    echo ""
    echo "🔍 Checking CloudFormation events for details..."
    aws cloudformation describe-stack-events --stack-name "$PROJECT_STACK_NAME" --region "$REGION" --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' --output table 2>/dev/null || echo "No failed events found"
    
    echo ""
    echo "📊 Stack status:"
    aws cloudformation describe-stacks --stack-name "$PROJECT_STACK_NAME" --region "$REGION" --query 'Stacks[0].{Status:StackStatus,Reason:StackStatusReason}' --output table 2>/dev/null || echo "Stack not found"
    
    echo ""
    echo "💡 Troubleshooting tips:"
    echo "   1. Check if the CustomerProvidedRoleConfigs property is supported in your region"
    echo "   2. Verify the IAM role exists: arn:aws:iam::${ACCOUNT_ID}:role/test-marketing-role"
    echo "   3. Check CloudFormation template syntax with: aws cloudformation validate-template --template-body file://create_project.yaml"
    
    exit 1
fi
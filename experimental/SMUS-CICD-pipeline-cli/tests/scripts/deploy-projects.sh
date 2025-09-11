#!/bin/bash

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${1:-$SCRIPT_DIR/config.yaml}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.yaml not found at $CONFIG_FILE"
    exit 1
fi

# Parse config
ACCOUNT_ID=$(yq '.account_id' "$CONFIG_FILE")
REGION=$(yq '.regions.primary.name' "$CONFIG_FILE")
DOMAIN_STACK_NAME=$(yq '.stacks.domain' "$CONFIG_FILE")
BLUEPRINTS_STACK_NAME=$(yq '.stacks.blueprints_profiles' "$CONFIG_FILE")

DEV_PROJECT_NAME=$(yq '.projects.dev.name' "$CONFIG_FILE")
DEV_PROJECT_DESC=$(yq '.projects.dev.description' "$CONFIG_FILE")
ADMIN_USERNAME=$(yq '.users.admin_username' "$CONFIG_FILE")

# Get owners array from config
OWNERS_JSON=$(yq '.users.owners' "$CONFIG_FILE" -o json)

echo "Deploying DataZone Dev Project..."
echo "Account ID: $ACCOUNT_ID"
echo "Region: $REGION"
echo "Domain Stack: $DOMAIN_STACK_NAME"
echo "Blueprints Stack: $BLUEPRINTS_STACK_NAME"
echo "Project Owners: $OWNERS_JSON"

# Check if stack exists and is in ROLLBACK_COMPLETE state
PROJECT_STACK_NAME="datazone-project-dev"
STACK_STATUS=$(aws cloudformation describe-stacks --stack-name "$PROJECT_STACK_NAME" --region "$REGION" --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DOES_NOT_EXIST")

if [ "$STACK_STATUS" = "ROLLBACK_COMPLETE" ]; then
    echo "Stack $PROJECT_STACK_NAME is in ROLLBACK_COMPLETE state. Deleting..."
    aws cloudformation delete-stack --stack-name "$PROJECT_STACK_NAME" --region "$REGION"
    echo "Waiting for stack deletion to complete..."
    aws cloudformation wait stack-delete-complete --stack-name "$PROJECT_STACK_NAME" --region "$REGION"
    echo "Stack deleted successfully."
fi

# Get required values from stacks
DOMAIN_ID=$(aws cloudformation describe-stacks --stack-name "$DOMAIN_STACK_NAME" --region "$REGION" --query 'Stacks[0].Outputs[?OutputKey==`DomainId`].OutputValue' --output text)

# Get the "All capabilities" project profile ID
PROJECT_PROFILE_ID=$(aws datazone list-project-profiles --domain-identifier "$DOMAIN_ID" --region "$REGION" --query 'items[?name==`All capabilities`].id' --output text)

echo "Domain ID: $DOMAIN_ID"
echo "Project Profile ID: $PROJECT_PROFILE_ID"

# Check if stack exists and handle cleanup
PROJECT_STACK_NAME="datazone-project-dev"
STACK_STATUS=$(aws cloudformation describe-stacks --stack-name "$PROJECT_STACK_NAME" --region "$REGION" --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DOES_NOT_EXIST")

if [ "$STACK_STATUS" = "ROLLBACK_COMPLETE" ] || [ "$STACK_STATUS" = "ROLLBACK_IN_PROGRESS" ] || [ "$STACK_STATUS" = "CREATE_FAILED" ]; then
    echo "Stack $PROJECT_STACK_NAME is in $STACK_STATUS state. Deleting..."
    aws cloudformation delete-stack --stack-name "$PROJECT_STACK_NAME" --region "$REGION"
    echo "Waiting for stack deletion to complete..."
    aws cloudformation wait stack-delete-complete --stack-name "$PROJECT_STACK_NAME" --region "$REGION"
    echo "Stack cleanup completed."
fi

echo ""
echo "=== Deploying Dev Project: $DEV_PROJECT_NAME ==="
aws cloudformation deploy \
  --template-file create_project.yaml \
  --stack-name "datazone-project-dev" \
  --parameter-overrides \
    DomainId="$DOMAIN_ID" \
    ProjectProfileId="$PROJECT_PROFILE_ID" \
    Name="$DEV_PROJECT_NAME" \
  --capabilities CAPABILITY_IAM \
  --region "$REGION"

if [ $? -eq 0 ]; then
    echo "✅ Dev project stack deployment complete!"
    
    # Get the project ID from the stack
    PROJECT_ID=$(aws cloudformation describe-stacks --stack-name "datazone-project-dev" --region "$REGION" --query 'Stacks[0].Outputs[?OutputKey==`ProjectId`].OutputValue' --output text)
    echo "Project ID: $PROJECT_ID"
    
    # Get the user identity from IDC for the admin user
    echo "Adding project membership for user: $ADMIN_USERNAME"
    
    # First, get the Identity Store ID (try current region first)
    echo "Getting Identity Store ID..."
    IDENTITY_STORE_ID=$(aws sso-admin list-instances --region "$REGION" --query 'Instances[0].IdentityStoreId' --output text)
    
    if [ -z "$IDENTITY_STORE_ID" ] || [ "$IDENTITY_STORE_ID" = "None" ]; then
        echo "❌ No SSO instance found. IDC may not be enabled or accessible."
        echo "Skipping user membership setup."
        exit 0
    fi
    
    echo "Identity Store ID: $IDENTITY_STORE_ID"
    
    # Find the user in IDC (Identity Center)
    echo "Looking up user $ADMIN_USERNAME in IDC..."
    IDC_USER_ID=$(aws identitystore list-users --identity-store-id "$IDENTITY_STORE_ID" --region "$REGION" --query "Users[?UserName=='${ADMIN_USERNAME}'].UserId" --output text)
    
    if [ -z "$IDC_USER_ID" ] || [ "$IDC_USER_ID" = "None" ]; then
        echo "❌ User $ADMIN_USERNAME not found in IDC"
        echo "Available IDC users:"
        aws identitystore list-users --identity-store-id "$IDENTITY_STORE_ID" --region "$REGION" --query "Users[].{UserName:UserName,DisplayName:DisplayName,UserId:UserId}" --output table
        exit 0
    fi
    
    echo "✅ Found IDC user: $IDC_USER_ID"
    
    # Now check if DataZone user profile exists
    echo "Checking if DataZone user profile exists for $ADMIN_USERNAME..."
    USER_PROFILE_ID=$(aws datazone search-user-profiles --domain-identifier "$DOMAIN_ID" --region "$REGION" --user-type SSO_USER --query "items[?details.username=='${ADMIN_USERNAME}' || id=='${IDC_USER_ID}'].id" --output text)
    
    if [ -z "$USER_PROFILE_ID" ] || [ "$USER_PROFILE_ID" = "None" ]; then
        echo "Creating DataZone user profile for $ADMIN_USERNAME..."
        USER_PROFILE_ID=$(aws datazone create-user-profile \
            --domain-identifier "$DOMAIN_ID" \
            --user-identifier "$IDC_USER_ID" \
            --user-type SSO_USER \
            --region "$REGION" \
            --query 'id' --output text 2>/dev/null)
        
        if [ $? -eq 0 ] && [ -n "$USER_PROFILE_ID" ]; then
            echo "✅ Created DataZone user profile: $USER_PROFILE_ID"
        else
            echo "⚠️  User profile may already exist, searching again..."
            USER_PROFILE_ID=$(aws datazone search-user-profiles --domain-identifier "$DOMAIN_ID" --region "$REGION" --user-type SSO_USER --query "items[].id" --output text | head -1)
        fi
    else
        echo "✅ DataZone user profile already exists: $USER_PROFILE_ID"
    fi
    
    if [ -n "$USER_PROFILE_ID" ] && [ "$USER_PROFILE_ID" != "None" ]; then
        echo "Adding user as PROJECT_OWNER..."
        
        # Add user as PROJECT_OWNER
        aws datazone create-project-membership \
            --domain-identifier "$DOMAIN_ID" \
            --project-identifier "$PROJECT_ID" \
            --member userIdentifier="$USER_PROFILE_ID" \
            --designation PROJECT_OWNER \
            --region "$REGION"
            
        if [ $? -eq 0 ]; then
            echo "✅ Successfully added $ADMIN_USERNAME as PROJECT_OWNER"
        else
            echo "❌ Failed to add project membership"
        fi
    else
        echo "❌ Could not get user profile ID for $ADMIN_USERNAME"
    fi
else
    echo "❌ Dev project stack deployment failed"
fi

if [ $? -eq 0 ]; then
    echo "✅ Dev project stack deployed successfully"
    echo ""
    echo "🎉 Dev project deployment complete!"
    echo ""
    echo "Stack Name: datazone-project-dev"
    echo ""
    echo "Note: Test and Prod projects will be created by the CLI when needed."
else
    echo "❌ Dev project stack deployment failed"
    exit 1
fi

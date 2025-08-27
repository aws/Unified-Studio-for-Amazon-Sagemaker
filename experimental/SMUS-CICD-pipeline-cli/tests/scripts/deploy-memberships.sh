#!/bin/bash

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.yaml not found at $CONFIG_FILE"
    exit 1
fi

# Parse config
REGION=$(yq '.region' "$CONFIG_FILE")
DOMAIN_STACK_NAME=$(yq '.stacks.domain' "$CONFIG_FILE")
ADMIN_USERNAME=$(yq '.users.admin_username' "$CONFIG_FILE")

echo "Deploying DataZone Project Memberships..."
echo "Region: $REGION"
echo "Domain Stack: $DOMAIN_STACK_NAME"
echo "Admin Username: $ADMIN_USERNAME"

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

# Deploy Dev Project Membership
echo ""
echo "=== Deploying Dev Project Membership ==="

# Get Dev Project ID
DEV_PROJECT_ID=$(aws cloudformation describe-stacks \
  --stack-name "datazone-project-dev" \
  --query 'Stacks[0].Outputs[?OutputKey==`ProjectId`].OutputValue' \
  --output text \
  --region "$REGION")

if [ -z "$DEV_PROJECT_ID" ] || [ "$DEV_PROJECT_ID" = "None" ]; then
    echo "❌ Failed to get Project ID from stack datazone-project-dev"
    exit 1
fi

echo "✅ Dev Project ID: $DEV_PROJECT_ID"

aws cloudformation deploy \
  --template-file ../../cloudformation/single-project-membership.yaml \
  --stack-name "datazone-membership-dev" \
  --parameter-overrides \
    DomainId="$DOMAIN_ID" \
    ProjectId="$DEV_PROJECT_ID" \
    ProjectOwners="$ADMIN_USERNAME" \
  --capabilities CAPABILITY_IAM \
  --region "$REGION"

if [ $? -eq 0 ]; then
    echo "✅ Dev project membership deployed successfully"
else
    echo "❌ Dev project membership deployment failed"
    exit 1
fi

# Deploy Test Project Membership (if test project exists)
echo ""
echo "=== Deploying Test Project Membership ==="

TEST_PROJECT_ID=$(aws cloudformation describe-stacks \
  --stack-name "datazone-project-test" \
  --query 'Stacks[0].Outputs[?OutputKey==`ProjectId`].OutputValue' \
  --output text \
  --region "$REGION" 2>/dev/null)

if [ -z "$TEST_PROJECT_ID" ] || [ "$TEST_PROJECT_ID" = "None" ]; then
    echo "⚠️  Test project stack not found, skipping test membership"
else
    echo "✅ Test Project ID: $TEST_PROJECT_ID"
    
    aws cloudformation deploy \
      --template-file ../../cloudformation/single-project-membership.yaml \
      --stack-name "datazone-membership-test" \
      --parameter-overrides \
        DomainId="$DOMAIN_ID" \
        ProjectId="$TEST_PROJECT_ID" \
        ProjectOwners="$ADMIN_USERNAME" \
      --capabilities CAPABILITY_IAM \
      --region "$REGION"

    if [ $? -eq 0 ]; then
        echo "✅ Test project membership deployed successfully"
    else
        echo "❌ Test project membership deployment failed"
        exit 1
    fi
fi

# Deploy Prod Project Membership (if prod project exists)
echo ""
echo "=== Deploying Prod Project Membership ==="

PROD_PROJECT_ID=$(aws cloudformation describe-stacks \
  --stack-name "datazone-project-prod" \
  --query 'Stacks[0].Outputs[?OutputKey==`ProjectId`].OutputValue' \
  --output text \
  --region "$REGION" 2>/dev/null)

if [ -z "$PROD_PROJECT_ID" ] || [ "$PROD_PROJECT_ID" = "None" ]; then
    echo "⚠️  Prod project stack not found, skipping prod membership"
else
    echo "✅ Prod Project ID: $PROD_PROJECT_ID"
    
    aws cloudformation deploy \
      --template-file ../../cloudformation/single-project-membership.yaml \
      --stack-name "datazone-membership-prod" \
      --parameter-overrides \
        DomainId="$DOMAIN_ID" \
        ProjectId="$PROD_PROJECT_ID" \
        ProjectOwners="$ADMIN_USERNAME" \
      --capabilities CAPABILITY_IAM \
      --region "$REGION"

    if [ $? -eq 0 ]; then
        echo "✅ Prod project membership deployed successfully"
    else
        echo "❌ Prod project membership deployment failed"
        exit 1
    fi
fi

echo ""
echo "🎉 Project memberships deployment completed!"
echo ""
echo "Domain ID: $DOMAIN_ID"
echo "Admin user '$ADMIN_USERNAME' added as PROJECT_OWNER to available projects"
echo ""
echo "Deployed Membership Stacks:"
[ ! -z "$DEV_PROJECT_ID" ] && echo "  - datazone-membership-dev (Project ID: $DEV_PROJECT_ID)"
[ ! -z "$TEST_PROJECT_ID" ] && echo "  - datazone-membership-test (Project ID: $TEST_PROJECT_ID)"
[ ! -z "$PROD_PROJECT_ID" ] && echo "  - datazone-membership-prod (Project ID: $PROD_PROJECT_ID)"

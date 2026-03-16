#!/bin/bash

# Update CF1 stack to support multi-strategy account creation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load configuration
if [ -f "$PROJECT_ROOT/config.yaml" ]; then
    ACCOUNT_ID=$(grep 'account_id:' "$PROJECT_ROOT/config.yaml" | awk '{print $2}' | tr -d '"')
    REGION=$(grep 'region:' "$PROJECT_ROOT/config.yaml" | awk '{print $2}' | tr -d '"')
else
    echo "Error: config.yaml not found"
    exit 1
fi

STACK_NAME="AccountPoolFactory-ControlTower-Test"
TEMPLATE_FILE="$PROJECT_ROOT/01-org-account/templates/cloudformation/SMUS-AccountPoolFactory-OrgAdmin.yaml"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Updating CF1 Stack for Multi-Strategy Support ===${NC}"
echo ""
echo "Stack: $STACK_NAME"
echo "Region: $REGION"
echo "Template: $TEMPLATE_FILE"
echo ""

# Check if stack exists
if ! aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" &>/dev/null; then
    echo -e "${RED}Error: Stack $STACK_NAME does not exist${NC}"
    echo "Deploy it first with: ./deploy-account-factory.sh"
    exit 1
fi

# Get current parameters
echo -e "${YELLOW}Getting current stack parameters...${NC}"
CURRENT_PARAMS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Parameters' \
    --output json)

REQUESTING_ACCOUNT_ID=$(echo "$CURRENT_PARAMS" | jq -r '.[] | select(.ParameterKey=="RequestingAccountId") | .ParameterValue')
PROJECT_TAG=$(echo "$CURRENT_PARAMS" | jq -r '.[] | select(.ParameterKey=="ProjectTag") | .ParameterValue // "AccountPoolFactory"')
ENVIRONMENT_TAG=$(echo "$CURRENT_PARAMS" | jq -r '.[] | select(.ParameterKey=="EnvironmentTag") | .ParameterValue // "Test"')
OWNER_TAG=$(echo "$CURRENT_PARAMS" | jq -r '.[] | select(.ParameterKey=="OwnerTag") | .ParameterValue // "DataZoneAdmin"')

echo "  Requesting Account ID: $REQUESTING_ACCOUNT_ID"
echo "  Project Tag: $PROJECT_TAG"
echo "  Environment Tag: $ENVIRONMENT_TAG"
echo "  Owner Tag: $OWNER_TAG"
echo ""

# Prompt for strategy selection
echo -e "${YELLOW}Select account creation strategy:${NC}"
echo "  1) organizations_api (recommended - no Control Tower needed)"
echo "  2) control_tower (requires Control Tower setup)"
echo "  3) both (support both strategies)"
echo ""
read -p "Enter choice [1-3]: " STRATEGY_CHOICE

case $STRATEGY_CHOICE in
    1)
        STRATEGY="organizations_api"
        ;;
    2)
        STRATEGY="control_tower"
        ;;
    3)
        STRATEGY="both"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo "Selected strategy: $STRATEGY"
echo ""

# Build parameters
PARAMETERS="ParameterKey=AccountCreationStrategy,ParameterValue=$STRATEGY"
PARAMETERS="$PARAMETERS ParameterKey=RequestingAccountId,ParameterValue=$REQUESTING_ACCOUNT_ID"
PARAMETERS="$PARAMETERS ParameterKey=ProjectTag,ParameterValue=$PROJECT_TAG"
PARAMETERS="$PARAMETERS ParameterKey=EnvironmentTag,ParameterValue=$ENVIRONMENT_TAG"
PARAMETERS="$PARAMETERS ParameterKey=OwnerTag,ParameterValue=$OWNER_TAG"

# If Control Tower strategy, ask for product ID
if [ "$STRATEGY" == "control_tower" ] || [ "$STRATEGY" == "both" ]; then
    echo -e "${YELLOW}Control Tower Configuration:${NC}"
    read -p "Enter Control Tower Product ID (or press Enter to auto-discover): " PRODUCT_ID
    if [ -n "$PRODUCT_ID" ]; then
        PARAMETERS="$PARAMETERS ParameterKey=ControlTowerProductId,ParameterValue=$PRODUCT_ID"
    fi
    echo ""
fi

# Validate template
echo -e "${YELLOW}Validating CloudFormation template...${NC}"
aws cloudformation validate-template \
    --template-body "file://$TEMPLATE_FILE" \
    --region "$REGION" \
    > /dev/null

echo -e "${GREEN}✓ Template is valid${NC}"
echo ""

# Create change set
CHANGE_SET_NAME="multi-strategy-update-$(date +%Y%m%d-%H%M%S)"

echo -e "${YELLOW}Creating change set: $CHANGE_SET_NAME${NC}"
aws cloudformation create-change-set \
    --stack-name "$STACK_NAME" \
    --change-set-name "$CHANGE_SET_NAME" \
    --template-body "file://$TEMPLATE_FILE" \
    --parameters $PARAMETERS \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION"

echo "Waiting for change set to be created..."
aws cloudformation wait change-set-create-complete \
    --stack-name "$STACK_NAME" \
    --change-set-name "$CHANGE_SET_NAME" \
    --region "$REGION"

echo -e "${GREEN}✓ Change set created${NC}"
echo ""

# Show changes
echo -e "${YELLOW}Changes to be applied:${NC}"
aws cloudformation describe-change-set \
    --stack-name "$STACK_NAME" \
    --change-set-name "$CHANGE_SET_NAME" \
    --region "$REGION" \
    --query 'Changes[].{Action:ResourceChange.Action,LogicalId:ResourceChange.LogicalResourceId,ResourceType:ResourceChange.ResourceType,Replacement:ResourceChange.Replacement}' \
    --output table

echo ""

# Confirm execution
read -p "Execute this change set? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Deleting change set...${NC}"
    aws cloudformation delete-change-set \
        --stack-name "$STACK_NAME" \
        --change-set-name "$CHANGE_SET_NAME" \
        --region "$REGION"
    echo "Update cancelled"
    exit 0
fi

# Execute change set
echo ""
echo -e "${YELLOW}Executing change set...${NC}"
aws cloudformation execute-change-set \
    --stack-name "$STACK_NAME" \
    --change-set-name "$CHANGE_SET_NAME" \
    --region "$REGION"

echo "Waiting for stack update to complete (this may take a few minutes)..."
aws cloudformation wait stack-update-complete \
    --stack-name "$STACK_NAME" \
    --region "$REGION"

echo -e "${GREEN}✓ Stack update complete!${NC}"
echo ""

# Show outputs
echo -e "${YELLOW}Stack Outputs:${NC}"
aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs' \
    --output table

echo ""
echo -e "${GREEN}=== Update Complete ===${NC}"
echo ""
echo "The CF1 stack now supports: $STRATEGY"
echo ""
echo "Next steps:"
if [ "$STRATEGY" == "organizations_api" ] || [ "$STRATEGY" == "both" ]; then
    echo "  1. Test Organizations API: ./test-create-account-orgs-api.sh"
fi
if [ "$STRATEGY" == "control_tower" ] || [ "$STRATEGY" == "both" ]; then
    echo "  1. Test Control Tower: ./test-create-account.sh"
fi
echo ""

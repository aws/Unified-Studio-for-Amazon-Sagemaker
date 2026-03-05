#!/bin/bash

# Check if AWS Control Tower is enabled in this account

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
CONFIG_FILE="$PROJECT_ROOT/config.yaml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Check AWS Control Tower Status${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Read region from config
if [ -f "$CONFIG_FILE" ]; then
    if command -v yq &> /dev/null; then
        REGION=$(yq eval '.aws.region' "$CONFIG_FILE")
    else
        REGION=$(grep "region:" "$CONFIG_FILE" | head -1 | sed 's/.*: //' | tr -d '"' | tr -d "'")
    fi
else
    REGION="us-east-2"
fi

echo "Region: $REGION"
echo ""

# Check 1: Control Tower Home Region
echo -e "${YELLOW}[1/4] Checking Control Tower home region...${NC}"
HOME_REGION=$(aws controltower get-control-tower-status \
    --region "$REGION" \
    --query 'homeRegion' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$HOME_REGION" != "NOT_FOUND" ] && [ "$HOME_REGION" != "None" ]; then
    echo -e "${GREEN}✓ Control Tower is enabled${NC}"
    echo "  Home Region: $HOME_REGION"
else
    echo -e "${RED}✗ Control Tower is not enabled${NC}"
    echo ""
    echo -e "${YELLOW}Control Tower Setup Required${NC}"
    echo ""
    echo "To enable Control Tower:"
    echo "1. Go to AWS Control Tower console: https://console.aws.amazon.com/controltower"
    echo "2. Click 'Set up landing zone'"
    echo "3. Follow the setup wizard (takes ~30 minutes)"
    echo "4. Required: AWS Organizations must be enabled"
    echo "5. Required: AWS SSO/IAM Identity Center will be configured"
    echo ""
    echo "For more information:"
    echo "https://docs.aws.amazon.com/controltower/latest/userguide/setting-up.html"
    echo ""
    exit 1
fi
echo ""

# Check 2: Account Factory Product
echo -e "${YELLOW}[2/4] Checking Account Factory product...${NC}"
PRODUCT_ID=$(aws servicecatalog search-products \
    --region "$REGION" \
    --filters "FullTextSearch=AWS Control Tower Account Factory" \
    --query 'ProductViewSummaries[0].ProductId' \
    --output text 2>/dev/null || echo "")

if [ -n "$PRODUCT_ID" ] && [ "$PRODUCT_ID" != "None" ]; then
    echo -e "${GREEN}✓ Account Factory product found${NC}"
    echo "  Product ID: $PRODUCT_ID"
else
    echo -e "${RED}✗ Account Factory product not found${NC}"
    echo "  This may indicate Control Tower is not fully set up"
fi
echo ""

# Check 3: Control Tower OUs
echo -e "${YELLOW}[3/4] Checking Control Tower OUs...${NC}"
ROOT_ID=$(aws organizations list-roots \
    --region "$REGION" \
    --query 'Roots[0].Id' \
    --output text 2>/dev/null || echo "")

if [ -n "$ROOT_ID" ]; then
    CT_OUS=$(aws organizations list-organizational-units-for-parent \
        --parent-id "$ROOT_ID" \
        --region "$REGION" \
        --query 'OrganizationalUnits[?Name==`Security` || Name==`Sandbox`].Name' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$CT_OUS" ]; then
        echo -e "${GREEN}✓ Control Tower OUs found${NC}"
        echo "  OUs: $CT_OUS"
    else
        echo -e "${YELLOW}⊘ Standard Control Tower OUs not found${NC}"
        echo "  This is OK if you're using custom OU structure"
    fi
else
    echo -e "${RED}✗ Could not access Organizations${NC}"
fi
echo ""

# Check 4: Control Tower Execution Role
echo -e "${YELLOW}[4/4] Checking AWSControlTowerExecution role...${NC}"
ROLE_EXISTS=$(aws iam get-role \
    --role-name AWSControlTowerExecution \
    --region "$REGION" \
    --query 'Role.RoleName' \
    --output text 2>/dev/null || echo "")

if [ -n "$ROLE_EXISTS" ]; then
    echo -e "${GREEN}✓ AWSControlTowerExecution role exists${NC}"
else
    echo -e "${YELLOW}⊘ AWSControlTowerExecution role not found${NC}"
    echo "  This role is created in managed accounts, not the management account"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ "$HOME_REGION" != "NOT_FOUND" ] && [ "$HOME_REGION" != "None" ] && [ -n "$PRODUCT_ID" ]; then
    echo -e "${GREEN}✓ Control Tower is enabled and ready${NC}"
    echo ""
    echo "You can proceed with:"
    echo "  ./tests/setup/scripts/deploy-account-factory.sh"
    echo "  ./tests/setup/scripts/test-create-account.sh"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Control Tower is not fully enabled${NC}"
    echo ""
    echo "Please enable Control Tower before proceeding:"
    echo "https://console.aws.amazon.com/controltower"
    echo ""
    exit 1
fi

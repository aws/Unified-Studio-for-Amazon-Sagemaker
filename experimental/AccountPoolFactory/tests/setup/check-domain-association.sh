#!/bin/bash

# Check DataZone Domain Association Status
# This script checks if the domain is properly associated with a project account

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
CONFIG_FILE="$PROJECT_ROOT/config.yaml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if account number provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Account number required${NC}"
    echo "Usage: $0 <account_number>"
    echo "Example: $0 100"
    exit 1
fi

ACCOUNT_NUM=$1
PROVISION_FILE="$PROJECT_ROOT/tests/setup/test-accounts/test-account-provision-${ACCOUNT_NUM}.json"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Check DataZone Domain Association${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if provision file exists
if [ ! -f "$PROVISION_FILE" ]; then
    echo -e "${RED}Error: Provision file not found: $PROVISION_FILE${NC}"
    echo "Please create the account first"
    exit 1
fi

# Read account details
ACCOUNT_ID=$(jq -r '.accountId' "$PROVISION_FILE")
ACCOUNT_EMAIL=$(jq -r '.accountEmail' "$PROVISION_FILE")
ACCOUNT_NAME=$(jq -r '.accountName' "$PROVISION_FILE")

echo "Account Details:"
echo "  Account Number: $ACCOUNT_NUM"
echo "  Account ID: $ACCOUNT_ID"
echo "  Account Email: $ACCOUNT_EMAIL"
echo "  Account Name: $ACCOUNT_NAME"
echo ""

# Function to read config value
get_config_value() {
    local key=$1
    if command -v yq &> /dev/null; then
        yq eval "$key" "$CONFIG_FILE"
    else
        grep "^${key##*.}:" "$CONFIG_FILE" | sed 's/.*: //' | tr -d '"' | tr -d "'"
    fi
}

# Read configuration
REGION=$(get_config_value '.aws.region')
ORG_ACCOUNT_ID=$(get_config_value '.aws.account_id')
DOMAIN_ID=$(get_config_value '.datazone.domain_id')
DOMAIN_NAME=$(get_config_value '.datazone.domain_name')
PORTAL_URL=$(get_config_value '.datazone.portal_url')

echo "Configuration:"
echo "  Region: $REGION"
echo "  Org Admin Account: $ORG_ACCOUNT_ID"
echo "  Domain ID: $DOMAIN_ID"
echo "  Domain Name: $DOMAIN_NAME"
echo "  Portal URL: $PORTAL_URL"
echo ""

# Check current account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query 'Account' --output text 2>/dev/null || echo "unknown")

if [ "$CURRENT_ACCOUNT" != "$ACCOUNT_ID" ]; then
    echo -e "${YELLOW}Note: You are in account $CURRENT_ACCOUNT, not target account $ACCOUNT_ID${NC}"
    echo "To check domain association, you need to:"
    echo "1. Assume role in account $ACCOUNT_ID"
    echo "2. Open DataZone console"
    echo "3. Check 'Associated domains' section"
    echo ""
    echo "To assume role:"
    echo "  aws sts assume-role \\"
    echo "    --role-arn arn:aws:iam::${ACCOUNT_ID}:role/OrganizationAccountAccessRole \\"
    echo "    --role-session-name DomainCheck \\"
    echo "    --region $REGION"
    echo ""
fi

# Try to list domains in the account
echo -e "${YELLOW}Checking DataZone domains in account...${NC}"

if [ "$CURRENT_ACCOUNT" = "$ACCOUNT_ID" ]; then
    DOMAINS=$(aws datazone list-domains --region "$REGION" --output json 2>&1)
    
    if echo "$DOMAINS" | jq -e '.items' &> /dev/null; then
        DOMAIN_COUNT=$(echo "$DOMAINS" | jq '.items | length')
        echo "Found $DOMAIN_COUNT domain(s) in account $ACCOUNT_ID"
        
        if [ "$DOMAIN_COUNT" -gt 0 ]; then
            echo ""
            echo "Domains:"
            echo "$DOMAINS" | jq -r '.items[] | "  - ID: \(.id)\n    Name: \(.name)\n    Status: \(.status)"'
            echo ""
            
            # Check if our domain is in the list
            OUR_DOMAIN=$(echo "$DOMAINS" | jq -r ".items[] | select(.id==\"$DOMAIN_ID\") | .id")
            if [ -n "$OUR_DOMAIN" ] && [ "$OUR_DOMAIN" != "null" ]; then
                echo -e "${GREEN}✓ Domain $DOMAIN_ID is associated with this account!${NC}"
            else
                echo -e "${YELLOW}Note: Domain $DOMAIN_ID not found in list${NC}"
                echo "This might mean:"
                echo "  - Domain association is pending"
                echo "  - Need to check 'Associated domains' in console"
                echo "  - API might not show associated domains from other accounts"
            fi
        else
            echo -e "${YELLOW}No domains found in this account${NC}"
            echo "This is expected if:"
            echo "  - Domain is in another account (org admin)"
            echo "  - Need to check 'Associated domains' section in console"
        fi
    else
        echo -e "${YELLOW}Could not list domains${NC}"
        echo "Error: $DOMAINS"
    fi
else
    echo -e "${YELLOW}Skipping domain list (not in target account)${NC}"
fi
echo ""

# Check RAM resource shares
echo -e "${YELLOW}Checking RAM resource shares...${NC}"

if [ "$CURRENT_ACCOUNT" = "$ACCOUNT_ID" ]; then
    RAM_SHARES=$(aws ram get-resource-shares \
        --resource-owner OTHER-ACCOUNTS \
        --region "$REGION" \
        --query 'resourceShares[?contains(name, `Domain`) || contains(name, `OrgShare`)]' \
        --output json 2>&1)
    
    if echo "$RAM_SHARES" | jq -e '.' &> /dev/null; then
        SHARE_COUNT=$(echo "$RAM_SHARES" | jq 'length')
        
        if [ "$SHARE_COUNT" -gt 0 ]; then
            echo -e "${GREEN}✓ Found $SHARE_COUNT domain resource share(s)${NC}"
            echo ""
            echo "Resource Shares:"
            echo "$RAM_SHARES" | jq -r '.[] | "  - Name: \(.name)\n    Status: \(.status)\n    Owner: \(.owningAccountId)"'
            echo ""
        else
            echo -e "${YELLOW}No domain resource shares found${NC}"
        fi
    else
        echo -e "${YELLOW}Could not check RAM shares${NC}"
        echo "Error: $RAM_SHARES"
    fi
else
    echo -e "${YELLOW}Skipping RAM check (not in target account)${NC}"
fi
echo ""

# Summary and next steps
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Summary and Next Steps${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo -e "${BLUE}To verify domain association in DataZone console:${NC}"
echo ""
echo "1. Sign in to AWS Console for account $ACCOUNT_ID"
echo "   Account ID: $ACCOUNT_ID"
echo "   Account Name: $ACCOUNT_NAME"
echo ""
echo "2. Open Amazon DataZone console:"
echo "   https://console.aws.amazon.com/datazone/home?region=${REGION}"
echo ""
echo "3. Check 'Associated domains' in left navigation"
echo "   Expected: See '$DOMAIN_NAME' listed"
echo "   Status should be: ASSOCIATED"
echo ""
echo "4. If domain is associated, enable blueprints:"
echo "   a. Click on the domain name"
echo "   b. Go to 'Blueprints' tab"
echo "   c. Select 'DefaultDataLake'"
echo "   d. Click 'Enable in this account'"
echo "   e. Configure IAM roles:"
echo "      - Glue Manage Access role: Create new"
echo "      - Provisioning role: Create new"
echo "   f. Click 'Enable blueprint'"
echo ""
echo "5. Verify blueprint is enabled:"
echo "   - Status should show 'Enabled'"
echo "   - Blueprint should be available for creating environments"
echo ""

echo -e "${BLUE}Alternative: Use DataZone Portal${NC}"
echo ""
echo "1. Open DataZone Portal:"
echo "   $PORTAL_URL"
echo ""
echo "2. Sign in with account $ACCOUNT_ID credentials"
echo ""
echo "3. You should see the domain and be able to:"
echo "   - Browse data catalog"
echo "   - Create projects"
echo "   - Subscribe to data assets"
echo ""

echo -e "${YELLOW}Important Notes:${NC}"
echo "• Domain association should be automatic (same AWS Organization)"
echo "• Blueprint enablement is required before creating environments"
echo "• Each account needs to enable blueprints independently"
echo "• VPC StackSet should be deployed before creating DataZone environments"
echo ""

echo -e "${GREEN}Verification complete!${NC}"
echo ""

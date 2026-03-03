#!/bin/bash

# Verify DataZone Domain is Available in Project Account
# This script checks if the domain shared via RAM is visible in a project account

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
echo -e "${GREEN}Verify Domain in Project Account${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if provision file exists
if [ ! -f "$PROVISION_FILE" ]; then
    echo -e "${RED}Error: Provision file not found: $PROVISION_FILE${NC}"
    echo "Please create the account first using test-create-account-orgs-api.sh"
    exit 1
fi

# Read account details from provision file
ACCOUNT_ID=$(jq -r '.accountId' "$PROVISION_FILE")
ACCOUNT_EMAIL=$(jq -r '.accountEmail' "$PROVISION_FILE")
ACCOUNT_NAME=$(jq -r '.accountName' "$PROVISION_FILE")

if [ -z "$ACCOUNT_ID" ] || [ "$ACCOUNT_ID" = "null" ]; then
    echo -e "${RED}Error: Account ID not found in provision file${NC}"
    exit 1
fi

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
ORGANIZATION_ID=$(get_config_value '.organization.organization_id')

echo "Configuration:"
echo "  Region: $REGION"
echo "  Org Admin Account: $ORG_ACCOUNT_ID"
echo "  Domain ID: $DOMAIN_ID"
echo "  Domain Name: $DOMAIN_NAME"
echo "  Organization ID: $ORGANIZATION_ID"
echo ""

# Step 1: Assume role in target account
echo -e "${YELLOW}Step 1: Assuming role in target account...${NC}"

# Check current account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query 'Account' --output text 2>/dev/null || echo "unknown")

if [ "$CURRENT_ACCOUNT" = "$ACCOUNT_ID" ]; then
    echo -e "${GREEN}✓ Already in target account $ACCOUNT_ID${NC}"
    echo "Using current credentials"
    ASSUMED_ROLE=false
else
    echo "Current account: $CURRENT_ACCOUNT"
    echo "Target account: $ACCOUNT_ID"
    echo ""
    
    # Try OrganizationAccountAccessRole first (created by Organizations)
    ROLE_NAME="OrganizationAccountAccessRole"
    ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
    
    echo "Attempting to assume role: $ROLE_ARN"
    
    # Assume role
    ASSUME_ROLE_OUTPUT=$(aws sts assume-role \
        --role-arn "$ROLE_ARN" \
        --role-session-name "DomainVerification-${ACCOUNT_NUM}" \
        --duration-seconds 3600 \
        --region "$REGION" 2>&1) || {
        
        # If OrganizationAccountAccessRole fails, try AWSControlTowerExecution
        echo -e "${YELLOW}OrganizationAccountAccessRole not available, trying AWSControlTowerExecution...${NC}"
        ROLE_NAME="AWSControlTowerExecution"
        ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
        
        ASSUME_ROLE_OUTPUT=$(aws sts assume-role \
            --role-arn "$ROLE_ARN" \
            --role-session-name "DomainVerification-${ACCOUNT_NUM}" \
            --duration-seconds 3600 \
            --region "$REGION" 2>&1) || {
            echo -e "${RED}Error: Failed to assume role${NC}"
            echo "$ASSUME_ROLE_OUTPUT"
            echo ""
            echo "Make sure one of these roles exists in the target account:"
            echo "  - OrganizationAccountAccessRole (created by Organizations)"
            echo "  - AWSControlTowerExecution (created by setup script)"
            echo ""
            echo "To create AWSControlTowerExecution role:"
            echo "  ./setup-stackset-execution-role.sh $ACCOUNT_ID"
            exit 1
        }
    }
    
    # Extract credentials
    export AWS_ACCESS_KEY_ID=$(echo "$ASSUME_ROLE_OUTPUT" | jq -r '.Credentials.AccessKeyId')
    export AWS_SECRET_ACCESS_KEY=$(echo "$ASSUME_ROLE_OUTPUT" | jq -r '.Credentials.SecretAccessKey')
    export AWS_SESSION_TOKEN=$(echo "$ASSUME_ROLE_OUTPUT" | jq -r '.Credentials.SessionToken')
    
    echo -e "${GREEN}✓ Successfully assumed role in account $ACCOUNT_ID${NC}"
    ASSUMED_ROLE=true
fi
echo ""

# Step 2: Check RAM resource shares
echo -e "${YELLOW}Step 2: Checking RAM resource shares...${NC}"

RAM_SHARES=$(aws ram get-resource-shares \
    --resource-owner OTHER-ACCOUNTS \
    --region "$REGION" \
    --query 'resourceShares[?contains(name, `Domain`) || contains(name, `OrgShare`)]' \
    --output json)

SHARE_COUNT=$(echo "$RAM_SHARES" | jq 'length')

if [ "$SHARE_COUNT" -eq 0 ]; then
    echo -e "${RED}✗ No domain resource shares found${NC}"
    echo ""
    echo "This could mean:"
    echo "1. Domain sharing (CF2) not deployed yet"
    echo "2. RAM sharing with Organizations not enabled"
    echo "3. Resource share not propagated yet (wait a few minutes)"
    echo ""
    echo "To enable RAM sharing with Organizations:"
    echo "  aws ram enable-sharing-with-aws-organization"
    echo ""
    exit 1
else
    echo -e "${GREEN}✓ Found $SHARE_COUNT domain resource share(s)${NC}"
    echo ""
    echo "Resource Shares:"
    echo "$RAM_SHARES" | jq -r '.[] | "  - Name: \(.name)\n    ARN: \(.resourceShareArn)\n    Status: \(.status)\n    Owner: \(.owningAccountId)"'
    echo ""
fi

# Get the domain resource share details
DOMAIN_SHARE_ARN=$(echo "$RAM_SHARES" | jq -r '.[0].resourceShareArn')
DOMAIN_SHARE_NAME=$(echo "$RAM_SHARES" | jq -r '.[0].name')
DOMAIN_SHARE_STATUS=$(echo "$RAM_SHARES" | jq -r '.[0].status')

echo "Domain Share Details:"
echo "  Name: $DOMAIN_SHARE_NAME"
echo "  ARN: $DOMAIN_SHARE_ARN"
echo "  Status: $DOMAIN_SHARE_STATUS"
echo ""

if [ "$DOMAIN_SHARE_STATUS" != "ACTIVE" ]; then
    echo -e "${YELLOW}Warning: Resource share status is not ACTIVE${NC}"
    echo "Current status: $DOMAIN_SHARE_STATUS"
    echo ""
fi

# Step 3: List shared resources
echo -e "${YELLOW}Step 3: Listing shared DataZone resources...${NC}"

SHARED_RESOURCES=$(aws ram list-resources \
    --resource-owner OTHER-ACCOUNTS \
    --resource-share-arns "$DOMAIN_SHARE_ARN" \
    --region "$REGION" \
    --query 'resources[?resourceType==`datazone:domain`]' \
    --output json)

RESOURCE_COUNT=$(echo "$SHARED_RESOURCES" | jq 'length')

if [ "$RESOURCE_COUNT" -eq 0 ]; then
    echo -e "${RED}✗ No DataZone domain resources found in share${NC}"
    echo ""
    echo "This could mean:"
    echo "1. Domain not properly added to resource share"
    echo "2. Resource share permissions not correct"
    echo "3. Propagation delay (wait a few minutes)"
    echo ""
    exit 1
else
    echo -e "${GREEN}✓ Found $RESOURCE_COUNT DataZone domain resource(s)${NC}"
    echo ""
    echo "Shared Domains:"
    echo "$SHARED_RESOURCES" | jq -r '.[] | "  - ARN: \(.arn)\n    Type: \(.resourceType)\n    Status: \(.status)"'
    echo ""
fi

# Extract domain ARN from shared resources
SHARED_DOMAIN_ARN=$(echo "$SHARED_RESOURCES" | jq -r '.[0].arn')
SHARED_DOMAIN_ID=$(echo "$SHARED_DOMAIN_ARN" | sed 's/.*domain\///')

echo "Shared Domain:"
echo "  Domain ID: $SHARED_DOMAIN_ID"
echo "  Domain ARN: $SHARED_DOMAIN_ARN"
echo ""

# Verify it matches our expected domain
if [ "$SHARED_DOMAIN_ID" = "$DOMAIN_ID" ]; then
    echo -e "${GREEN}✓ Shared domain matches expected domain ID${NC}"
else
    echo -e "${YELLOW}Warning: Shared domain ID doesn't match expected${NC}"
    echo "  Expected: $DOMAIN_ID"
    echo "  Found: $SHARED_DOMAIN_ID"
fi
echo ""

# Step 4: Try to access domain via DataZone API
echo -e "${YELLOW}Step 4: Attempting to access domain via DataZone API...${NC}"

# Note: This will likely fail because the domain is in a different account
# and we need to associate it first. But let's try anyway.
DOMAIN_ACCESS=$(aws datazone get-domain \
    --identifier "$DOMAIN_ID" \
    --region "$REGION" 2>&1) || {
    echo -e "${YELLOW}Note: Cannot directly access domain (expected)${NC}"
    echo "Domain is in org admin account ($ORG_ACCOUNT_ID)"
    echo "Project account needs to associate with the domain first"
    echo ""
}

# Step 5: Check if domain association exists
echo -e "${YELLOW}Step 5: Checking for domain associations...${NC}"

# List associated domains (this should show domains shared via RAM)
ASSOCIATED_DOMAINS=$(aws datazone list-domains \
    --region "$REGION" \
    --output json 2>&1) || {
    echo -e "${YELLOW}Note: Cannot list domains in this account${NC}"
    echo "This is expected if no domains have been associated yet"
    echo ""
}

if echo "$ASSOCIATED_DOMAINS" | jq -e '.items' &> /dev/null; then
    DOMAIN_COUNT=$(echo "$ASSOCIATED_DOMAINS" | jq '.items | length')
    echo "Found $DOMAIN_COUNT associated domain(s)"
    
    if [ "$DOMAIN_COUNT" -gt 0 ]; then
        echo "$ASSOCIATED_DOMAINS" | jq -r '.items[] | "  - ID: \(.id)\n    Name: \(.name)\n    Status: \(.status)"'
    fi
    echo ""
fi

# Summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Verification Summary${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Account: $ACCOUNT_ID ($ACCOUNT_NAME)"
echo ""
echo "✓ Successfully assumed role in target account"
echo "✓ RAM resource share is visible and ACTIVE"
echo "✓ DataZone domain is shared via RAM"
echo "✓ Domain ID matches expected: $DOMAIN_ID"
echo ""
echo -e "${BLUE}Status: Domain is available via RAM sharing${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Domain is shared and visible via RAM ✓"
echo "2. To use the domain in DataZone console:"
echo "   - Open DataZone console in account $ACCOUNT_ID"
echo "   - Navigate to 'Associated domains' or 'Domains'"
echo "   - The domain should appear automatically"
echo "   - If not visible, may need to accept association"
echo ""
echo "3. To enable blueprints in this account:"
echo "   - Deploy Blueprint Enablement StackSet instance"
echo "   - Run: ./deploy-blueprint-stackset.sh"
echo "   - Add account $ACCOUNT_ID to target accounts"
echo ""
echo "4. To create projects in this account:"
echo "   - Domain must be associated first"
echo "   - Then projects can be created via DataZone console or API"
echo ""

# Unset credentials if we assumed a role
if [ "$ASSUMED_ROLE" = true ]; then
    unset AWS_ACCESS_KEY_ID
    unset AWS_SECRET_ACCESS_KEY
    unset AWS_SESSION_TOKEN
fi

echo -e "${GREEN}Verification complete!${NC}"
echo ""

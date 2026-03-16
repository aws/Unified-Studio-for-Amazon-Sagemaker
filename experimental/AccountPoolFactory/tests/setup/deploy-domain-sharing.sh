#!/bin/bash
set -e

# Deploy CF2 - DataZone Domain Sharing Setup
# This script shares the DataZone domain with project accounts via AWS RAM

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
CONFIG_FILE="$PROJECT_ROOT/config.yaml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== CF2: DataZone Domain Sharing Setup ===${NC}"

# Load configuration
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: config.yaml not found at $CONFIG_FILE${NC}"
    exit 1
fi

# Parse config using Python
DOMAIN_ID=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['datazone']['domain_id'])")
DOMAIN_NAME=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['datazone']['domain_name'])")
DOMAIN_ARN=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['datazone']['domain_arn'])")
REGION=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['aws']['region'])")
STACK_NAME=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['stacks']['domain_sharing'])")

echo "Domain ID: $DOMAIN_ID"
echo "Domain Name: $DOMAIN_NAME"
echo "Region: $REGION"
echo "Stack Name: $STACK_NAME"

# Get list of test accounts from test-accounts directory
TEST_ACCOUNTS_DIR="$PROJECT_ROOT/tests/setup/test-accounts"
ACCOUNT_IDS=""

if [ -d "$TEST_ACCOUNTS_DIR" ]; then
    echo -e "\n${YELLOW}Finding test accounts...${NC}"
    for file in "$TEST_ACCOUNTS_DIR"/test-account-provision-*.json; do
        if [ -f "$file" ]; then
            ACCOUNT_ID=$(jq -r '.accountId' "$file" 2>/dev/null || echo "")
            if [ -n "$ACCOUNT_ID" ] && [ "$ACCOUNT_ID" != "null" ]; then
                if [ -z "$ACCOUNT_IDS" ]; then
                    ACCOUNT_IDS="$ACCOUNT_ID"
                else
                    ACCOUNT_IDS="$ACCOUNT_IDS,$ACCOUNT_ID"
                fi
                echo "  Found account: $ACCOUNT_ID"
            fi
        fi
    done
fi

if [ -z "$ACCOUNT_IDS" ]; then
    echo -e "${YELLOW}No test accounts found. You can specify accounts manually:${NC}"
    echo "  ./deploy-domain-sharing.sh 123456789012,234567890123"
    echo ""
    echo -e "${YELLOW}Or deploy without accounts (can add later):${NC}"
    read -p "Deploy without accounts? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    ACCOUNT_IDS=""
else
    echo -e "\n${GREEN}Found ${ACCOUNT_IDS//,/ } accounts${NC}"
fi

# Allow override from command line
if [ -n "$1" ]; then
    ACCOUNT_IDS="$1"
    echo -e "${YELLOW}Using accounts from command line: $ACCOUNT_IDS${NC}"
fi

# Refresh AWS credentials
echo -e "\n${YELLOW}Refreshing AWS credentials...${NC}"
eval $(isengardcli creds amirbo+1 --role Admin)

# Deploy CloudFormation stack
echo -e "\n${YELLOW}Deploying CloudFormation stack...${NC}"

TEMPLATE_FILE="$PROJECT_ROOT/02-domain-account/templates/cloudformation/01-infrastructure.yaml"

if [ -z "$ACCOUNT_IDS" ]; then
    # Deploy without accounts
    aws cloudformation deploy \
        --template-file "$TEMPLATE_FILE" \
        --stack-name "$STACK_NAME" \
        --parameter-overrides \
            DomainId="$DOMAIN_ID" \
            DomainName="$DOMAIN_NAME" \
            DomainArn="$DOMAIN_ARN" \
            EnableSharing="false" \
        --region "$REGION" \
        --no-fail-on-empty-changeset
else
    # Deploy with accounts
    aws cloudformation deploy \
        --template-file "$TEMPLATE_FILE" \
        --stack-name "$STACK_NAME" \
        --parameter-overrides \
            DomainId="$DOMAIN_ID" \
            DomainName="$DOMAIN_NAME" \
            DomainArn="$DOMAIN_ARN" \
            ProjectAccountIds="$ACCOUNT_IDS" \
            EnableSharing="true" \
        --region "$REGION" \
        --no-fail-on-empty-changeset
fi

# Get stack outputs
echo -e "\n${YELLOW}Getting stack outputs...${NC}"
aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs' \
    --output table

# Verify RAM shares were created
if [ -n "$ACCOUNT_IDS" ]; then
    echo -e "\n${YELLOW}Verifying RAM shares...${NC}"
    aws ram get-resource-shares \
        --resource-owner SELF \
        --region "$REGION" \
        --query "resourceShares[?contains(name, 'DataZone-$DOMAIN_NAME')].[name,status,resourceShareArn]" \
        --output table
    
    # Check resources associated with shares
    echo -e "\n${YELLOW}Checking resources in RAM shares...${NC}"
    SHARE_ARNS=$(aws ram get-resource-shares \
        --resource-owner SELF \
        --region "$REGION" \
        --query "resourceShares[?contains(name, 'DataZone-$DOMAIN_NAME')].resourceShareArn" \
        --output text)
    
    for SHARE_ARN in $SHARE_ARNS; do
        echo -e "\n${GREEN}Share: $SHARE_ARN${NC}"
        aws ram list-resources \
            --resource-owner SELF \
            --resource-share-arns "$SHARE_ARN" \
            --region "$REGION" \
            --query 'resources[*].[arn,type,status]' \
            --output table || echo "  No resources found"
    done
fi

echo -e "\n${GREEN}=== CF2 Deployment Complete ===${NC}"
echo ""
echo "Next steps:"
echo "1. Verify domain is visible in project accounts"
echo "2. Test domain association acceptance (if needed)"
echo "3. Enable blueprints in domain account"
echo ""
echo "To verify in project account:"
echo "  aws datazone list-domains --region $REGION"

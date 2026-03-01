#!/bin/bash

# Test Script: Create Account via Control Tower Account Factory
# This script tests the CF1 setup by creating a new AWS account

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

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Test: Create Account via Control Tower${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check config
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: Configuration file not found: $CONFIG_FILE${NC}"
    exit 1
fi

# Read configuration
get_config_value() {
    local key=$1
    if command -v yq &> /dev/null; then
        yq eval "$key" "$CONFIG_FILE"
    else
        grep "^${key##*.}:" "$CONFIG_FILE" | sed 's/.*: //' | tr -d '"' | tr -d "'"
    fi
}

REGION=$(get_config_value '.aws.region')
ACCOUNT_ID=$(get_config_value '.aws.account_id')
TARGET_OU_ID=$(get_config_value '.organization.target_ou_id')
CF1_STACK_NAME="AccountPoolFactory-ControlTower-Test"

echo "Configuration:"
echo "  Region: $REGION"
echo "  Account ID: $ACCOUNT_ID"
echo "  Target OU: $TARGET_OU_ID"
echo "  CF1 Stack: $CF1_STACK_NAME"
echo ""

# Check if CF1 stack exists
echo -e "${YELLOW}Checking CF1 stack...${NC}"
if ! aws cloudformation describe-stacks \
    --stack-name "$CF1_STACK_NAME" \
    --region "$REGION" &> /dev/null; then
    echo -e "${RED}Error: CF1 stack not found: $CF1_STACK_NAME${NC}"
    exit 1
fi
echo -e "${GREEN}✓ CF1 stack exists${NC}"
echo ""

# Get Control Tower Product ID
echo -e "${YELLOW}Finding Control Tower Account Factory product...${NC}"
PRODUCT_ID=$(aws servicecatalog search-products \
    --region "$REGION" \
    --filters "FullTextSearch=AWS Control Tower Account Factory" \
    --query 'ProductViewSummaries[0].ProductId' \
    --output text)

if [ -z "$PRODUCT_ID" ] || [ "$PRODUCT_ID" = "None" ]; then
    echo -e "${RED}Error: Control Tower Account Factory product not found${NC}"
    echo "This account may not have Control Tower enabled."
    echo "For testing purposes, we'll simulate account creation."
    exit 1
fi

echo -e "${GREEN}✓ Found Product ID: $PRODUCT_ID${NC}"

# Get provisioning artifact (latest version)
ARTIFACT_ID=$(aws servicecatalog describe-product \
    --id "$PRODUCT_ID" \
    --region "$REGION" \
    --query 'ProvisioningArtifacts[0].Id' \
    --output text)

echo -e "${GREEN}✓ Found Artifact ID: $ARTIFACT_ID${NC}"
echo ""

# Find next available email number
echo -e "${YELLOW}Finding next available email number...${NC}"
EMAIL_BASE="amirbo"
EMAIL_DOMAIN="amazon.com"
EMAIL_NUM=100

# Check existing provision files to find highest number used
if ls "$PROJECT_ROOT"/test-account-provision-*.json 1> /dev/null 2>&1; then
    HIGHEST_NUM=$(ls "$PROJECT_ROOT"/test-account-provision-*.json | \
        sed 's/.*provision-\([0-9]*\)\.json/\1/' | \
        sort -n | tail -1)
    EMAIL_NUM=$((HIGHEST_NUM + 1))
fi

# Verify email is not already in use in Organizations
while true; do
    TEST_EMAIL="${EMAIL_BASE}+${EMAIL_NUM}@${EMAIL_DOMAIN}"
    
    # Check if email exists in Organizations
    EXISTING_ACCOUNT=$(aws organizations list-accounts \
        --region "$REGION" \
        --query "Accounts[?Email=='${TEST_EMAIL}'].Id" \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$EXISTING_ACCOUNT" ]; then
        break
    fi
    
    echo "  Email ${TEST_EMAIL} already in use, trying next..."
    EMAIL_NUM=$((EMAIL_NUM + 1))
done

echo -e "${GREEN}✓ Using email number: $EMAIL_NUM${NC}"

# Generate account details
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
ACCOUNT_NAME="test-account-${EMAIL_NUM}"
ACCOUNT_EMAIL="${EMAIL_BASE}+${EMAIL_NUM}@${EMAIL_DOMAIN}"
SSO_USER_EMAIL="${EMAIL_BASE}+${EMAIL_NUM}-admin@${EMAIL_DOMAIN}"
SSO_USER_FIRSTNAME="Test"
SSO_USER_LASTNAME="Admin${EMAIL_NUM}"

echo -e "${BLUE}Account Details:${NC}"
echo "  Name: $ACCOUNT_NAME"
echo "  Email: $ACCOUNT_EMAIL"
echo "  SSO User: $SSO_USER_EMAIL"
echo "  Target OU: $TARGET_OU_ID"
echo ""

# Confirm with user
read -p "Create this account? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo -e "${YELLOW}Provisioning account via Service Catalog...${NC}"

# Provision the account
PROVISION_TOKEN="provision-${TIMESTAMP}"
PROVISION_OUTPUT=$(aws servicecatalog provision-product \
    --product-id "$PRODUCT_ID" \
    --provisioning-artifact-id "$ARTIFACT_ID" \
    --provisioned-product-name "$ACCOUNT_NAME" \
    --provisioning-token "$PROVISION_TOKEN" \
    --provisioning-parameters \
        Key=AccountName,Value="$ACCOUNT_NAME" \
        Key=AccountEmail,Value="$ACCOUNT_EMAIL" \
        Key=SSOUserEmail,Value="$SSO_USER_EMAIL" \
        Key=SSOUserFirstName,Value="$SSO_USER_FIRSTNAME" \
        Key=SSOUserLastName,Value="$SSO_USER_LASTNAME" \
        Key=ManagedOrganizationalUnit,Value="$TARGET_OU_ID" \
    --region "$REGION" \
    --output json)

RECORD_ID=$(echo "$PROVISION_OUTPUT" | jq -r '.RecordDetail.RecordId')

if [ -z "$RECORD_ID" ] || [ "$RECORD_ID" = "null" ]; then
    echo -e "${RED}Error: Failed to provision account${NC}"
    echo "$PROVISION_OUTPUT"
    exit 1
fi

echo -e "${GREEN}✓ Provisioning started${NC}"
echo "  Record ID: $RECORD_ID"
echo ""

# Save provisioning details with email number in filename
PROVISION_FILE="$PROJECT_ROOT/test-account-provision-${EMAIL_NUM}.json"
cat > "$PROVISION_FILE" <<EOF
{
  "emailNumber": $EMAIL_NUM,
  "timestamp": "$TIMESTAMP",
  "accountName": "$ACCOUNT_NAME",
  "accountEmail": "$ACCOUNT_EMAIL",
  "recordId": "$RECORD_ID",
  "productId": "$PRODUCT_ID",
  "artifactId": "$ARTIFACT_ID",
  "targetOuId": "$TARGET_OU_ID",
  "region": "$REGION",
  "status": "PROVISIONING"
}
EOF

echo -e "${GREEN}✓ Provisioning details saved to: $PROVISION_FILE${NC}"
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Provisioning Started (Async)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Account provisioning is running in the background."
echo "This process takes 5-10 minutes."
echo ""
echo "You can:"
echo "1. Wait here and monitor progress"
echo "2. Press Ctrl+C to exit (provisioning continues)"
echo "3. Check status later with: ./tests/setup/scripts/test-check-status.sh $EMAIL_NUM"
echo ""
read -p "Monitor provisioning now? (yes/no): " MONITOR

if [ "$MONITOR" != "yes" ]; then
    echo ""
    echo "Provisioning continues in background."
    echo "Check status with: ./tests/setup/scripts/test-check-status.sh $EMAIL_NUM"
    exit 0
fi

# Monitor provisioning status
echo -e "${YELLOW}Monitoring provisioning status...${NC}"
echo "This may take 5-10 minutes. Press Ctrl+C to stop monitoring (provisioning will continue)."
echo ""

COUNTER=0
while true; do
    RECORD_STATUS=$(aws servicecatalog describe-record \
        --id "$RECORD_ID" \
        --region "$REGION" \
        --query 'RecordDetail.Status' \
        --output text)
    
    COUNTER=$((COUNTER + 1))
    echo -e "${BLUE}[$COUNTER] Status: $RECORD_STATUS${NC}"
    
    if [ "$RECORD_STATUS" = "SUCCEEDED" ]; then
        echo ""
        echo -e "${GREEN}✓ Account provisioning completed successfully!${NC}"
        
        # Update status in provision file
        jq '.status = "SUCCEEDED"' "$PROVISION_FILE" > "${PROVISION_FILE}.tmp"
        mv "${PROVISION_FILE}.tmp" "$PROVISION_FILE"
        
        break
    elif [ "$RECORD_STATUS" = "FAILED" ] || [ "$RECORD_STATUS" = "ERROR" ]; then
        echo ""
        echo -e "${RED}✗ Account provisioning failed${NC}"
        
        # Update status in provision file
        jq '.status = "FAILED"' "$PROVISION_FILE" > "${PROVISION_FILE}.tmp"
        mv "${PROVISION_FILE}.tmp" "$PROVISION_FILE"
        
        # Get error details
        aws servicecatalog describe-record \
            --id "$RECORD_ID" \
            --region "$REGION" \
            --query 'RecordDetail.RecordErrors' \
            --output table
        
        exit 1
    fi
    
    sleep 30
done

echo ""
echo -e "${YELLOW}Getting account details...${NC}"

# Get the provisioned product details
PROVISIONED_PRODUCT=$(aws servicecatalog describe-record \
    --id "$RECORD_ID" \
    --region "$REGION" \
    --query 'RecordOutputs' \
    --output json)

echo "$PROVISIONED_PRODUCT" | jq '.'

# Try to extract account ID from outputs
NEW_ACCOUNT_ID=$(echo "$PROVISIONED_PRODUCT" | jq -r '.[] | select(.OutputKey=="AccountId") | .OutputValue')

if [ -n "$NEW_ACCOUNT_ID" ] && [ "$NEW_ACCOUNT_ID" != "null" ]; then
    echo ""
    echo -e "${GREEN}✓ New Account ID: $NEW_ACCOUNT_ID${NC}"
    
    # Update provision file with account ID
    jq --arg aid "$NEW_ACCOUNT_ID" '.accountId = $aid' "$PROVISION_FILE" > "${PROVISION_FILE}.tmp"
    mv "${PROVISION_FILE}.tmp" "$PROVISION_FILE"
    
    # Verify account in Organizations
    echo ""
    echo -e "${YELLOW}Verifying account in Organizations...${NC}"
    
    ACCOUNT_INFO=$(aws organizations describe-account \
        --account-id "$NEW_ACCOUNT_ID" \
        --region "$REGION" \
        --output json 2>/dev/null || echo "{}")
    
    if [ "$ACCOUNT_INFO" != "{}" ]; then
        echo -e "${GREEN}✓ Account found in Organizations${NC}"
        echo "$ACCOUNT_INFO" | jq '.Account | {Id, Name, Email, Status, JoinedMethod}'
    fi
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Account Creation Test Complete${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Summary:"
echo "  Email Number: $EMAIL_NUM"
echo "  Account Name: $ACCOUNT_NAME"
echo "  Account Email: $ACCOUNT_EMAIL"
if [ -n "$NEW_ACCOUNT_ID" ] && [ "$NEW_ACCOUNT_ID" != "null" ]; then
    echo "  Account ID: $NEW_ACCOUNT_ID"
fi
echo "  Record ID: $RECORD_ID"
echo "  Provision File: $PROVISION_FILE"
echo ""
echo "Next Steps:"
echo "1. Verify account: ./tests/setup/scripts/test-verify-account.sh $EMAIL_NUM"
echo "2. Check status anytime: ./tests/setup/scripts/test-check-status.sh $EMAIL_NUM"
echo "3. When done testing: ./tests/setup/scripts/test-delete-account.sh $EMAIL_NUM"
echo ""

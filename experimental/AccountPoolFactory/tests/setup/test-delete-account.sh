#!/bin/bash

# Test Script: Delete Test Account
# This script deletes the test account created by test-create-account.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Get email number from argument or find latest
EMAIL_NUM="$1"

if [ -z "$EMAIL_NUM" ]; then
    # Find latest provision file
    if ls "$PROJECT_ROOT"/test-account-provision-*.json 1> /dev/null 2>&1; then
        LATEST_FILE=$(ls -t "$PROJECT_ROOT"/test-account-provision-*.json | head -1)
        EMAIL_NUM=$(basename "$LATEST_FILE" | sed 's/test-account-provision-\([0-9]*\)\.json/\1/')
        echo "No email number provided, using latest: $EMAIL_NUM"
        echo ""
    else
        echo -e "${RED}Error: No provision files found${NC}"
        echo "Usage: $0 [EMAIL_NUMBER]"
        exit 1
    fi
fi

PROVISION_FILE="$PROJECT_ROOT/test-account-provision-${EMAIL_NUM}.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${RED}========================================${NC}"
echo -e "${RED}Test: Delete Account${NC}"
echo -e "${RED}========================================${NC}"
echo ""

# Check if provision file exists
if [ ! -f "$PROVISION_FILE" ]; then
    echo -e "${RED}Error: Provision file not found: $PROVISION_FILE${NC}"
    echo "No test account to delete."
    exit 1
fi

# Read provision details
ACCOUNT_NAME=$(jq -r '.accountName' "$PROVISION_FILE")
ACCOUNT_EMAIL=$(jq -r '.accountEmail' "$PROVISION_FILE")
ACCOUNT_ID=$(jq -r '.accountId // "unknown"' "$PROVISION_FILE")
RECORD_ID=$(jq -r '.recordId' "$PROVISION_FILE")
REGION=$(jq -r '.region' "$PROVISION_FILE")

echo "Test Account Details:"
echo "  Name: $ACCOUNT_NAME"
echo "  Email: $ACCOUNT_EMAIL"
echo "  Account ID: $ACCOUNT_ID"
echo "  Record ID: $RECORD_ID"
echo "  Region: $REGION"
echo ""

# Warning
echo -e "${RED}WARNING: This will delete the test account!${NC}"
echo -e "${RED}This action cannot be undone.${NC}"
echo ""
read -p "Are you sure you want to delete this account? (type 'DELETE' to confirm): " CONFIRM

if [ "$CONFIRM" != "DELETE" ]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo -e "${YELLOW}Terminating provisioned product...${NC}"

# Get provisioned product ID
PROVISIONED_PRODUCT_ID=$(aws servicecatalog describe-record \
    --id "$RECORD_ID" \
    --region "$REGION" \
    --query 'RecordDetail.ProvisionedProductId' \
    --output text 2>/dev/null || echo "")

if [ -z "$PROVISIONED_PRODUCT_ID" ] || [ "$PROVISIONED_PRODUCT_ID" = "None" ]; then
    echo -e "${YELLOW}Warning: Could not find provisioned product ID from record${NC}"
    echo "Trying to find by name..."
    
    PROVISIONED_PRODUCT_ID=$(aws servicecatalog search-provisioned-products \
        --region "$REGION" \
        --filters "SearchQuery=$ACCOUNT_NAME" \
        --query 'ProvisionedProducts[0].Id' \
        --output text 2>/dev/null || echo "")
fi

if [ -z "$PROVISIONED_PRODUCT_ID" ] || [ "$PROVISIONED_PRODUCT_ID" = "None" ]; then
    echo -e "${RED}Error: Could not find provisioned product to terminate${NC}"
    echo "The account may have already been deleted or the provisioning failed."
    echo ""
    read -p "Delete the provision file anyway? (yes/no): " DELETE_FILE
    if [ "$DELETE_FILE" = "yes" ]; then
        rm -f "$PROVISION_FILE"
        echo -e "${GREEN}✓ Provision file deleted${NC}"
    fi
    exit 1
fi

echo -e "${GREEN}✓ Found Provisioned Product ID: $PROVISIONED_PRODUCT_ID${NC}"
echo ""

# Terminate the provisioned product
echo -e "${YELLOW}Terminating provisioned product...${NC}"

TERMINATE_OUTPUT=$(aws servicecatalog terminate-provisioned-product \
    --provisioned-product-id "$PROVISIONED_PRODUCT_ID" \
    --region "$REGION" \
    --output json)

TERMINATE_RECORD_ID=$(echo "$TERMINATE_OUTPUT" | jq -r '.RecordDetail.RecordId')

if [ -z "$TERMINATE_RECORD_ID" ] || [ "$TERMINATE_RECORD_ID" = "null" ]; then
    echo -e "${RED}Error: Failed to terminate provisioned product${NC}"
    echo "$TERMINATE_OUTPUT"
    exit 1
fi

echo -e "${GREEN}✓ Termination started${NC}"
echo "  Termination Record ID: $TERMINATE_RECORD_ID"
echo ""

# Monitor termination status
echo -e "${YELLOW}Monitoring termination status...${NC}"
echo "This may take several minutes. Press Ctrl+C to stop monitoring (termination will continue)."
echo ""

COUNTER=0
while true; do
    RECORD_STATUS=$(aws servicecatalog describe-record \
        --id "$TERMINATE_RECORD_ID" \
        --region "$REGION" \
        --query 'RecordDetail.Status' \
        --output text 2>/dev/null || echo "UNKNOWN")
    
    COUNTER=$((COUNTER + 1))
    echo -e "${BLUE}[$COUNTER] Status: $RECORD_STATUS${NC}"
    
    if [ "$RECORD_STATUS" = "SUCCEEDED" ]; then
        echo ""
        echo -e "${GREEN}✓ Account termination completed successfully!${NC}"
        break
    elif [ "$RECORD_STATUS" = "FAILED" ] || [ "$RECORD_STATUS" = "ERROR" ]; then
        echo ""
        echo -e "${RED}✗ Account termination failed${NC}"
        
        # Get error details
        aws servicecatalog describe-record \
            --id "$TERMINATE_RECORD_ID" \
            --region "$REGION" \
            --query 'RecordDetail.RecordErrors' \
            --output table
        
        echo ""
        echo "The account may need to be closed manually in AWS Organizations."
        exit 1
    elif [ "$RECORD_STATUS" = "UNKNOWN" ]; then
        echo ""
        echo -e "${YELLOW}Warning: Could not get termination status${NC}"
        echo "The termination may still be in progress."
        break
    fi
    
    sleep 30
done

# Note about account closure
echo ""
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Important Notes${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""
echo "Control Tower Account Factory termination:"
echo "1. Removes the account from Control Tower management"
echo "2. Moves the account to the root of the organization"
echo "3. Does NOT close the AWS account"
echo ""
echo "To fully close the account:"
echo "1. Sign in to the account as root user"
echo "2. Go to Account Settings"
echo "3. Close the account"
echo ""
echo "Or use AWS Organizations to close it:"
echo "  aws organizations close-account --account-id $ACCOUNT_ID --region $REGION"
echo ""

# Ask if user wants to close the account
if [ "$ACCOUNT_ID" != "unknown" ] && [ -n "$ACCOUNT_ID" ]; then
    read -p "Do you want to close the account now? (yes/no): " CLOSE_ACCOUNT
    
    if [ "$CLOSE_ACCOUNT" = "yes" ]; then
        echo ""
        echo -e "${YELLOW}Closing account...${NC}"
        
        if aws organizations close-account \
            --account-id "$ACCOUNT_ID" \
            --region "$REGION" 2>/dev/null; then
            echo -e "${GREEN}✓ Account closure initiated${NC}"
            echo "The account will be closed within 90 days."
        else
            echo -e "${RED}✗ Failed to close account${NC}"
            echo "You may need to close it manually."
        fi
    fi
fi

# Delete provision file
echo ""
read -p "Delete the provision file? (yes/no): " DELETE_FILE
if [ "$DELETE_FILE" = "yes" ]; then
    rm -f "$PROVISION_FILE"
    echo -e "${GREEN}✓ Provision file deleted: $PROVISION_FILE${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Account Deletion Complete${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

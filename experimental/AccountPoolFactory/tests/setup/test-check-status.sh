#!/bin/bash

# Test Script: Check Account Provisioning Status
# This script checks the status of an account being provisioned

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Check Account Provisioning Status${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

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

# Check if provision file exists
if [ ! -f "$PROVISION_FILE" ]; then
    echo -e "${RED}Error: Provision file not found: $PROVISION_FILE${NC}"
    echo ""
    echo "Available provision files:"
    ls -1 "$PROJECT_ROOT"/test-account-provision-*.json 2>/dev/null | sed 's/.*provision-/  /' | sed 's/\.json//' || echo "  None"
    exit 1
fi

# Read provision details
ACCOUNT_NAME=$(jq -r '.accountName' "$PROVISION_FILE")
ACCOUNT_EMAIL=$(jq -r '.accountEmail' "$PROVISION_FILE")
ACCOUNT_ID=$(jq -r '.accountId // "unknown"' "$PROVISION_FILE")
RECORD_ID=$(jq -r '.recordId' "$PROVISION_FILE")
REGION=$(jq -r '.region' "$PROVISION_FILE")
SAVED_STATUS=$(jq -r '.status // "UNKNOWN"' "$PROVISION_FILE")

echo "Account Details:"
echo "  Email Number: $EMAIL_NUM"
echo "  Name: $ACCOUNT_NAME"
echo "  Email: $ACCOUNT_EMAIL"
echo "  Account ID: $ACCOUNT_ID"
echo "  Saved Status: $SAVED_STATUS"
echo ""

# Check current status from AWS
echo -e "${YELLOW}Checking current status from AWS...${NC}"

RECORD_STATUS=$(aws servicecatalog describe-record \
    --id "$RECORD_ID" \
    --region "$REGION" \
    --query 'RecordDetail.Status' \
    --output text 2>/dev/null || echo "UNKNOWN")

echo "  Current Status: $RECORD_STATUS"
echo ""

# Update status in file if changed
if [ "$RECORD_STATUS" != "$SAVED_STATUS" ] && [ "$RECORD_STATUS" != "UNKNOWN" ]; then
    jq --arg status "$RECORD_STATUS" '.status = $status' "$PROVISION_FILE" > "${PROVISION_FILE}.tmp"
    mv "${PROVISION_FILE}.tmp" "$PROVISION_FILE"
    echo -e "${BLUE}✓ Status updated in provision file${NC}"
    echo ""
fi

# Show status-specific information
case "$RECORD_STATUS" in
    "IN_PROGRESS"|"IN_PROGRESS_IN_ERROR")
        echo -e "${YELLOW}⏳ Provisioning is still in progress...${NC}"
        echo ""
        echo "Estimated time remaining: 5-10 minutes"
        echo ""
        echo "You can:"
        echo "1. Wait and check again: ./tests/setup/scripts/test-check-status.sh $EMAIL_NUM"
        echo "2. Monitor continuously: watch -n 30 './tests/setup/scripts/test-check-status.sh $EMAIL_NUM'"
        ;;
    
    "SUCCEEDED")
        echo -e "${GREEN}✓ Provisioning completed successfully!${NC}"
        echo ""
        
        # Get account ID if not already saved
        if [ "$ACCOUNT_ID" = "unknown" ]; then
            echo -e "${YELLOW}Retrieving account ID...${NC}"
            
            PROVISIONED_PRODUCT=$(aws servicecatalog describe-record \
                --id "$RECORD_ID" \
                --region "$REGION" \
                --query 'RecordOutputs' \
                --output json 2>/dev/null || echo "[]")
            
            NEW_ACCOUNT_ID=$(echo "$PROVISIONED_PRODUCT" | jq -r '.[] | select(.OutputKey=="AccountId") | .OutputValue')
            
            if [ -n "$NEW_ACCOUNT_ID" ] && [ "$NEW_ACCOUNT_ID" != "null" ]; then
                echo -e "${GREEN}✓ Account ID: $NEW_ACCOUNT_ID${NC}"
                
                # Update provision file
                jq --arg aid "$NEW_ACCOUNT_ID" '.accountId = $aid' "$PROVISION_FILE" > "${PROVISION_FILE}.tmp"
                mv "${PROVISION_FILE}.tmp" "$PROVISION_FILE"
                
                ACCOUNT_ID="$NEW_ACCOUNT_ID"
            fi
            echo ""
        fi
        
        echo "Next Steps:"
        echo "1. Verify account: ./tests/setup/scripts/test-verify-account.sh $EMAIL_NUM"
        echo "2. Test deploying StackSets to this account"
        echo "3. When done: ./tests/setup/scripts/test-delete-account.sh $EMAIL_NUM"
        ;;
    
    "FAILED"|"ERROR")
        echo -e "${RED}✗ Provisioning failed${NC}"
        echo ""
        
        # Get error details
        echo "Error details:"
        aws servicecatalog describe-record \
            --id "$RECORD_ID" \
            --region "$REGION" \
            --query 'RecordDetail.RecordErrors' \
            --output table 2>/dev/null || echo "Could not retrieve error details"
        
        echo ""
        echo "You may need to:"
        echo "1. Review the error above"
        echo "2. Delete the failed provisioning: ./tests/setup/scripts/test-delete-account.sh $EMAIL_NUM"
        echo "3. Try creating a new account"
        ;;
    
    "UNKNOWN")
        echo -e "${RED}✗ Could not retrieve status from AWS${NC}"
        echo ""
        echo "This could mean:"
        echo "1. The provisioning record no longer exists"
        echo "2. AWS credentials expired"
        echo "3. Network connectivity issue"
        ;;
    
    *)
        echo -e "${YELLOW}Status: $RECORD_STATUS${NC}"
        ;;
esac

# Show account info if available
if [ "$ACCOUNT_ID" != "unknown" ] && [ -n "$ACCOUNT_ID" ]; then
    echo ""
    echo -e "${BLUE}Account Information:${NC}"
    
    ACCOUNT_INFO=$(aws organizations describe-account \
        --account-id "$ACCOUNT_ID" \
        --region "$REGION" \
        --output json 2>/dev/null || echo "{}")
    
    if [ "$ACCOUNT_INFO" != "{}" ]; then
        echo "$ACCOUNT_INFO" | jq '.Account | {Id, Name, Email, Status, JoinedMethod, JoinedTimestamp}'
    else
        echo "  Could not retrieve account information"
    fi
fi

echo ""

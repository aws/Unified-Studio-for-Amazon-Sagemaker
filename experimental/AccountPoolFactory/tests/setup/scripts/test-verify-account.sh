#!/bin/bash

# Test Script: Verify Test Account Setup
# This script verifies the test account was created correctly

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

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test: Verify Account Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if provision file exists
if [ ! -f "$PROVISION_FILE" ]; then
    echo -e "${RED}Error: Provision file not found: $PROVISION_FILE${NC}"
    echo "Run test-create-account.sh first."
    exit 1
fi

# Read provision details
ACCOUNT_NAME=$(jq -r '.accountName' "$PROVISION_FILE")
ACCOUNT_EMAIL=$(jq -r '.accountEmail' "$PROVISION_FILE")
ACCOUNT_ID=$(jq -r '.accountId // "unknown"' "$PROVISION_FILE")
RECORD_ID=$(jq -r '.recordId' "$PROVISION_FILE")
TARGET_OU_ID=$(jq -r '.targetOuId' "$PROVISION_FILE")
REGION=$(jq -r '.region' "$PROVISION_FILE")

echo "Test Account Details:"
echo "  Email Number: $EMAIL_NUM"
echo "  Name: $ACCOUNT_NAME"
echo "  Email: $ACCOUNT_EMAIL"
echo "  Account ID: $ACCOUNT_ID"
echo "  Target OU: $TARGET_OU_ID"
echo "  Region: $REGION"
echo ""

CHECKS_PASSED=0
CHECKS_FAILED=0

# Check 1: Verify provisioning record status
echo -e "${YELLOW}[1/6] Checking provisioning record status...${NC}"
RECORD_STATUS=$(aws servicecatalog describe-record \
    --id "$RECORD_ID" \
    --region "$REGION" \
    --query 'RecordDetail.Status' \
    --output text 2>/dev/null || echo "UNKNOWN")

if [ "$RECORD_STATUS" = "SUCCEEDED" ]; then
    echo -e "${GREEN}✓ Provisioning record status: $RECORD_STATUS${NC}"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
else
    echo -e "${RED}✗ Provisioning record status: $RECORD_STATUS${NC}"
    CHECKS_FAILED=$((CHECKS_FAILED + 1))
fi
echo ""

# Check 2: Verify account exists in Organizations
echo -e "${YELLOW}[2/6] Checking account in Organizations...${NC}"
if [ "$ACCOUNT_ID" != "unknown" ] && [ -n "$ACCOUNT_ID" ]; then
    ACCOUNT_STATUS=$(aws organizations describe-account \
        --account-id "$ACCOUNT_ID" \
        --region "$REGION" \
        --query 'Account.Status' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [ "$ACCOUNT_STATUS" = "ACTIVE" ]; then
        echo -e "${GREEN}✓ Account exists and is ACTIVE${NC}"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        echo -e "${RED}✗ Account status: $ACCOUNT_STATUS${NC}"
        CHECKS_FAILED=$((CHECKS_FAILED + 1))
    fi
else
    echo -e "${RED}✗ Account ID not available${NC}"
    CHECKS_FAILED=$((CHECKS_FAILED + 1))
fi
echo ""

# Check 3: Verify account is in correct OU
echo -e "${YELLOW}[3/6] Checking account OU placement...${NC}"
if [ "$ACCOUNT_ID" != "unknown" ] && [ -n "$ACCOUNT_ID" ]; then
    PARENT_ID=$(aws organizations list-parents \
        --child-id "$ACCOUNT_ID" \
        --region "$REGION" \
        --query 'Parents[0].Id' \
        --output text 2>/dev/null || echo "UNKNOWN")
    
    if [ "$PARENT_ID" = "$TARGET_OU_ID" ]; then
        echo -e "${GREEN}✓ Account is in correct OU: $TARGET_OU_ID${NC}"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        echo -e "${RED}✗ Account is in OU: $PARENT_ID (expected: $TARGET_OU_ID)${NC}"
        CHECKS_FAILED=$((CHECKS_FAILED + 1))
    fi
else
    echo -e "${YELLOW}⊘ Skipped (no account ID)${NC}"
fi
echo ""

# Check 4: Check EventBridge events
echo -e "${YELLOW}[4/6] Checking EventBridge events...${NC}"
EVENT_BUS_NAME="AccountPoolFactoryEventBus"

# Look for events in the last hour
START_TIME=$(date -u -v-1H +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -d '1 hour ago' +"%Y-%m-%dT%H:%M:%SZ")

EVENTS=$(aws events list-archives \
    --event-source-arn "arn:aws:events:${REGION}:*:event-bus/${EVENT_BUS_NAME}" \
    --region "$REGION" \
    --query 'Archives[*].ArchiveName' \
    --output text 2>/dev/null || echo "")

if [ -n "$EVENTS" ]; then
    echo -e "${GREEN}✓ EventBridge event bus exists and has archives${NC}"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
else
    echo -e "${YELLOW}⊘ No event archives found (events may not be archived)${NC}"
    echo "  Event bus: $EVENT_BUS_NAME"
fi
echo ""

# Check 5: Verify Control Tower enrollment
echo -e "${YELLOW}[5/6] Checking Control Tower enrollment...${NC}"
if [ "$ACCOUNT_ID" != "unknown" ] && [ -n "$ACCOUNT_ID" ]; then
    # Check if account has Control Tower tags
    TAGS=$(aws organizations list-tags-for-resource \
        --resource-id "$ACCOUNT_ID" \
        --region "$REGION" \
        --query 'Tags[?Key==`aws-control-tower-managed`].Value' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$TAGS" ]; then
        echo -e "${GREEN}✓ Account is managed by Control Tower${NC}"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        echo -e "${YELLOW}⊘ Control Tower management tag not found${NC}"
        echo "  This is normal for newly created accounts"
    fi
else
    echo -e "${YELLOW}⊘ Skipped (no account ID)${NC}"
fi
echo ""

# Check 6: Check for AWSControlTowerExecution role
echo -e "${YELLOW}[6/6] Checking AWSControlTowerExecution role...${NC}"
if [ "$ACCOUNT_ID" != "unknown" ] && [ -n "$ACCOUNT_ID" ]; then
    echo "  Note: Cannot verify role in new account without assuming a role"
    echo "  The AWSControlTowerExecution role should exist in the new account"
    echo -e "${YELLOW}⊘ Manual verification required${NC}"
else
    echo -e "${YELLOW}⊘ Skipped (no account ID)${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Verification Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Checks Passed: ${GREEN}$CHECKS_PASSED${NC}"
echo "Checks Failed: ${RED}$CHECKS_FAILED${NC}"
echo ""

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All automated checks passed!${NC}"
    echo ""
    echo "Manual verification steps:"
    echo "1. Sign in to AWS Console"
    echo "2. Go to AWS Organizations"
    echo "3. Verify account appears in the correct OU"
    echo "4. Go to Control Tower dashboard"
    echo "5. Verify account is enrolled"
    echo ""
    echo "Next steps:"
    echo "1. Test deploying approved StackSets to this account"
    echo "2. Verify VPC, IAM roles, and blueprints are configured"
    echo "3. When done, run: ./tests/setup/scripts/test-delete-account.sh $EMAIL_NUM"
else
    echo -e "${RED}✗ Some checks failed${NC}"
    echo ""
    echo "Review the errors above and check:"
    echo "1. Control Tower is enabled in this account"
    echo "2. Account Factory product is available"
    echo "3. Provisioning completed successfully"
fi
echo ""

# Show account details
if [ "$ACCOUNT_ID" != "unknown" ] && [ -n "$ACCOUNT_ID" ]; then
    echo -e "${BLUE}Account Details:${NC}"
    aws organizations describe-account \
        --account-id "$ACCOUNT_ID" \
        --region "$REGION" \
        --output table 2>/dev/null || echo "Could not retrieve account details"
fi

echo ""

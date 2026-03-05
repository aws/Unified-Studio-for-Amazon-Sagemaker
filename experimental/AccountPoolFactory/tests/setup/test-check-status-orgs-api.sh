#!/bin/bash

# Check status of Organizations API account creation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load configuration
if [ -f "$PROJECT_ROOT/config.yaml" ]; then
    REGION=$(grep 'region:' "$PROJECT_ROOT/config.yaml" | awk '{print $2}' | tr -d '"')
else
    echo "Error: config.yaml not found"
    exit 1
fi

PROVISION_DIR="$PROJECT_ROOT/tests/setup/test-accounts"
STACK_NAME="AccountPoolFactory-ControlTower-Test"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Get email number from argument or find latest
if [ -n "$1" ]; then
    EMAIL_NUM=$1
else
    # Find latest provision file
    LATEST_FILE=$(ls -t "$PROVISION_DIR"/test-account-provision-*.json 2>/dev/null | head -1)
    if [ -z "$LATEST_FILE" ]; then
        echo -e "${RED}Error: No provision files found${NC}"
        exit 1
    fi
    EMAIL_NUM=$(basename "$LATEST_FILE" | sed 's/test-account-provision-\([0-9]*\)\.json/\1/')
fi

PROVISION_FILE="$PROVISION_DIR/test-account-provision-${EMAIL_NUM}.json"

if [ ! -f "$PROVISION_FILE" ]; then
    echo -e "${RED}Error: Provision file not found: $PROVISION_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}=== Checking Account Creation Status ===${NC}"
echo ""

# Read provision file
REQUEST_ID=$(jq -r '.requestId' "$PROVISION_FILE")
ACCOUNT_EMAIL=$(jq -r '.accountEmail' "$PROVISION_FILE")
ACCOUNT_NAME=$(jq -r '.accountName' "$PROVISION_FILE")
STRATEGY=$(jq -r '.strategy // "organizations_api"' "$PROVISION_FILE")

echo "Account Details:"
echo "  Email: $ACCOUNT_EMAIL"
echo "  Name: $ACCOUNT_NAME"
echo "  Strategy: $STRATEGY"
echo "  Request ID: $REQUEST_ID"
echo ""

# Assume cross-account role
ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`AccountCreationRoleArn`].OutputValue' \
    --output text)

EXTERNAL_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`ExternalId`].OutputValue' \
    --output text)

CREDENTIALS=$(aws sts assume-role \
    --role-arn "$ROLE_ARN" \
    --role-session-name "AccountStatusCheck" \
    --external-id "$EXTERNAL_ID" \
    --region "$REGION" \
    --query 'Credentials' \
    --output json)

export AWS_ACCESS_KEY_ID=$(echo "$CREDENTIALS" | jq -r '.AccessKeyId')
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDENTIALS" | jq -r '.SecretAccessKey')
export AWS_SESSION_TOKEN=$(echo "$CREDENTIALS" | jq -r '.SessionToken')

# Check status
STATUS_RESPONSE=$(aws organizations describe-create-account-status \
    --create-account-request-id "$REQUEST_ID" \
    --region "$REGION" \
    --output json)

STATE=$(echo "$STATUS_RESPONSE" | jq -r '.CreateAccountStatus.State')
ACCOUNT_ID=$(echo "$STATUS_RESPONSE" | jq -r '.CreateAccountStatus.AccountId // "N/A"')

# Update provision file
jq --arg state "$STATE" --arg updated "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    '.status = $state | .updatedAt = $updated' \
    "$PROVISION_FILE" > "${PROVISION_FILE}.tmp" && mv "${PROVISION_FILE}.tmp" "$PROVISION_FILE"

if [ "$ACCOUNT_ID" != "N/A" ] && [ "$ACCOUNT_ID" != "null" ]; then
    jq --arg accountId "$ACCOUNT_ID" \
        '.accountId = $accountId' \
        "$PROVISION_FILE" > "${PROVISION_FILE}.tmp" && mv "${PROVISION_FILE}.tmp" "$PROVISION_FILE"
fi

echo "Current Status:"
echo "  State: $STATE"
echo "  Account ID: $ACCOUNT_ID"
echo ""

case "$STATE" in
    "IN_PROGRESS")
        echo -e "${YELLOW}⏳ Account creation is still in progress${NC}"
        echo ""
        echo "Check again in a few minutes with:"
        echo "  ./test-check-status-orgs-api.sh $EMAIL_NUM"
        ;;
    "SUCCEEDED")
        echo -e "${GREEN}✓ Account created successfully!${NC}"
        echo ""
        echo "Next steps:"
        echo "  1. Verify account: ./test-verify-account.sh $EMAIL_NUM"
        echo "  2. Deploy StackSets to account"
        echo "  3. Delete when done: ./test-delete-account.sh $EMAIL_NUM"
        ;;
    "FAILED")
        FAILURE_REASON=$(echo "$STATUS_RESPONSE" | jq -r '.CreateAccountStatus.FailureReason // "Unknown"')
        jq --arg reason "$FAILURE_REASON" \
            '.failureReason = $reason' \
            "$PROVISION_FILE" > "${PROVISION_FILE}.tmp" && mv "${PROVISION_FILE}.tmp" "$PROVISION_FILE"
        
        echo -e "${RED}✗ Account creation failed${NC}"
        echo "  Reason: $FAILURE_REASON"
        echo ""
        echo "You may need to:"
        echo "  1. Check AWS Organizations quotas"
        echo "  2. Verify email is not already in use"
        echo "  3. Check IAM permissions"
        ;;
    *)
        echo -e "${YELLOW}⚠ Unknown state: $STATE${NC}"
        ;;
esac

echo ""

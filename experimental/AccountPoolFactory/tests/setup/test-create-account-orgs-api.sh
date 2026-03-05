#!/bin/bash

# Test script for creating AWS account using Organizations API (Strategy 2)
# This script creates an account directly via Organizations API without Control Tower

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

# Configuration
STACK_NAME="AccountPoolFactory-ControlTower-Test"
PROVISION_DIR="$PROJECT_ROOT/tests/setup/test-accounts"
mkdir -p "$PROVISION_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Organizations API Account Creation Test ===${NC}"
echo ""

# Find next available email number
find_next_email_number() {
    local max_num=99
    
    # Check existing provision files
    for file in "$PROVISION_DIR"/test-account-provision-*.json; do
        if [ -f "$file" ]; then
            num=$(basename "$file" | sed 's/test-account-provision-\([0-9]*\)\.json/\1/')
            if [ "$num" -gt "$max_num" ]; then
                max_num=$num
            fi
        fi
    done
    
    # Check existing accounts in Organizations
    existing_emails=$(aws organizations list-accounts --region "$REGION" --query 'Accounts[].Email' --output text 2>/dev/null || echo "")
    for email in $existing_emails; do
        if [[ $email =~ amirbo\+([0-9]+)@amazon\.com ]]; then
            num="${BASH_REMATCH[1]}"
            if [ "$num" -gt "$max_num" ]; then
                max_num=$num
            fi
        fi
    done
    
    echo $((max_num + 1))
}

EMAIL_NUM=$(find_next_email_number)
ACCOUNT_EMAIL="amirbo+${EMAIL_NUM}@amazon.com"
ACCOUNT_NAME="TestAccount-OrgsApi-${EMAIL_NUM}"
PROVISION_FILE="$PROVISION_DIR/test-account-provision-${EMAIL_NUM}.json"

echo "Account Details:"
echo "  Email: $ACCOUNT_EMAIL"
echo "  Name: $ACCOUNT_NAME"
echo "  Provision File: $PROVISION_FILE"
echo ""

# Get target OU from ou-ids.json
if [ -f "$PROJECT_ROOT/ou-ids.json" ]; then
    TARGET_OU=$(jq -r '.[] | select(.OutputKey=="TargetOUId") | .OutputValue' "$PROJECT_ROOT/ou-ids.json")
    echo "  Target OU: $TARGET_OU"
else
    echo -e "${RED}Error: ou-ids.json not found${NC}"
    exit 1
fi

# Get cross-account role ARN from CF1 stack
echo -e "${YELLOW}Getting cross-account role from CF1 stack...${NC}"
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

if [ -z "$ROLE_ARN" ]; then
    echo -e "${RED}Error: Could not get AccountCreationRoleArn from stack${NC}"
    exit 1
fi

echo "  Role ARN: $ROLE_ARN"
echo "  External ID: $EXTERNAL_ID"
echo ""

# Assume the cross-account role
echo -e "${YELLOW}Assuming cross-account role...${NC}"
CREDENTIALS=$(aws sts assume-role \
    --role-arn "$ROLE_ARN" \
    --role-session-name "AccountCreationTest" \
    --external-id "$EXTERNAL_ID" \
    --region "$REGION" \
    --query 'Credentials' \
    --output json)

if [ -z "$CREDENTIALS" ]; then
    echo -e "${RED}Error: Failed to assume role${NC}"
    exit 1
fi

export AWS_ACCESS_KEY_ID=$(echo "$CREDENTIALS" | jq -r '.AccessKeyId')
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDENTIALS" | jq -r '.SecretAccessKey')
export AWS_SESSION_TOKEN=$(echo "$CREDENTIALS" | jq -r '.SessionToken')

echo -e "${GREEN}✓ Successfully assumed role${NC}"
echo ""

# Create account using Organizations API
echo -e "${YELLOW}Creating account via Organizations API...${NC}"
echo "  This will take 5-8 minutes..."
echo ""

CREATE_RESPONSE=$(aws organizations create-account \
    --email "$ACCOUNT_EMAIL" \
    --account-name "$ACCOUNT_NAME" \
    --role-name "OrganizationAccountAccessRole" \
    --iam-user-access-to-billing ALLOW \
    --tags "Key=Purpose,Value=Testing" "Key=Strategy,Value=OrganizationsApi" "Key=ManagedBy,Value=AccountPoolFactory" \
    --region "$REGION" \
    --output json)

REQUEST_ID=$(echo "$CREATE_RESPONSE" | jq -r '.CreateAccountStatus.Id')
STATE=$(echo "$CREATE_RESPONSE" | jq -r '.CreateAccountStatus.State')

if [ -z "$REQUEST_ID" ] || [ "$REQUEST_ID" == "null" ]; then
    echo -e "${RED}Error: Failed to create account${NC}"
    echo "$CREATE_RESPONSE"
    exit 1
fi

echo -e "${GREEN}✓ Account creation initiated${NC}"
echo "  Request ID: $REQUEST_ID"
echo "  Initial State: $STATE"
echo ""

# Save provisioning details
cat > "$PROVISION_FILE" <<EOF
{
  "emailNumber": ${EMAIL_NUM},
  "accountEmail": "$ACCOUNT_EMAIL",
  "accountName": "$ACCOUNT_NAME",
  "strategy": "organizations_api",
  "requestId": "$REQUEST_ID",
  "status": "$STATE",
  "targetOu": "$TARGET_OU",
  "createdAt": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "updatedAt": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

echo -e "${GREEN}✓ Provisioning details saved to: $PROVISION_FILE${NC}"
echo ""

# Monitor account creation
echo -e "${YELLOW}Monitoring account creation (this may take 5-8 minutes)...${NC}"
echo "You can safely disconnect and check status later with:"
echo "  ./test-check-status-orgs-api.sh $EMAIL_NUM"
echo ""

MAX_ATTEMPTS=60
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    sleep 10
    ATTEMPT=$((ATTEMPT + 1))
    
    STATUS_RESPONSE=$(aws organizations describe-create-account-status \
        --create-account-request-id "$REQUEST_ID" \
        --region "$REGION" \
        --output json)
    
    STATE=$(echo "$STATUS_RESPONSE" | jq -r '.CreateAccountStatus.State')
    
    # Update provision file
    jq --arg state "$STATE" --arg updated "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
        '.status = $state | .updatedAt = $updated' \
        "$PROVISION_FILE" > "${PROVISION_FILE}.tmp" && mv "${PROVISION_FILE}.tmp" "$PROVISION_FILE"
    
    echo "  Attempt $ATTEMPT/$MAX_ATTEMPTS - State: $STATE"
    
    if [ "$STATE" == "SUCCEEDED" ]; then
        ACCOUNT_ID=$(echo "$STATUS_RESPONSE" | jq -r '.CreateAccountStatus.AccountId')
        
        # Update provision file with account ID
        jq --arg accountId "$ACCOUNT_ID" \
            '.accountId = $accountId' \
            "$PROVISION_FILE" > "${PROVISION_FILE}.tmp" && mv "${PROVISION_FILE}.tmp" "$PROVISION_FILE"
        
        echo ""
        echo -e "${GREEN}✓ Account created successfully!${NC}"
        echo "  Account ID: $ACCOUNT_ID"
        echo ""
        
        # Move account to target OU
        echo -e "${YELLOW}Moving account to target OU...${NC}"
        
        # Get root OU
        ROOT_ID=$(aws organizations list-roots --region "$REGION" --query 'Roots[0].Id' --output text)
        
        aws organizations move-account \
            --account-id "$ACCOUNT_ID" \
            --source-parent-id "$ROOT_ID" \
            --destination-parent-id "$TARGET_OU" \
            --region "$REGION"
        
        echo -e "${GREEN}✓ Account moved to target OU${NC}"
        echo ""
        
        # Emit custom EventBridge event
        echo -e "${YELLOW}Emitting EventBridge event...${NC}"
        
        # Get event bus name from config or use default
        EVENT_BUS_NAME="AccountPoolFactoryEventBus"
        
        aws events put-events \
            --entries "[{
                \"Source\": \"accountpoolfactory.organizations\",
                \"DetailType\": \"Account Creation Status Change\",
                \"Detail\": \"{\\\"accountId\\\":\\\"$ACCOUNT_ID\\\",\\\"accountName\\\":\\\"$ACCOUNT_NAME\\\",\\\"accountEmail\\\":\\\"$ACCOUNT_EMAIL\\\",\\\"state\\\":\\\"SUCCEEDED\\\",\\\"requestId\\\":\\\"$REQUEST_ID\\\",\\\"organizationalUnit\\\":\\\"$TARGET_OU\\\"}\",
                \"EventBusName\": \"$EVENT_BUS_NAME\"
            }]" \
            --region "$REGION"
        
        echo -e "${GREEN}✓ EventBridge event emitted${NC}"
        echo ""
        
        echo -e "${GREEN}=== Account Creation Complete ===${NC}"
        echo ""
        echo "Next steps:"
        echo "  1. Verify account: ./test-verify-account.sh $EMAIL_NUM"
        echo "  2. Deploy StackSets to account (manual for now)"
        echo "  3. Delete account when done: ./test-delete-account.sh $EMAIL_NUM"
        echo ""
        
        exit 0
    elif [ "$STATE" == "FAILED" ]; then
        FAILURE_REASON=$(echo "$STATUS_RESPONSE" | jq -r '.CreateAccountStatus.FailureReason // "Unknown"')
        
        # Update provision file
        jq --arg reason "$FAILURE_REASON" \
            '.failureReason = $reason' \
            "$PROVISION_FILE" > "${PROVISION_FILE}.tmp" && mv "${PROVISION_FILE}.tmp" "$PROVISION_FILE"
        
        echo ""
        echo -e "${RED}✗ Account creation failed${NC}"
        echo "  Reason: $FAILURE_REASON"
        echo ""
        exit 1
    fi
done

echo ""
echo -e "${YELLOW}⚠ Timeout waiting for account creation${NC}"
echo "Account creation is still in progress. Check status with:"
echo "  ./test-check-status-orgs-api.sh $EMAIL_NUM"
echo ""

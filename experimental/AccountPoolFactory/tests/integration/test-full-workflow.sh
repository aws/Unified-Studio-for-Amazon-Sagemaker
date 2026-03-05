#!/bin/bash

# Account Pool Factory - Full Testing Script
# This script guides you through the complete testing cycle

set -e

REGION="us-east-2"
PROGRESS_FILE="TESTING_PROGRESS.md"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "🚀 Account Pool Factory - Full Testing Cycle"
echo "=============================================="
echo ""

# Function to update progress file
update_progress() {
  local phase=$1
  local step=$2
  local status=$3
  local notes=$4
  
  echo "📝 Updating progress: Phase $phase, Step $step - $status"
}

# Function to wait for user confirmation
wait_for_confirmation() {
  local message=$1
  echo ""
  echo -e "${YELLOW}$message${NC}"
  read -p "Press Enter to continue or Ctrl+C to abort..."
  echo ""
}

# Phase 1: Configuration Update
echo -e "${BLUE}=== Phase 1: Configuration Update ===${NC}"
echo ""
echo "Step 1.1: Get new domain information"
echo "Run: ./get-domain-info.sh"
echo ""
wait_for_confirmation "Have you updated config.yaml with the new domain details?"

# Phase 2: Organization Admin Deployment
echo -e "${BLUE}=== Phase 2: Organization Admin Deployment ===${NC}"
echo ""
echo "Step 2.1: Deploy Approved StackSets"
echo "This will create 3 StackSets in the Organization Admin account"
echo ""
wait_for_confirmation "Ready to deploy StackSets?"

if [ -f "tests/setup/scripts/deploy-approved-stacksets.sh" ]; then
  echo "Running: ./tests/setup/scripts/deploy-approved-stacksets.sh"
  ./tests/setup/scripts/deploy-approved-stacksets.sh
else
  echo -e "${RED}❌ Script not found: tests/setup/scripts/deploy-approved-stacksets.sh${NC}"
  echo "Please create this script or deploy StackSets manually"
  wait_for_confirmation "Have you deployed the StackSets manually?"
fi

# Phase 3: Domain Account Deployment
echo -e "${BLUE}=== Phase 3: Domain Account Deployment ===${NC}"
echo ""
echo "Step 3.1: Deploy Infrastructure Stack"
echo "This will deploy all Lambda functions, DynamoDB, EventBridge, SNS, and CloudWatch dashboards"
echo ""
wait_for_confirmation "Ready to deploy infrastructure?"

echo "Running: ./deploy-infrastructure.sh"
./deploy-infrastructure.sh

echo ""
echo "Step 3.2: Verify Lambda Functions"
aws lambda list-functions \
  --region $REGION \
  --query 'Functions[?starts_with(FunctionName, `PoolManager`) || starts_with(FunctionName, `SetupOrchestrator`) || starts_with(FunctionName, `AccountProvider`)].FunctionName' \
  --output table

echo ""
echo "Step 3.3: Verify SSM Parameters"
aws ssm get-parameters-by-path \
  --path /AccountPoolFactory/ \
  --recursive \
  --region $REGION \
  --query 'Parameters[*].[Name,Value]' \
  --output table

wait_for_confirmation "Do the Lambda functions and SSM parameters look correct?"

# Phase 4: DataZone Integration
echo -e "${BLUE}=== Phase 4: DataZone Integration ===${NC}"
echo ""
echo "Step 4.1: Create Account Pool in DataZone"
echo ""
echo "You need to create the account pool manually via DataZone console or CLI"
echo "Use the Account Provider Lambda ARN from the infrastructure stack outputs"
echo ""
wait_for_confirmation "Have you created the account pool in DataZone?"

echo ""
echo "Step 4.2: Create Project Profile with Account Pool"
echo ""
echo "Create a project profile that uses the account pool"
echo ""
wait_for_confirmation "Have you created the project profile?"

# Phase 5: Initial Pool Seeding
echo -e "${BLUE}=== Phase 5: Initial Pool Seeding ===${NC}"
echo ""
echo "Step 5.1: Trigger Manual Replenishment"
echo ""
wait_for_confirmation "Ready to seed the initial pool?"

echo "Running: ./seed-initial-pool.sh"
./seed-initial-pool.sh

echo ""
echo "Step 5.2-5.3: Monitor Account Creation and Setup"
echo ""
echo "Open two terminal windows:"
echo "  Terminal 1: aws logs tail /aws/lambda/PoolManager --follow --region $REGION"
echo "  Terminal 2: aws logs tail /aws/lambda/SetupOrchestrator --follow --region $REGION"
echo ""
wait_for_confirmation "Are accounts being created and set up? (This takes 6-8 minutes per account)"

echo ""
echo "Step 5.4: Verify DynamoDB State"
aws dynamodb scan \
  --table-name AccountPoolFactory-AccountState \
  --region $REGION \
  --query 'Items[*].[accountId.S,state.S,createdDate.S]' \
  --output table

wait_for_confirmation "Do you see accounts in AVAILABLE state?"

# Phase 6: Project Creation Testing
echo -e "${BLUE}=== Phase 6: Project Creation Testing ===${NC}"
echo ""
echo "Step 6.1: Create Test Project"
echo ""
echo "Create a project via DataZone portal using the account pool-enabled profile"
echo ""
wait_for_confirmation "Have you created a test project?"

echo ""
echo "Step 6.2: Verify Account Assignment"
aws dynamodb scan \
  --table-name AccountPoolFactory-AccountState \
  --region $REGION \
  --query 'Items[?state.S==`ASSIGNED`].[accountId.S,projectId.S,assignedDate.S]' \
  --output table

wait_for_confirmation "Do you see one account in ASSIGNED state?"

# Phase 7: Environment Creation Testing
echo -e "${BLUE}=== Phase 7: Environment Creation Testing ===${NC}"
echo ""
echo "Step 7.1: Create Environment Manually"
echo ""
echo "Create an environment in your test project (ON_DEMAND mode)"
echo ""
wait_for_confirmation "Have you created an environment?"

echo ""
echo "Step 7.2: Check Account Provider Lambda Logs"
aws logs tail /aws/lambda/AccountProvider --region $REGION | head -50

wait_for_confirmation "Did the Account Provider Lambda return an account?"

# Phase 8: Monitoring Validation
echo -e "${BLUE}=== Phase 8: Monitoring Validation ===${NC}"
echo ""
echo "Step 8.1: Check CloudWatch Dashboards"
echo ""
echo "Navigate to CloudWatch console and verify these dashboards:"
echo "  - AccountPoolFactory-Overview"
echo "  - AccountPoolFactory-Inventory"
echo "  - AccountPoolFactory-FailedAccounts"
echo "  - AccountPoolFactory-OrgLimits"
echo ""
wait_for_confirmation "Are all dashboards showing data?"

# Phase 9: Cleanup Testing
echo -e "${BLUE}=== Phase 9: Cleanup Testing ===${NC}"
echo ""
echo "Step 9.1: Delete Test Project"
echo ""
echo "Delete the test project via DataZone portal"
echo ""
wait_for_confirmation "Have you deleted the test project?"

echo ""
echo "Step 9.2: Monitor Account Deletion"
echo "Watch Pool Manager logs for DELETE_COMPLETE event and account closure"
aws logs tail /aws/lambda/PoolManager --follow --region $REGION &
LOG_PID=$!

wait_for_confirmation "Did you see the account being closed?"
kill $LOG_PID 2>/dev/null || true

# Summary
echo ""
echo -e "${GREEN}=== Testing Complete ===${NC}"
echo ""
echo "✅ All phases completed!"
echo ""
echo "Please review TESTING_PROGRESS.md and update with:"
echo "  - All resource IDs created"
echo "  - Any issues encountered"
echo "  - Performance metrics"
echo "  - Recommendations"
echo ""
echo "Next steps:"
echo "  1. Review all CloudWatch dashboards"
echo "  2. Check for any failed accounts"
echo "  3. Verify all metrics are being published"
echo "  4. Test failure scenarios if needed"
echo ""

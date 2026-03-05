#!/bin/bash

# Fix Trust Policy Update Issue and Test
# This script:
# 1. Deploys updated cross-account role with sts:AssumeRole permission
# 2. Deletes the failed account
# 3. Triggers new account creation to test the fix

set -e

echo "🔧 Fixing Trust Policy Update Issue"
echo "===================================="
echo ""

# Step 1: Deploy updated cross-account role in Org Admin account
echo "Step 1: Deploying updated cross-account role in Org Admin account (495869084367)"
echo "--------------------------------------------------------------------------------"
echo "⚠️  ACTION REQUIRED: Run this command in your terminal:"
echo ""
echo "eval \$(isengardcli credentials amirbo+1@amazon.com) && cd experimental/AccountPoolFactory && ./deploy-org-admin-role.sh"
echo ""
read -p "Press Enter after you've deployed the role..."
echo ""

# Step 2: Switch to Domain account
echo "Step 2: Switching to Domain account (994753223772)"
echo "---------------------------------------------------"
eval $(isengardcli credentials amirbo+3@amazon.com)
echo "✅ Switched to Domain account"
echo ""

# Step 3: Delete failed account
echo "Step 3: Deleting failed account 070648356629"
echo "---------------------------------------------"
aws lambda invoke \
  --function-name PoolManager \
  --cli-binary-format raw-in-base64-out \
  --payload '{"action":"delete_failed_account","accountId":"070648356629"}' \
  --region us-east-2 \
  /tmp/delete-response.json

echo "Response:"
cat /tmp/delete-response.json
echo ""
echo ""

# Step 4: Trigger new account creation
echo "Step 4: Triggering new account creation"
echo "----------------------------------------"
./seed-initial-pool.sh
echo ""

# Step 5: Monitor logs
echo "Step 5: Monitoring Pool Manager logs"
echo "-------------------------------------"
echo "⚠️  Watch for trust policy update success/failure"
echo ""
echo "Run this command to monitor logs:"
echo "aws logs tail /aws/lambda/PoolManager --follow --region us-east-2"
echo ""
echo "✅ Fix deployment complete!"
echo ""
echo "Next steps:"
echo "1. Monitor Pool Manager logs for trust policy update"
echo "2. Monitor Setup Orchestrator logs for account setup"
echo "3. Verify account reaches AVAILABLE state"

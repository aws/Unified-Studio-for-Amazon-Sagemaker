#!/bin/bash
set -e

PROJECT_ACCOUNT="004878717744"

echo "=== Fixing DataZoneProvisioningRole in Account $PROJECT_ACCOUNT ==="
echo ""

# Switch to project account
eval "$(isengardcli creds amirbo+1 --role Admin)"
CREDS=$(aws sts assume-role \
  --role-arn "arn:aws:iam::$PROJECT_ACCOUNT:role/OrganizationAccountAccessRole" \
  --role-session-name "FixRole" \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text)

export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | awk '{print $1}')
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | awk '{print $2}')
export AWS_SESSION_TOKEN=$(echo "$CREDS" | awk '{print $3}')

echo "Step 1: Checking current attached policies..."
aws iam list-attached-role-policies \
  --role-name DataZoneProvisioningRole \
  --output json | jq '.AttachedPolicies'

echo ""
echo "Step 2: Detaching AmazonDataZoneEnvironmentRolePermissionsBoundary..."
aws iam detach-role-policy \
  --role-name DataZoneProvisioningRole \
  --policy-arn "arn:aws:iam::aws:policy/AmazonDataZoneEnvironmentRolePermissionsBoundary"

echo "✅ Policy detached"
echo ""

echo "Step 3: Verifying remaining policies..."
aws iam list-attached-role-policies \
  --role-name DataZoneProvisioningRole \
  --output json | jq '.AttachedPolicies'

echo ""
echo "✅ DataZoneProvisioningRole fixed!"
echo ""
echo "The role now only has:"
echo "  - AmazonDataZoneSageMakerProvisioningRolePolicy"
echo ""
echo "This should resolve the glue:GetDataCatalogEncryptionSettings permission error"

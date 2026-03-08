#!/bin/bash
set -e

# Test RAM share creation with IAM-mode DataZone domain
# This script tests RAM share creation in isolation to understand the behavior

echo "🧪 Testing RAM Share Creation with IAM-mode DataZone Domain"
echo "============================================================"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

DOMAIN_ID=$(grep "domain_id:" config.yaml | awk '{print $2}')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')
REGION=$(grep "region:" config.yaml | awk '{print $2}')
PROJECT_ACCOUNT_ID="${1:?Usage: $0 <project-account-id>}"  # Pass as argument

DOMAIN_ARN="arn:aws:datazone:${REGION}:${DOMAIN_ACCOUNT_ID}:domain/${DOMAIN_ID}"
SHARE_NAME="Test-RAM-Share-$(date +%s)"

echo ""
echo "Configuration:"
echo "  Domain ID: ${DOMAIN_ID}"
echo "  Domain Account: ${DOMAIN_ACCOUNT_ID}"
echo "  Project Account: ${PROJECT_ACCOUNT_ID}"
echo "  Domain ARN: ${DOMAIN_ARN}"
echo "  Region: ${REGION}"
echo ""

# Switch to domain account
echo "🔐 Switching to domain account..."
eval $(isengardcli credentials amirbo+3@amazon.com)

echo ""
echo "📋 Step 1: Get domain details"
echo "------------------------------"
aws datazone get-domain \
  --identifier "${DOMAIN_ID}" \
  --region "${REGION}" \
  --query '{Id:id, Name:name, Status:status, DomainExecutionRole:domainExecutionRole}' \
  --output table

echo ""
echo "📋 Step 2: Test different RAM permissions"
echo "------------------------------------------"
echo "  Available permissions for DataZone domains:"
aws ram list-permissions \
  --resource-type datazone:Domain \
  --region "${REGION}" \
  --query 'permissions[].{Name:name, Version:version}' \
  --output table

echo ""
echo "  Testing with AWSRAMPermissionAmazonDataZoneDomainFullAccessWithPortalAccess (v7)..."
echo "  This permission might work better for IAM-mode domains"

echo ""
echo "📋 Step 3: Create RAM resource share (WITHOUT resources initially)"
echo "-------------------------------------------------------------"
echo "  Creating share without resources first, then associating..."
SHARE_OUTPUT=$(aws ram create-resource-share \
  --name "${SHARE_NAME}" \
  --principals "${PROJECT_ACCOUNT_ID}" \
  --permission-arns "arn:aws:ram::aws:permission/AWSRAMPermissionAmazonDataZoneDomainFullAccessWithPortalAccess" \
  --tags key=ManagedBy,value=AccountPoolFactory key=AccountId,value=${PROJECT_ACCOUNT_ID} \
  --region "${REGION}" \
  --output json)

SHARE_ARN=$(echo "${SHARE_OUTPUT}" | jq -r '.resourceShare.resourceShareArn')
SHARE_STATUS=$(echo "${SHARE_OUTPUT}" | jq -r '.resourceShare.status')

echo "  Share ARN: ${SHARE_ARN}"
echo "  Initial Status: ${SHARE_STATUS}"

echo ""
echo "⏳ Step 4: Wait for share to become ACTIVE (max 60 seconds)..."
echo "---------------------------------------------------------------"
for i in {1..12}; do
  CURRENT_STATUS=$(aws ram get-resource-shares \
    --resource-share-arns "${SHARE_ARN}" \
    --resource-owner SELF \
    --region "${REGION}" \
    --query 'resourceShares[0].status' \
    --output text)
  
  echo "  Attempt $i/12: Status = ${CURRENT_STATUS}"
  
  if [ "${CURRENT_STATUS}" = "ACTIVE" ]; then
    echo "  ✅ Share is ACTIVE"
    break
  fi
  
  sleep 5
done

echo ""
echo "📎 Step 5: EXPLICITLY associate domain resource with share"
echo "-------------------------------------------------------------"
echo "  This is the KEY step - resourceArns in create doesn't work reliably!"
ASSOCIATE_OUTPUT=$(aws ram associate-resource-share \
  --resource-share-arn "${SHARE_ARN}" \
  --resource-arns "${DOMAIN_ARN}" \
  --region "${REGION}" \
  --output json)

echo "  ✅ Resource association initiated"
echo "${ASSOCIATE_OUTPUT}" | jq -r '.resourceShareAssociations[] | "    Association Status: \(.status)\n    Resource ARN: \(.associatedEntity)"'

echo ""
echo "📋 Step 6: Wait for resources to be added to share (max 2 minutes)..."
echo "-----------------------------------------------------------------------"
RESOURCE_COUNT=0
for i in {1..24}; do
  RESOURCES=$(aws ram list-resources \
    --resource-owner SELF \
    --resource-share-arns "${SHARE_ARN}" \
    --region "${REGION}" \
    --output json)

  RESOURCE_COUNT=$(echo "${RESOURCES}" | jq -r '.resources | length')
  
  echo "  Attempt $i/24: Resources in share = ${RESOURCE_COUNT}"
  
  if [ "${RESOURCE_COUNT}" -gt 0 ]; then
    echo "  ✅ Resources found in share!"
    echo "${RESOURCES}" | jq -r '.resources[] | "    Resource ARN: \(.arn)\n    Type: \(.type)\n    Status: \(.status)"'
    break
  fi
  
  sleep 5
done

echo ""
echo "  Final resource count: ${RESOURCE_COUNT}"

if [ "${RESOURCE_COUNT}" -eq 0 ]; then
  echo ""
  echo "  ⚠️  WARNING: No resources found in the share after 2 minutes!"
  echo "  This means the domain ARN was not added to the share."
  echo ""
  echo "  Possible reasons:"
  echo "  1. IAM-mode domains may not support RAM sharing"
  echo "  2. The domain ARN format is incorrect"
  echo "  3. There's a permission issue"
  echo "  4. The resource type is not supported"
  echo ""
  echo "  Let's check the share status one more time..."
  aws ram get-resource-shares \
    --resource-share-arns "${SHARE_ARN}" \
    --resource-owner SELF \
    --region "${REGION}" \
    --query 'resourceShares[0]' \
    --output json | jq '.'
fi

echo ""
echo "📋 Step 7: Check principal association status (CRITICAL)"
echo "---------------------------------------------------------"
echo "  Checking if principal association succeeded or failed..."

PRINCIPAL_ASSOC=$(aws ram get-resource-share-associations \
  --association-type PRINCIPAL \
  --resource-share-arns "${SHARE_ARN}" \
  --region "${REGION}" \
  --output json)

echo "${PRINCIPAL_ASSOC}" | jq -r '.resourceShareAssociations[] | "  Principal: \(.associatedEntity)\n  Status: \(.status)\n  Message: \(.statusMessage // "N/A")"'

PRINCIPAL_STATUS=$(echo "${PRINCIPAL_ASSOC}" | jq -r '.resourceShareAssociations[0].status')

if [ "${PRINCIPAL_STATUS}" = "FAILED" ]; then
  echo ""
  echo "  ❌ PRINCIPAL ASSOCIATION FAILED!"
  echo "  This is why the project account cannot access the domain."
  echo "  The RAM permission we're using doesn't work with IAM-mode domains."
  echo ""
  echo "  Cleaning up and exiting..."
  aws ram delete-resource-share \
    --resource-share-arn "${SHARE_ARN}" \
    --region "${REGION}" \
    --output text
  exit 1
elif [ "${PRINCIPAL_STATUS}" = "ASSOCIATED" ]; then
  echo ""
  echo "  ✅ Principal association succeeded!"
fi

echo ""
echo "📋 Step 8: Check RAM share invitation status"
echo "---------------------------------------------"
echo "  Checking if invitation needs to be accepted..."

# Check invitation status from domain account perspective
INVITATIONS=$(aws ram get-resource-share-invitations \
  --resource-share-arns "${SHARE_ARN}" \
  --region "${REGION}" \
  --output json 2>/dev/null || echo '{"resourceShareInvitations":[]}')

INVITATION_COUNT=$(echo "${INVITATIONS}" | jq -r '.resourceShareInvitations | length')
echo "  Invitations found: ${INVITATION_COUNT}"

if [ "${INVITATION_COUNT}" -gt 0 ]; then
  echo "${INVITATIONS}" | jq -r '.resourceShareInvitations[] | "  Invitation ARN: \(.resourceShareInvitationArn)\n  Status: \(.status)\n  Receiver Account: \(.receiverAccountId)"'
fi

echo ""
echo "📋 Step 9: List principals (accounts) in the share"
echo "---------------------------------------------------"
PRINCIPALS=$(aws ram list-principals \
  --resource-owner SELF \
  --resource-share-arns "${SHARE_ARN}" \
  --region "${REGION}" \
  --output json)

echo "${PRINCIPALS}" | jq -r '.principals[] | "  Principal: \(.id)\n  External: \(.external)"'

echo ""
echo "📋 Step 10: Get share details"
echo "-----------------------------"
aws ram get-resource-shares \
  --resource-share-arns "${SHARE_ARN}" \
  --resource-owner SELF \
  --region "${REGION}" \
  --query 'resourceShares[0].{Name:name, Status:status, AllowExternalPrincipals:allowExternalPrincipals, CreationTime:creationTime}' \
  --output table

echo ""
echo "📋 Step 11: Check if project account can see the share"
echo "-------------------------------------------------------"
echo "  Switching to project account..."
eval $(isengardcli credentials amirbo+1@amazon.com)

# Assume role in project account
PROJECT_ROLE_ARN="arn:aws:iam::${PROJECT_ACCOUNT_ID}:role/OrganizationAccountAccessRole"
echo "  Assuming role: ${PROJECT_ROLE_ARN}"

CREDS=$(aws sts assume-role \
  --role-arn "${PROJECT_ROLE_ARN}" \
  --role-session-name "test-ram-share" \
  --output json)

export AWS_ACCESS_KEY_ID=$(echo "${CREDS}" | jq -r '.Credentials.AccessKeyId')
export AWS_SECRET_ACCESS_KEY=$(echo "${CREDS}" | jq -r '.Credentials.SecretAccessKey')
export AWS_SESSION_TOKEN=$(echo "${CREDS}" | jq -r '.Credentials.SessionToken')

echo ""
echo "  Checking for pending invitations in project account..."
PROJECT_INVITATIONS=$(aws ram get-resource-share-invitations \
  --region "${REGION}" \
  --output json 2>/dev/null || echo '{"resourceShareInvitations":[]}')

PROJECT_INVITATION_COUNT=$(echo "${PROJECT_INVITATIONS}" | jq -r '.resourceShareInvitations | length')
echo "  Pending invitations: ${PROJECT_INVITATION_COUNT}"

if [ "${PROJECT_INVITATION_COUNT}" -gt 0 ]; then
  echo ""
  echo "  Found pending invitations:"
  echo "${PROJECT_INVITATIONS}" | jq -r '.resourceShareInvitations[] | "    Invitation ARN: \(.resourceShareInvitationArn)\n    Status: \(.status)\n    Share ARN: \(.resourceShareArn)\n    Sender Account: \(.senderAccountId)"'
  
  # Check if our share needs acceptance
  OUR_INVITATION=$(echo "${PROJECT_INVITATIONS}" | jq -r --arg arn "${SHARE_ARN}" '.resourceShareInvitations[] | select(.resourceShareArn == $arn) | .resourceShareInvitationArn')
  
  if [ -n "${OUR_INVITATION}" ]; then
    echo ""
    echo "  ⚠️  Our share requires acceptance!"
    echo "  Invitation ARN: ${OUR_INVITATION}"
    echo ""
    echo "  Accepting invitation..."
    
    ACCEPT_RESULT=$(aws ram accept-resource-share-invitation \
      --resource-share-invitation-arn "${OUR_INVITATION}" \
      --region "${REGION}" \
      --output json)
    
    ACCEPT_STATUS=$(echo "${ACCEPT_RESULT}" | jq -r '.resourceShareInvitation.status')
    echo "  Acceptance status: ${ACCEPT_STATUS}"
    
    # Wait a bit for acceptance to propagate
    echo "  Waiting 10 seconds for acceptance to propagate..."
    sleep 10
  fi
fi

echo ""
echo "  Listing resource shares visible to project account..."
SHARED_WITH_ME=$(aws ram get-resource-shares \
  --resource-owner OTHER-ACCOUNTS \
  --region "${REGION}" \
  --output json)

echo "${SHARED_WITH_ME}" | jq -r '.resourceShares[] | "  Share: \(.name)\n  ARN: \(.resourceShareArn)\n  Status: \(.status)\n  Owner: \(.owningAccountId)"'

SHARE_VISIBLE=$(echo "${SHARED_WITH_ME}" | jq -r --arg arn "${SHARE_ARN}" '.resourceShares[] | select(.resourceShareArn == $arn) | .name')

if [ -n "${SHARE_VISIBLE}" ]; then
  echo ""
  echo "  ✅ Share is visible to project account: ${SHARE_VISIBLE}"
  
  # Check resources available through the share
  echo ""
  echo "  Checking resources available through the share..."
  SHARED_RESOURCES=$(aws ram list-resources \
    --resource-owner OTHER-ACCOUNTS \
    --resource-share-arns "${SHARE_ARN}" \
    --region "${REGION}" \
    --output json)
  
  SHARED_RESOURCE_COUNT=$(echo "${SHARED_RESOURCES}" | jq -r '.resources | length')
  echo "  Resources available: ${SHARED_RESOURCE_COUNT}"
  
  if [ "${SHARED_RESOURCE_COUNT}" -gt 0 ]; then
    echo "${SHARED_RESOURCES}" | jq -r '.resources[] | "    Resource ARN: \(.arn)\n    Type: \(.type)\n    Status: \(.status)"'
  fi
else
  echo ""
  echo "  ⚠️  Share is NOT visible to project account"
fi

echo ""
echo "📋 Step 12: Try to access domain from project account"
echo "------------------------------------------------------"
echo "  Waiting 10 more seconds for RAM propagation..."
sleep 10

DOMAIN_ACCESS=$(aws datazone get-domain \
  --identifier "${DOMAIN_ID}" \
  --region "${REGION}" \
  2>&1 || true)

if echo "${DOMAIN_ACCESS}" | grep -q "UnauthorizedException"; then
  echo "  ❌ UnauthorizedException - Domain not accessible"
elif echo "${DOMAIN_ACCESS}" | grep -q "ResourceNotFoundException"; then
  echo "  ❌ ResourceNotFoundException - Domain not found"
elif echo "${DOMAIN_ACCESS}" | grep -q "id"; then
  echo "  ✅ Domain is accessible!"
  echo "${DOMAIN_ACCESS}" | jq -r '{Id:.id, Name:.name, Status:.status}'
else
  echo "  ⚠️  Unexpected response:"
  echo "${DOMAIN_ACCESS}"
fi

echo ""
echo "📋 Step 13: Test blueprint API call (same as Lambda)"
echo "-----------------------------------------------------"
echo "  This tests the EXACT same operation that's failing in the Lambda..."

# Try to create just the ToolingLite blueprint resource
echo "  Testing ToolingLite blueprint configuration..."
BLUEPRINT_RESULT=$(aws datazone put-environment-blueprint-configuration \
  --domain-identifier "${DOMAIN_ID}" \
  --environment-blueprint-identifier "ToolingLite" \
  --enabled-regions "${REGION}" \
  --region "${REGION}" \
  2>&1 || true)

if echo "${BLUEPRINT_RESULT}" | grep -q "UnauthorizedException"; then
  echo "  ❌ Blueprint configuration failed: UnauthorizedException"
  echo "     This is the SAME error the Lambda is getting!"
  echo "     Output: ${BLUEPRINT_RESULT}"
elif echo "${BLUEPRINT_RESULT}" | grep -q "domainId\|environmentBlueprintId"; then
  echo "  ✅ Blueprint configuration succeeded!"
  echo "     Account association is working correctly"
  echo "     Output: ${BLUEPRINT_RESULT}"
else
  echo "  ⚠️  Unexpected response:"
  echo "     ${BLUEPRINT_RESULT}"
fi

echo ""
echo "📋 Step 14: Cleanup - Delete RAM share"
echo "---------------------------------------"
# Switch back to domain account
eval $(isengardcli credentials amirbo+3@amazon.com)

aws ram delete-resource-share \
  --resource-share-arn "${SHARE_ARN}" \
  --region "${REGION}" \
  --output text

echo "  ✅ RAM share deleted"

echo ""
echo "============================================================"
echo "✅ Test completed"
echo ""
echo "Summary:"
echo "  - RAM share created: ${SHARE_STATUS}"
echo "  - Resources in share: ${RESOURCE_COUNT}"
echo "  - Share visible to project account: ${SHARE_VISIBLE:-NO}"
echo ""

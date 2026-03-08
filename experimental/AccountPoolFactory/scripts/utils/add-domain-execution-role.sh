#!/bin/bash
set -e

echo "🔧 Adding Domain Execution Role to IAM-mode DataZone Domain"
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
ROLE_NAME="AmazonDataZoneDomainExecutionRole"

echo ""
echo "Configuration:"
echo "  Domain ID: ${DOMAIN_ID}"
echo "  Domain Account: ${DOMAIN_ACCOUNT_ID}"
echo "  Region: ${REGION}"
echo "  Role Name: ${ROLE_NAME}"
echo ""

# Switch to domain account
echo "🔐 Switching to domain account..."
eval $(isengardcli credentials amirbo+3@amazon.com)

echo ""
echo "📋 Step 1: Create IAM role with domain execution policy"
echo "--------------------------------------------------------"

# Create trust policy
cat > /tmp/domain-execution-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "datazone.amazonaws.com"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "${DOMAIN_ACCOUNT_ID}"
        },
        "ArnLike": {
          "aws:SourceArn": "arn:aws:datazone:${REGION}:${DOMAIN_ACCOUNT_ID}:domain/${DOMAIN_ID}"
        }
      }
    }
  ]
}
EOF

# Check if role exists
if aws iam get-role --role-name "${ROLE_NAME}" 2>/dev/null; then
  echo "  ✅ Role already exists: ${ROLE_NAME}"
else
  echo "  Creating role..."
  aws iam create-role \
    --role-name "${ROLE_NAME}" \
    --assume-role-policy-document file:///tmp/domain-execution-trust-policy.json \
    --description "Domain execution role for DataZone domain ${DOMAIN_ID}" \
    --output text
  
  echo "  ✅ Role created: ${ROLE_NAME}"
fi

echo ""
echo "📋 Step 2: Attach managed policy"
echo "---------------------------------"
aws iam attach-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonDataZoneDomainExecutionRolePolicy"

echo "  ✅ Policy attached"

# Wait for role to propagate
echo ""
echo "⏳ Waiting 10 seconds for role to propagate..."
sleep 10

echo ""
echo "📋 Step 3: Update domain with execution role"
echo "---------------------------------------------"
ROLE_ARN="arn:aws:iam::${DOMAIN_ACCOUNT_ID}:role/${ROLE_NAME}"

aws datazone update-domain \
  --identifier "${DOMAIN_ID}" \
  --domain-execution-role "${ROLE_ARN}" \
  --region "${REGION}" \
  --output json | jq '{id, name, status, domainExecutionRole}'

echo ""
echo "✅ Domain updated with execution role"
echo ""
echo "============================================================"
echo "✅ Setup complete!"
echo ""
echo "The domain now has a domain execution role which is required"
echo "for RAM sharing to work properly."
echo ""
echo "Next steps:"
echo "1. Wait a few minutes for the change to propagate"
echo "2. Re-run the RAM share test: ./test-ram-share.sh"
echo "3. The domain resource should now appear in the RAM share"
echo ""

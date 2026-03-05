#!/bin/bash

# Get Domain Information Script
# This script retrieves DataZone domain details for configuration

set -e

REGION="us-east-2"
DOMAIN_ACCOUNT="994753223772"

echo "🔍 Retrieving DataZone domain information..."
echo ""

# List all domains
echo "📋 Available domains:"
aws datazone list-domains \
  --region $REGION \
  --query 'items[*].[id,name,status]' \
  --output table

echo ""
echo "Enter the Domain ID you want to use:"
read DOMAIN_ID

echo ""
echo "🔍 Getting detailed domain information for: $DOMAIN_ID"
echo ""

# Get domain details
DOMAIN_INFO=$(aws datazone get-domain \
  --identifier $DOMAIN_ID \
  --region $REGION)

# Extract values
DOMAIN_NAME=$(echo $DOMAIN_INFO | jq -r '.name')
DOMAIN_ARN=$(echo $DOMAIN_INFO | jq -r '.arn')
PORTAL_URL=$(echo $DOMAIN_INFO | jq -r '.portalUrl')

echo "✅ Domain Information Retrieved:"
echo "  Domain ID: $DOMAIN_ID"
echo "  Domain Name: $DOMAIN_NAME"
echo "  Domain ARN: $DOMAIN_ARN"
echo "  Portal URL: $PORTAL_URL"
echo ""

# Get root domain unit
echo "🔍 Getting root domain unit..."
ROOT_UNIT_INFO=$(aws datazone list-domain-units-for-parent \
  --domain-identifier $DOMAIN_ID \
  --region $REGION \
  --query 'items[0]' 2>/dev/null || echo "{}")

if [ "$ROOT_UNIT_INFO" != "{}" ]; then
  ROOT_UNIT_ID=$(echo $ROOT_UNIT_INFO | jq -r '.id')
  echo "  Root Domain Unit ID: $ROOT_UNIT_ID"
else
  echo "  ⚠️  No domain units found - using domain ID as root unit"
  ROOT_UNIT_ID=$DOMAIN_ID
fi

echo ""
echo "📝 Update config.yaml with these values:"
echo ""
echo "datazone:"
echo "  domain_id: $DOMAIN_ID"
echo "  domain_name: $DOMAIN_NAME"
echo "  domain_arn: $DOMAIN_ARN"
echo "  root_domain_unit_id: $ROOT_UNIT_ID"
echo "  portal_url: $PORTAL_URL"
echo ""

# Save to temporary file for easy copying
cat > domain-info-temp.yaml <<EOF
datazone:
  domain_id: $DOMAIN_ID
  domain_name: $DOMAIN_NAME
  domain_arn: $DOMAIN_ARN
  root_domain_unit_id: $ROOT_UNIT_ID
  portal_url: $PORTAL_URL
EOF

echo "✅ Domain information saved to: domain-info-temp.yaml"
echo ""
echo "Next steps:"
echo "1. Update config.yaml with the values above"
echo "2. Update TESTING_PROGRESS.md Phase 1.1 status"
echo "3. Proceed to Phase 2: Organization Admin Deployment"

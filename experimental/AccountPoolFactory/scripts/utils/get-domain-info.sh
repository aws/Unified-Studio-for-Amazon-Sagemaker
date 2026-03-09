#!/bin/bash

# Get Domain Information Script
# Retrieves DataZone domain details using the resolver

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

source scripts/utils/resolve-config.sh domain

echo "🔍 Retrieving DataZone domain information..."
echo ""

# List all domains
echo "📋 Available domains:"
aws datazone list-domains \
  --region "$REGION" \
  --query 'items[*].[id,name,status]' \
  --output table

echo ""
echo "✅ Resolved Domain Information:"
echo "  Domain ID:           $DOMAIN_ID"
echo "  Domain Name:         $DOMAIN_NAME"
echo "  Root Domain Unit ID: $ROOT_DOMAIN_UNIT_ID"
echo "  Portal URL:          $PORTAL_URL"
echo "  Region:              $REGION"
echo "  Domain Account:      $DOMAIN_ACCOUNT_ID"
echo ""

# Save to temporary file for easy copying
cat > /tmp/domain-info-temp.yaml <<EOF
domain_id: $DOMAIN_ID
domain_name: $DOMAIN_NAME
root_domain_unit_id: $ROOT_DOMAIN_UNIT_ID
portal_url: $PORTAL_URL
EOF

echo "✅ Domain information saved to: /tmp/domain-info-temp.yaml"
echo ""
echo "These values are resolved from domain-config.yaml via the resolver."
echo "Update domain-config.yaml if any values need to change."

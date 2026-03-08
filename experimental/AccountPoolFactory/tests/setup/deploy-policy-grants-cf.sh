#!/bin/bash
set -e

# Deploy Policy Grants — adds "All Capabilities - Account Pool" profile to
# the domain unit's CREATE_PROJECT_FROM_PROJECT_PROFILE grant.
#
# Safe/incremental: adds a NEW grant for our profile only.
# Does NOT touch the existing grant covering the other 4 profiles.
#
# Usage: ./deploy-policy-grants-cf.sh
# Run from domain account (amirbo+3).
#
# The CF template (tests/setup/templates/policy-grants.yaml) is kept for
# reference but is not used here — Admin role cannot call AddPolicyGrant
# via CloudFormation.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

REGION=$(grep "region:" config.yaml | awk '{print $2}')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')
DOMAIN_ID=$(grep "domain_id:" config.yaml | awk '{print $2}')
ROOT_DOMAIN_UNIT_ID=$(grep "root_domain_unit_id:" config.yaml | awk '{print $2}')
PROFILE_ID="5riu03k7l71zc9"  # All Capabilities - Account Pool

echo "🔐 Adding policy grant for Account Pool project profile"
echo "======================================================="
echo "Region:            $REGION"
echo "Domain Account:    $DOMAIN_ACCOUNT_ID"
echo "Domain ID:         $DOMAIN_ID"
echo "Root Domain Unit:  $ROOT_DOMAIN_UNIT_ID"
echo "Profile ID:        $PROFILE_ID"
echo ""

CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "$DOMAIN_ACCOUNT_ID" ]; then
    echo "❌ Must run in domain account ($DOMAIN_ACCOUNT_ID), currently in $CURRENT_ACCOUNT"
    exit 1
fi

echo "📋 Current CREATE_PROJECT_FROM_PROJECT_PROFILE grants:"
aws datazone list-policy-grants \
    --domain-identifier "$DOMAIN_ID" \
    --entity-type DOMAIN_UNIT \
    --entity-identifier "$ROOT_DOMAIN_UNIT_ID" \
    --policy-type CREATE_PROJECT_FROM_PROJECT_PROFILE \
    --region "$REGION" \
    --query 'grantList[*].detail.createProjectFromProjectProfile.projectProfiles' \
    --output json
echo ""

echo "➕ Adding grant for profile $PROFILE_ID..."
aws datazone add-policy-grant \
    --domain-identifier "$DOMAIN_ID" \
    --entity-type DOMAIN_UNIT \
    --entity-identifier "$ROOT_DOMAIN_UNIT_ID" \
    --policy-type CREATE_PROJECT_FROM_PROJECT_PROFILE \
    --detail "{\"createProjectFromProjectProfile\":{\"includeChildDomainUnits\":true,\"projectProfiles\":[\"$PROFILE_ID\"]}}" \
    --principal '{"user":{"allUsersGrantFilter":{}}}' \
    --region "$REGION"

echo ""
echo "📋 Updated grants:"
aws datazone list-policy-grants \
    --domain-identifier "$DOMAIN_ID" \
    --entity-type DOMAIN_UNIT \
    --entity-identifier "$ROOT_DOMAIN_UNIT_ID" \
    --policy-type CREATE_PROJECT_FROM_PROJECT_PROFILE \
    --region "$REGION" \
    --query 'grantList[*].detail.createProjectFromProjectProfile.projectProfiles' \
    --output json

echo ""
echo "✅ Done"

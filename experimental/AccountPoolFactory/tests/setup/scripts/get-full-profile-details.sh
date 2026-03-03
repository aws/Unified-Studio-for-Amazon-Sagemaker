#!/bin/bash
set -e

# Get complete project profile details for review

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load configuration
CONFIG_FILE="$PROJECT_ROOT/config.yaml"
PROFILE_FILE="$PROJECT_ROOT/project-profile-details.json"

if [ ! -f "$PROFILE_FILE" ]; then
    echo "Error: Project profile details not found: $PROFILE_FILE"
    exit 1
fi

# Parse configuration
read -r DOMAIN_ID REGION < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['region'])
EOF
)

PROFILE_ID=$(jq -r '.profileId' "$PROFILE_FILE")

echo "=== Getting Full Project Profile Details ==="
echo "Domain ID: $DOMAIN_ID"
echo "Profile ID: $PROFILE_ID"
echo "Region: $REGION"
echo ""

# Get complete profile details
FULL_PROFILE=$(aws datazone get-project-profile \
    --domain-identifier "$DOMAIN_ID" \
    --identifier "$PROFILE_ID" \
    --region "$REGION" \
    --output json)

# Save to file for review
OUTPUT_FILE="$PROJECT_ROOT/project-profile-full-details.json"
echo "$FULL_PROFILE" > "$OUTPUT_FILE"

echo "✅ Full profile details saved to: $OUTPUT_FILE"
echo ""

# Show summary
echo "=== Profile Summary ==="
echo "$FULL_PROFILE" | jq '{
    id,
    name,
    status,
    domainId,
    domainUnitId,
    createdAt,
    lastUpdatedAt,
    environmentConfigurationCount: (.environmentConfigurations | length)
}'

echo ""
echo "=== Environment Configurations ==="
echo "$FULL_PROFILE" | jq -r '.environmentConfigurations[] | "
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name: \(.name)
Blueprint ID: \(.environmentBlueprintId)
Deployment Mode: \(.deploymentMode // "N/A")
Deployment Order: \(.deploymentOrder // "N/A")
Account Pools: \(.accountPools // [] | join(", "))
AWS Account: \(.awsAccount // "NOT SET - using account pool")
AWS Region: \(.awsRegion // "NOT SET - using account pool")
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"'

echo ""
echo "=== Account Pool Configuration ==="
ACCOUNT_POOL_ID=$(echo "$FULL_PROFILE" | jq -r '.environmentConfigurations[0].accountPools[0] // "none"')

if [ "$ACCOUNT_POOL_ID" != "none" ]; then
    echo "Account Pool ID: $ACCOUNT_POOL_ID"
    echo ""
    echo "Getting account pool details..."
    
    POOL_DETAILS=$(aws datazone get-account-pool \
        --domain-identifier "$DOMAIN_ID" \
        --identifier "$ACCOUNT_POOL_ID" \
        --region "$REGION" \
        --output json)
    
    echo "$POOL_DETAILS" | jq '{
        id,
        name,
        resolutionStrategy,
        accountSource
    }'
else
    echo "⚠️  No account pool configured"
fi

echo ""
echo "=== Analysis ==="
echo ""

# Check if any config has awsAccount or awsRegion set
HAS_ACCOUNT=$(echo "$FULL_PROFILE" | jq '[.environmentConfigurations[] | select(.awsAccount != null)] | length')
HAS_REGION=$(echo "$FULL_PROFILE" | jq '[.environmentConfigurations[] | select(.awsRegion != null)] | length')
HAS_POOLS=$(echo "$FULL_PROFILE" | jq '[.environmentConfigurations[] | select(.accountPools != null and (.accountPools | length) > 0)] | length')

echo "Configurations with awsAccount set: $HAS_ACCOUNT"
echo "Configurations with awsRegion set: $HAS_REGION"
echo "Configurations with accountPools set: $HAS_POOLS"
echo ""

if [ "$HAS_ACCOUNT" -gt 0 ] || [ "$HAS_REGION" -gt 0 ]; then
    echo "❌ PROBLEM FOUND!"
    echo "Some environment configurations have awsAccount or awsRegion set."
    echo "When using account pools, these fields MUST NOT be set."
    echo "The account and region should come from the pool dynamically."
else
    echo "✅ Account/Region configuration looks correct (not hardcoded)"
fi

echo ""
echo "Full details available in: $OUTPUT_FILE"

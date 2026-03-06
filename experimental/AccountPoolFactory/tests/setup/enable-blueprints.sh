#!/bin/bash
set -e

# Enable DataZone blueprints in the domain

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load configuration
CONFIG_FILE="$PROJECT_ROOT/config.yaml"

read -r DOMAIN_ID REGION < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['region'])
EOF
)

echo "=== Enabling DataZone Blueprints ==="
echo "Domain ID: $DOMAIN_ID"
echo "Region: $REGION"
echo ""

# List of blueprint IDs from the project profile template
# These must match the blueprints referenced in 02-project-profile-with-pool.yaml
BLUEPRINTS=(
    "3owsbi7jjppvc9:Tooling"
    "6bbrztdwfxomeh:DataLake"
    "6vtt2ycs570ezt:LakehouseCatalog"
    "5zux18nxyx6pd5:RedshiftServerless"
    "b0eis75ozsqhd5:Workflows"
    "b78loa64t9oyuh:MLExperiments"
    "atyconez9k8zjd:EmrOnEc2"
    "c1vpqx2w5jxsh5:EmrServerless"
    "d55dwbwfj35qax:AmazonBedrockChatAgent"
    "5smdhnwnnk8j55:AmazonBedrockKnowledgeBase"
    "4q5zrcfovzaq5l:AmazonBedrockGuardrail"
    "da33e9jk0oyq95:AmazonBedrockFunction"
    "40xpt2w3xewr1l:AmazonBedrockFlow"
    "bx74dti0en1e95:AmazonBedrockPrompt"
    "6cxr3kg2f90uw9:AmazonBedrockEvaluation"
)

echo "Blueprints to enable:"
for BP in "${BLUEPRINTS[@]}"; do
    BP_ID="${BP%%:*}"
    BP_NAME="${BP##*:}"
    echo "  - $BP_NAME ($BP_ID)"
done
echo ""

# Enable each blueprint
ENABLED_COUNT=0
ALREADY_ENABLED=0
FAILED_COUNT=0

for BP in "${BLUEPRINTS[@]}"; do
    BP_ID="${BP%%:*}"
    BP_NAME="${BP##*:}"
    
    echo "Enabling $BP_NAME ($BP_ID)..."
    
    if aws datazone put-environment-blueprint-configuration \
        --domain-identifier "$DOMAIN_ID" \
        --environment-blueprint-identifier "$BP_ID" \
        --enabled-regions "$REGION" \
        --region "$REGION" \
        --output json > /dev/null 2>&1; then
        echo "  ✅ Enabled successfully"
        ENABLED_COUNT=$((ENABLED_COUNT+1))
    else
        # Check if it's already enabled
        if aws datazone get-environment-blueprint-configuration \
            --domain-identifier "$DOMAIN_ID" \
            --environment-blueprint-identifier "$BP_ID" \
            --region "$REGION" \
            --query 'enabledRegions' \
            --output text 2>/dev/null | grep -q "$REGION"; then
            echo "  ℹ️  Already enabled"
            ALREADY_ENABLED=$((ALREADY_ENABLED+1))
        else
            echo "  ❌ Failed to enable"
            FAILED_COUNT=$((FAILED_COUNT+1))
        fi
    fi
done

echo ""
echo "=== Summary ==="
echo "Newly enabled: $ENABLED_COUNT"
echo "Already enabled: $ALREADY_ENABLED"
echo "Failed: $FAILED_COUNT"
echo ""

# Verify enabled blueprints
echo "=== Verifying Enabled Blueprints ==="
ENABLED_BPS=$(aws datazone list-environment-blueprints \
    --domain-identifier "$DOMAIN_ID" \
    --region "$REGION" \
    --output json)

ENABLED_COUNT=$(echo "$ENABLED_BPS" | jq '.items | length')
echo "Total enabled blueprints: $ENABLED_COUNT"
echo ""

if [ "$ENABLED_COUNT" -gt 0 ]; then
    echo "Enabled blueprints:"
    echo "$ENABLED_BPS" | jq -r '.items[] | "  - \(.name) (\(.id))"'
else
    echo "⚠️  No blueprints are enabled"
fi

echo ""
echo "✅ Blueprint enablement complete!"

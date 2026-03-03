#!/bin/bash
set -e

# Check project environments and their status

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load configuration
CONFIG_FILE="$PROJECT_ROOT/config.yaml"
PROJECT_FILE="$PROJECT_ROOT/test-project-details.json"

if [ ! -f "$PROJECT_FILE" ]; then
    echo "Error: Project details not found: $PROJECT_FILE"
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

PROJECT_ID=$(jq -r '.projectId' "$PROJECT_FILE")
PROJECT_NAME=$(jq -r '.projectName' "$PROJECT_FILE")

echo "=== Project Information ==="
echo "Project ID: $PROJECT_ID"
echo "Project Name: $PROJECT_NAME"
echo "Domain ID: $DOMAIN_ID"
echo ""

# Get project details
echo "=== Project Status ==="
PROJECT_DETAILS=$(aws datazone get-project \
    --domain-identifier "$DOMAIN_ID" \
    --identifier "$PROJECT_ID" \
    --region "$REGION" \
    --output json)

echo "$PROJECT_DETAILS" | jq '{
    id,
    name,
    projectStatus,
    failureReasons,
    createdAt,
    lastUpdatedAt
}'

echo ""
echo "=== Listing All Environments ==="

# List all environments
ENVIRONMENTS=$(aws datazone list-environments \
    --domain-identifier "$DOMAIN_ID" \
    --project-identifier "$PROJECT_ID" \
    --region "$REGION" \
    --output json)

ENV_COUNT=$(echo "$ENVIRONMENTS" | jq '.items | length')
echo "Total environments: $ENV_COUNT"
echo ""

if [ "$ENV_COUNT" -gt 0 ]; then
    echo "Environment Details:"
    echo "$ENVIRONMENTS" | jq -r '.items[] | "
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name: \(.name)
ID: \(.id)
Status: \(.status)
Blueprint: \(.environmentBlueprintId)
Account: \(.awsAccountId // "NOT ASSIGNED")
Region: \(.awsAccountRegion // "NOT ASSIGNED")
Created: \(.createdAt)
Failure Reasons: \(.failureReasons // [] | join(", ") | if . == "" then "None" else . end)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"'
else
    echo "⚠️  No environments found"
    echo ""
    echo "Expected 4 ON_CREATE environments:"
    echo "  1. Tooling (3owsbi7jjppvc9)"
    echo "  2. Lakehouse Database (6bbrztdwfxomeh)"
    echo "  3. Lakehouse Catalog (6vtt2ycs570ezt)"
    echo "  4. RedshiftServerless (5zux18nxyx6pd5)"
    echo ""
    echo "These should have been created automatically when the project was created."
fi

echo ""
echo "=== Checking Lambda Invocations ==="
LOG_GROUP="/aws/lambda/AccountProvider-$DOMAIN_ID"

echo "Checking for Lambda invocations in last 10 minutes..."
RECENT_LOGS=$(aws logs filter-log-events \
    --log-group-name "$LOG_GROUP" \
    --filter-pattern "Account Provider Lambda INVOKED" \
    --start-time $(($(date +%s) - 600))000 \
    --region "$REGION" \
    --query 'events[*].message' \
    --output text 2>/dev/null || echo "")

if [ -n "$RECENT_LOGS" ]; then
    echo "✅ Lambda was invoked!"
    echo "$RECENT_LOGS"
else
    echo "❌ Lambda was NOT invoked"
    echo ""
    echo "This confirms that ON_CREATE environments are not triggering Lambda invocation."
fi

echo ""
echo "=== Analysis ==="
echo ""

if [ "$ENV_COUNT" -eq 0 ]; then
    echo "❌ PROBLEM: No environments were created automatically"
    echo ""
    echo "Possible causes:"
    echo "1. ON_CREATE deployment mode may not work with account pools"
    echo "2. Account pools may require manual environment creation"
    echo "3. There may be a DataZone service issue"
    echo "4. Additional configuration may be needed"
    echo ""
    echo "Recommendation:"
    echo "- Check DataZone documentation for account pool + ON_CREATE behavior"
    echo "- Try creating environment manually through portal to test Lambda"
    echo "- Contact AWS Support if this is expected to work"
else
    echo "✅ Environments were created"
    echo ""
    echo "Check if Lambda was invoked and accounts were assigned."
fi

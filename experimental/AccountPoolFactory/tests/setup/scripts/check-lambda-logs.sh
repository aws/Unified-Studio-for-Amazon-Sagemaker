#!/bin/bash
set -e

# Check Lambda CloudWatch logs for invocations

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load configuration
CONFIG_FILE="$PROJECT_ROOT/config.yaml"

read -r DOMAIN_ID REGION < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['region'])
EOF
)

LOG_GROUP="/aws/lambda/AccountProvider-$DOMAIN_ID"

echo "=== Checking Lambda CloudWatch Logs ==="
echo "Log Group: $LOG_GROUP"
echo "Region: $REGION"
echo ""

# Check if log group exists
if ! aws logs describe-log-groups \
    --log-group-name-prefix "$LOG_GROUP" \
    --region "$REGION" \
    --query 'logGroups[0].logGroupName' \
    --output text 2>/dev/null | grep -q "$LOG_GROUP"; then
    echo "❌ Log group does not exist yet"
    echo "This means the Lambda has NEVER been invoked"
    exit 0
fi

echo "✅ Log group exists"
echo ""

# Get log streams
echo "=== Recent Log Streams ==="
aws logs describe-log-streams \
    --log-group-name "$LOG_GROUP" \
    --order-by LastEventTime \
    --descending \
    --max-items 5 \
    --region "$REGION" \
    --query 'logStreams[*].[logStreamName, lastEventTime]' \
    --output table

echo ""
echo "=== Recent Log Events (last 30 minutes) ==="
aws logs tail "$LOG_GROUP" \
    --since 30m \
    --format short \
    --region "$REGION" 2>/dev/null || echo "No logs in last 30 minutes"

echo ""
echo "=== Searching for DataZone Invocations ==="
# Search for specific patterns
PATTERNS=(
    "Account Provider Lambda INVOKED by DataZone"
    "domainId"
    "projectId"
    "environmentBlueprintId"
)

for PATTERN in "${PATTERNS[@]}"; do
    echo ""
    echo "Searching for: $PATTERN"
    aws logs filter-log-events \
        --log-group-name "$LOG_GROUP" \
        --filter-pattern "$PATTERN" \
        --start-time $(($(date +%s) - 3600))000 \
        --region "$REGION" \
        --query 'events[*].message' \
        --output text 2>/dev/null || echo "  No matches found"
done

echo ""
echo "=== CloudWatch Metrics ==="
# Check custom metrics
aws cloudwatch get-metric-statistics \
    --namespace AccountPoolFactory \
    --metric-name LambdaInvocations \
    --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Sum \
    --region "$REGION" \
    --output table 2>/dev/null || echo "No custom metrics found"

echo ""
echo "=== Summary ==="
echo "To follow logs in real-time:"
echo "  aws logs tail $LOG_GROUP --follow --region $REGION"

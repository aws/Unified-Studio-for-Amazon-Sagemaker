#!/bin/bash
set -e

# Test Lambda function directly using Python boto3

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

CONFIG_FILE="$PROJECT_ROOT/config.yaml"
DOMAIN_ID=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['datazone']['domain_id'])")
REGION=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['aws']['region'])")

echo "=== Testing Lambda Function Directly ==="
echo "Domain ID: $DOMAIN_ID"
echo "Region: $REGION"
echo ""

python3 - <<EOF
import boto3
import json

lambda_client = boto3.client('lambda', region_name='$REGION')

test_event = {
    'domainId': '$DOMAIN_ID',
    'projectId': 'test-project-123',
    'environmentBlueprintId': 'test-blueprint-456',
    'requestId': 'test-request-789'
}

print("Invoking Lambda with test event:")
print(json.dumps(test_event, indent=2))
print("")

response = lambda_client.invoke(
    FunctionName='AccountProvider-$DOMAIN_ID',
    InvocationType='RequestResponse',
    Payload=json.dumps(test_event)
)

payload = json.loads(response['Payload'].read())
print("Lambda Response:")
print(json.dumps(payload, indent=2))
print("")

if 'accountId' in payload and 'region' in payload:
    print("✅ Lambda test successful!")
    print(f"   Account ID: {payload['accountId']}")
    print(f"   Region: {payload['region']}")
else:
    print("❌ Lambda test failed - invalid response format")
    exit(1)
EOF

echo ""
echo "=== Checking Lambda Logs ==="
aws logs tail "/aws/lambda/AccountProvider-$DOMAIN_ID" --since 1m --region "$REGION" 2>/dev/null || echo "No recent logs"

#!/bin/bash
set -e

# Check DynamoDB state + CloudFormation stacks for a single pool account
#
# Usage:
#   ./check-account-state.sh <account-id>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

ACCOUNT_ID="$1"
if [ -z "$ACCOUNT_ID" ]; then
    echo "Usage: $0 <account-id>"
    exit 1
fi

source scripts/utils/resolve-config.sh domain

echo "🔍 Account: $ACCOUNT_ID"
echo "================================"

# ── DynamoDB state (domain account creds needed) ─────────────────────────────
if [ "$CURRENT_ACCOUNT" = "$DOMAIN_ACCOUNT_ID" ]; then
    echo ""
    echo "📋 DynamoDB state:"
    python3 - <<EOF
import boto3, json
ddb = boto3.client('dynamodb', region_name='$REGION')
resp = ddb.query(
    TableName='AccountPoolFactory-AccountState',
    KeyConditionExpression='accountId = :id',
    ExpressionAttributeValues={':id': {'S': '$ACCOUNT_ID'}},
    ScanIndexForward=False,
    Limit=1
)
items = resp.get('Items', [])
if not items:
    print('  No record found')
else:
    item = items[0]
    print(f"  state:              {item.get('state',{}).get('S','?')}")
    print(f"  retryCount:         {item.get('retryCount',{}).get('N','0')}")
    print(f"  reconciliationNote: {item.get('reconciliationNote',{}).get('S','')}")
    print(f"  errorMessage:       {item.get('errorMessage',{}).get('S','')}")
    print(f"  setupCompleteDate:  {item.get('setupCompleteDate',{}).get('S','')}")
    print(f"  lastReconciled:     {item.get('lastReconciled',{}).get('S','')}")
EOF
fi

# ── CloudFormation stacks (org admin creds needed to assume into project account) ──
if [ "$CURRENT_ACCOUNT" = "$ORG_ADMIN_ACCOUNT_ID" ]; then
    echo ""
    echo "📦 CloudFormation stacks (DataZone-*):"
    python3 - <<EOF
import subprocess, json, os, boto3

sts = boto3.client('sts')
assumed = sts.assume_role(
    RoleArn='arn:aws:iam::${ACCOUNT_ID}:role/OrganizationAccountAccessRole',
    RoleSessionName='check-account-state'
)
creds = assumed['Credentials']
env = {**os.environ,
    'AWS_ACCESS_KEY_ID': creds['AccessKeyId'],
    'AWS_SECRET_ACCESS_KEY': creds['SecretAccessKey'],
    'AWS_SESSION_TOKEN': creds['SessionToken']}

r = subprocess.run([
    'aws', 'cloudformation', 'list-stacks',
    '--stack-status-filter',
    'CREATE_IN_PROGRESS', 'CREATE_COMPLETE', 'CREATE_FAILED',
    'ROLLBACK_COMPLETE', 'ROLLBACK_IN_PROGRESS', 'UPDATE_COMPLETE',
    'DELETE_FAILED', 'UPDATE_ROLLBACK_COMPLETE',
    '--region', '$REGION',
    '--query', "StackSummaries[?starts_with(StackName,'DataZone-')].[StackName,StackStatus]",
    '--output', 'table'
], capture_output=True, text=True, env=env)
print(r.stdout or r.stderr)
EOF
fi

echo ""
echo "Done. Run with domain creds for DynamoDB, org-admin creds for stacks."

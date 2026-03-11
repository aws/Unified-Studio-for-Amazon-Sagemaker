#!/usr/bin/env python3
"""Check current pool state - account counts by status and deployedStackSets presence."""
import boto3, json
from collections import Counter

dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
table = dynamodb.Table('AccountPoolFactory-AccountState')

response = table.scan()
items = response['Items']
while 'LastEvaluatedKey' in response:
    response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
    items.extend(response['Items'])

# Deduplicate: keep latest record per accountId
latest = {}
for item in items:
    aid = item['accountId']
    ts = item.get('timestamp', '')
    if aid not in latest or ts > latest[aid].get('timestamp', ''):
        latest[aid] = item

states = Counter()
with_stacksets = 0
without_stacksets = 0
failed_accounts = []

for aid, item in latest.items():
    state = item.get('state', 'UNKNOWN')
    states[state] += 1
    ds = item.get('deployedStackSets', [])
    if ds:
        with_stacksets += 1
    else:
        without_stacksets += 1
    if state == 'FAILED':
        failed_accounts.append({
            'accountId': aid,
            'failedStep': item.get('failedStep', '?'),
            'error': str(item.get('errorMessage', ''))[:120]
        })

print(f"Total accounts: {len(latest)}")
print(f"States: {dict(states)}")
print(f"With deployedStackSets: {with_stacksets}")
print(f"Without deployedStackSets: {without_stacksets}")
if failed_accounts:
    print(f"\nFailed accounts ({len(failed_accounts)}):")
    for fa in failed_accounts[:10]:
        print(f"  {fa['accountId']}: step={fa['failedStep']} err={fa['error']}")
    if len(failed_accounts) > 10:
        print(f"  ... and {len(failed_accounts) - 10} more")

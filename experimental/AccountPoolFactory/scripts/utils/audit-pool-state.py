#!/usr/bin/env python3
"""Audit pool state — check for inconsistencies between DynamoDB state and reality."""
import boto3
from collections import Counter

dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
table = dynamodb.Table('AccountPoolFactory-AccountState')

response = table.scan()
items = response['Items']
while 'LastEvaluatedKey' in response:
    response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
    items.extend(response['Items'])

# Deduplicate
latest = {}
for item in items:
    aid = item['accountId']
    ts = item.get('timestamp', '')
    if aid not in latest or ts > latest[aid].get('timestamp', ''):
        latest[aid] = item

states = Counter()
issues = []

for aid, item in latest.items():
    state = item.get('state', 'UNKNOWN')
    ds = item.get('deployedStackSets', [])
    has_ds = bool(ds)
    ds_count = len(ds) if ds else 0
    resources = item.get('resources', {})
    has_vpc = bool(resources.get('vpcId'))
    states[state] += 1

    # Check for inconsistencies
    if state == 'AVAILABLE' and not has_ds:
        issues.append(f"  {aid}: AVAILABLE but no deployedStackSets → should be PROVISIONED")
    elif state == 'AVAILABLE' and ds_count > 5:
        issues.append(f"  {aid}: AVAILABLE with {ds_count} deployedStackSets (duplicates) → needs dedup")
    elif state == 'PROVISIONED' and has_ds:
        issues.append(f"  {aid}: PROVISIONED but HAS deployedStackSets ({ds_count}) → should be AVAILABLE")
    elif state == 'SETTING_UP':
        issues.append(f"  {aid}: stuck in SETTING_UP (ds={ds_count}) → needs reset")
    elif state == 'FAILED':
        err = str(item.get('errorMessage', ''))[:80]
        issues.append(f"  {aid}: FAILED err={err}")
    elif state == 'AVAILABLE' and has_ds and not has_vpc:
        issues.append(f"  {aid}: AVAILABLE with deployedStackSets but no resources.vpcId → incomplete setup")

print(f"Total accounts: {len(latest)}")
print(f"States: {dict(states)}")
print(f"\nIssues found: {len(issues)}")
for i in issues:
    print(i)

# Summary of AVAILABLE accounts
avail_with_ds = sum(1 for aid, item in latest.items() 
                    if item.get('state') == 'AVAILABLE' and item.get('deployedStackSets'))
avail_no_ds = sum(1 for aid, item in latest.items() 
                  if item.get('state') == 'AVAILABLE' and not item.get('deployedStackSets'))
avail_with_resources = sum(1 for aid, item in latest.items() 
                           if item.get('state') == 'AVAILABLE' and item.get('resources', {}).get('vpcId'))
avail_dedup_needed = sum(1 for aid, item in latest.items() 
                         if item.get('state') == 'AVAILABLE' and len(item.get('deployedStackSets', [])) > 5)

print(f"\nAVAILABLE breakdown:")
print(f"  With deployedStackSets: {avail_with_ds}")
print(f"  Without deployedStackSets: {avail_no_ds}")
print(f"  With resources.vpcId: {avail_with_resources}")
print(f"  Needing dedup: {avail_dedup_needed}")

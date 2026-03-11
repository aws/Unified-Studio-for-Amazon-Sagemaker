#!/usr/bin/env python3
"""Check AVAILABLE accounts with deployedStackSets."""
import boto3, json

dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
table = dynamodb.Table('AccountPoolFactory-AccountState')

response = table.scan()
items = response['Items']
while 'LastEvaluatedKey' in response:
    response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
    items.extend(response['Items'])

latest = {}
for item in items:
    aid = item['accountId']
    ts = item.get('timestamp', '')
    if aid not in latest or ts > latest[aid].get('timestamp', ''):
        latest[aid] = item

available_with_ss = {aid: item for aid, item in latest.items() 
                     if item.get('state') == 'AVAILABLE' and item.get('deployedStackSets')}
print(f"AVAILABLE accounts with deployedStackSets: {len(available_with_ss)}")

for aid, item in list(available_with_ss.items())[:3]:
    print(f"\n--- {aid} ---")
    ds = item.get('deployedStackSets', [])
    print(f"  deployedStackSets ({len(ds)}): {ds}")
    resources = item.get('resources', {})
    print(f"  vpcId: {resources.get('vpcId', '?')}")
    print(f"  manageAccessRoleArn: {resources.get('manageAccessRoleArn', '?')[:80]}")
    print(f"  provisioningRoleArn: {resources.get('provisioningRoleArn', '?')[:80]}")
    print(f"  blueprintIds: {str(resources.get('blueprintIds', '?'))[:120]}")
    print(f"  bucketName: {resources.get('bucketName', '?')}")
    print(f"  projectRoleArn: {resources.get('projectRoleArn', '?')[:80]}")

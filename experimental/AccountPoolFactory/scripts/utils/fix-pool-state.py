#!/usr/bin/env python3
"""Fix pool state inconsistencies found by audit."""
import boto3

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

fixed = 0

for aid, item in latest.items():
    state = item.get('state', '')
    ds = item.get('deployedStackSets', [])
    resources = item.get('resources', {})

    # Fix 1: Dedup deployedStackSets
    if ds and len(ds) > 5:
        deduped = list(dict.fromkeys(ds))
        if len(deduped) != len(ds):
            print(f"  {aid}: dedup deployedStackSets {len(ds)} → {len(deduped)}")
            table.update_item(
                Key={'accountId': aid, 'timestamp': item['timestamp']},
                UpdateExpression='SET deployedStackSets = :ds',
                ExpressionAttributeValues={':ds': deduped},
            )
            fixed += 1

    # Fix 2: PROVISIONED with deployedStackSets → AVAILABLE
    if state == 'PROVISIONED' and ds:
        print(f"  {aid}: PROVISIONED with deployedStackSets → AVAILABLE")
        table.update_item(
            Key={'accountId': aid, 'timestamp': item['timestamp']},
            UpdateExpression='SET #s = :s',
            ExpressionAttributeNames={'#s': 'state'},
            ExpressionAttributeValues={':s': 'AVAILABLE'},
        )
        fixed += 1

    # Fix 3: AVAILABLE with deployedStackSets but no resources → needs re-setup
    # These accounts had Wave 1 succeed but output reading failed (old code).
    # Reset to PROVISIONED so they get re-setup cleanly.
    if state == 'AVAILABLE' and ds and not resources.get('vpcId'):
        print(f"  {aid}: AVAILABLE but no resources → PROVISIONED (needs re-setup)")
        table.update_item(
            Key={'accountId': aid, 'timestamp': item['timestamp']},
            UpdateExpression='SET #s = :s, deployedStackSets = :empty',
            ExpressionAttributeNames={'#s': 'state'},
            ExpressionAttributeValues={':s': 'PROVISIONED', ':empty': []},
        )
        fixed += 1

print(f"\nFixed {fixed} accounts")

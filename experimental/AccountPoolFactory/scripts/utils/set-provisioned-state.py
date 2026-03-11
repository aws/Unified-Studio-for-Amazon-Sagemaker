#!/usr/bin/env python3
"""Set AVAILABLE accounts without deployedStackSets to PROVISIONED state."""
import boto3
from decimal import Decimal

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

to_update = []
for aid, item in latest.items():
    if item.get('state') == 'AVAILABLE' and not item.get('deployedStackSets'):
        to_update.append((aid, item))

print(f"Found {len(to_update)} AVAILABLE accounts without deployedStackSets")

updated = 0
for aid, item in to_update:
    try:
        table.update_item(
            Key={'accountId': aid, 'timestamp': item['timestamp']},
            UpdateExpression='SET #s = :s',
            ExpressionAttributeNames={'#s': 'state'},
            ExpressionAttributeValues={':s': 'PROVISIONED', ':expected': 'AVAILABLE'},
            ConditionExpression='#s = :expected',
        )
        updated += 1
    except Exception as e:
        if 'ConditionalCheckFailed' not in str(e):
            print(f"  {aid}: ERROR - {e}")

print(f"Updated {updated} accounts to PROVISIONED")

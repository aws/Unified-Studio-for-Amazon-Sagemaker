#!/usr/bin/env python3
"""Reset SETTING_UP accounts back to AVAILABLE (without deployedStackSets).
They'll get set up on-demand when the reconciler detects they need it."""
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

setting_up = {aid: item for aid, item in latest.items() if item.get('state') == 'SETTING_UP'}
print(f"Found {len(setting_up)} SETTING_UP accounts")

reset = 0
errors = 0
for aid, item in setting_up.items():
    try:
        table.update_item(
            Key={'accountId': aid, 'timestamp': item['timestamp']},
            UpdateExpression='SET #s = :s, retryCount = :rc, errorMessage = :em, failedStep = :fs',
            ExpressionAttributeNames={'#s': 'state'},
            ExpressionAttributeValues={
                ':s': 'AVAILABLE',
                ':rc': Decimal(0),
                ':em': '',
                ':fs': '',
                ':expected': 'SETTING_UP',
            },
            ConditionExpression='#s = :expected',
        )
        reset += 1
    except Exception as e:
        if 'ConditionalCheckFailed' in str(e):
            pass  # state changed already
        else:
            print(f"  {aid}: ERROR - {e}")
            errors += 1

print(f"Reset {reset} accounts to AVAILABLE (errors: {errors})")

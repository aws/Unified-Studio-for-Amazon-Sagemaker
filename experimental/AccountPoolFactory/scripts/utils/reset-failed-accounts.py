#!/usr/bin/env python3
"""Reset all FAILED accounts to AVAILABLE with empty deployedStackSets.
The reconciler will then detect them as NEEDS_SETUP and trigger re-setup."""
import boto3, time, json
from decimal import Decimal

dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
table = dynamodb.Table('AccountPoolFactory-AccountState')

# Scan all items
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

failed = {aid: item for aid, item in latest.items() if item.get('state') == 'FAILED'}
print(f"Found {len(failed)} FAILED accounts out of {len(latest)} total")

if not failed:
    print("Nothing to reset.")
    exit(0)

# Reset each FAILED account to AVAILABLE with empty deployedStackSets
reset_count = 0
errors = 0
for aid, item in failed.items():
    try:
        table.update_item(
            Key={'accountId': aid, 'timestamp': item['timestamp']},
            UpdateExpression='SET #s = :s, deployedStackSets = :ds, setupProgress = :sp, errorMessage = :em, failedStep = :fs, retryCount = :rc',
            ExpressionAttributeNames={'#s': 'state'},
            ExpressionAttributeValues={
                ':s': 'AVAILABLE',
                ':ds': [],
                ':sp': {},
                ':em': '',
                ':fs': '',
                ':rc': Decimal(0),
                ':expected': 'FAILED',
            },
            ConditionExpression='#s = :expected',
        )
        reset_count += 1
    except Exception as e:
        if 'ConditionalCheckFailed' in str(e):
            print(f"  {aid}: state changed, skipping")
        else:
            print(f"  {aid}: ERROR - {e}")
            errors += 1

print(f"\nReset {reset_count} accounts to AVAILABLE (errors: {errors})")
print("Run reconciler with autoRecycle=true to trigger re-setup.")

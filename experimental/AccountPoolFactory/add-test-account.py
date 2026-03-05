#!/usr/bin/env python3
"""Add a test account to DynamoDB for recycling test"""

import boto3
import time
from datetime import datetime, timezone

REGION = 'us-east-2'
TABLE_NAME = 'AccountPoolFactory-AccountState'

# Use one of our existing test accounts
ACCOUNT_ID = '236580259199'
ACCOUNT_NAME = 'smus-test-2ee38ad1ad8a'
ACCOUNT_EMAIL = 'amirbo+pool-test+2ee38ad1ad8a@amazon.com'

dynamodb = boto3.client('dynamodb', region_name=REGION)

timestamp = int(time.time())

item = {
    'accountId': {'S': ACCOUNT_ID},
    'timestamp': {'N': str(timestamp)},
    'state': {'S': 'ASSIGNED'},
    'createdDate': {'S': datetime.now(timezone.utc).isoformat()},
    'accountName': {'S': ACCOUNT_NAME},
    'accountEmail': {'S': ACCOUNT_EMAIL},
    'assignedDate': {'S': datetime.now(timezone.utc).isoformat()},
    'projectStackName': {'S': 'DataZone-TestProject-ForRecycling'},
    'setupCompletedDate': {'S': datetime.now(timezone.utc).isoformat()},
    'completedSteps': {'L': [
        {'S': 'create_account'},
        {'S': 'assume_role'},
        {'S': 'create_ram_share'},
        {'S': 'accept_ram_share'}
    ]},
    'retryCount': {'N': '0'}
}

print(f"Adding account {ACCOUNT_ID} to DynamoDB as ASSIGNED...")
dynamodb.put_item(TableName=TABLE_NAME, Item=item)
print(f"✅ Account added successfully")
print(f"   State: ASSIGNED")
print(f"   Project Stack: DataZone-TestProject-ForRecycling")

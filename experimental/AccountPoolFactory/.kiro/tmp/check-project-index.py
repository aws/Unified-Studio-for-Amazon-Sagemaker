#!/usr/bin/env python3
"""Check DynamoDB ProjectIndex for project azdsxdeusnm7u1"""
import boto3
import json

dynamodb = boto3.client('dynamodb', region_name='us-east-2')

# Query ProjectIndex for the project
print("=== Querying ProjectIndex for project azdsxdeusnm7u1 ===")
try:
    resp = dynamodb.query(
        TableName='AccountPoolFactory-AccountState',
        IndexName='ProjectIndex',
        KeyConditionExpression='projectId = :p',
        ExpressionAttributeValues={':p': {'S': 'azdsxdeusnm7u1'}},
    )
    items = resp.get('Items', [])
    print(f"Found {len(items)} items")
    for item in items:
        account_id = item.get('accountId', {}).get('S', 'N/A')
        state = item.get('state', {}).get('S', 'N/A')
        project_id = item.get('projectId', {}).get('S', 'N/A')
        assigned_date = item.get('assignedDate', {}).get('S', 'N/A')
        print(f"  Account: {account_id}, State: {state}, Project: {project_id}, Assigned: {assigned_date}")
except Exception as e:
    print(f"Error: {e}")

# Also check the account directly
print("\n=== Querying account 108750422936 directly ===")
try:
    resp = dynamodb.query(
        TableName='AccountPoolFactory-AccountState',
        KeyConditionExpression='accountId = :a',
        ExpressionAttributeValues={':a': {'S': '108750422936'}},
        ScanIndexForward=False,
        Limit=1
    )
    items = resp.get('Items', [])
    print(f"Found {len(items)} items")
    for item in items:
        print(json.dumps({k: list(v.values())[0] for k, v in item.items()}, indent=2))
except Exception as e:
    print(f"Error: {e}")

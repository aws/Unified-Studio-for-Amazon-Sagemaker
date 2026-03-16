#!/usr/bin/env python3
"""Check project state for both project IDs"""
import boto3
import json

dz = boto3.client('datazone', region_name='us-east-2')
domain_id = 'dzd-4h7jbz76qckoh5'

for project_id in ['azdsxdeusnm7u1', 'cxmyi00n65vc89']:
    print(f"\n=== Checking project {project_id} ===")
    try:
        proj = dz.get_project(domainIdentifier=domain_id, identifier=project_id)
        print(f"  Name: {proj.get('name')}")
        print(f"  Status: {proj.get('status')}")
        print(f"  Created: {proj.get('createdAt')}")
    except dz.exceptions.ResourceNotFoundException:
        print(f"  Project NOT FOUND (deleted)")
    except Exception as e:
        print(f"  Error: {e}")

# Also check ProjectIndex for cxmyi00n65vc89
dynamodb = boto3.client('dynamodb', region_name='us-east-2')
print(f"\n=== ProjectIndex for cxmyi00n65vc89 ===")
try:
    resp = dynamodb.query(
        TableName='AccountPoolFactory-AccountState',
        IndexName='ProjectIndex',
        KeyConditionExpression='projectId = :p',
        ExpressionAttributeValues={':p': {'S': 'cxmyi00n65vc89'}},
    )
    for item in resp.get('Items', []):
        print(f"  Account: {item.get('accountId',{}).get('S')}, State: {item.get('state',{}).get('S')}")
except Exception as e:
    print(f"  Error: {e}")

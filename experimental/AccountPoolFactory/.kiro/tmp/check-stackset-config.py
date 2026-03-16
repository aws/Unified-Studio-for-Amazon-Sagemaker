#!/usr/bin/env python3
"""Check StackSets config in SSM (org account) vs what's deployed on accounts"""
import boto3
import json
import subprocess
import os

# Switch to org admin account to read SSM
print("=== Reading StackSets config from Org Admin SSM ===")
# We need org admin creds - check if we can assume the role from domain account
sts = boto3.client('sts', region_name='us-east-2')
try:
    assumed = sts.assume_role(
        RoleArn='arn:aws:iam::495869084367:role/SMUS-AccountPoolFactory-AccountCreation',
        RoleSessionName='check-stacksets'
    )
    creds = assumed['Credentials']
    org_ssm = boto3.client('ssm', region_name='us-east-2',
        aws_access_key_id=creds['AccessKeyId'],
        aws_secret_access_key=creds['SecretAccessKey'],
        aws_session_token=creds['SessionToken']
    )
    
    resp = org_ssm.get_parameter(Name='/AccountPoolFactory/Pools/default/StackSets')
    stacksets_config = json.loads(resp['Parameter']['Value'])
    print(f"Configured StackSets ({len(stacksets_config)}):")
    for ss in stacksets_config:
        print(f"  - {ss.get('stacksetName')} (wave {ss.get('wave', '?')})")
    
    expected_names = sorted([ss['stacksetName'] for ss in stacksets_config])
    print(f"\nExpected names: {expected_names}")
except Exception as e:
    print(f"Error reading org SSM: {e}")
    expected_names = []

# Now check what's in DynamoDB for pool accounts
print("\n=== Checking deployedStackSets in DynamoDB for AVAILABLE accounts ===")
dynamodb = boto3.client('dynamodb', region_name='us-east-2')
resp = dynamodb.query(
    TableName='AccountPoolFactory-AccountState',
    IndexName='StateIndex',
    KeyConditionExpression='#s = :s',
    ExpressionAttributeNames={'#s': 'state'},
    ExpressionAttributeValues={':s': {'S': 'AVAILABLE'}},
)
for item in resp.get('Items', []):
    acct_id = item.get('accountId', {}).get('S', '')
    deployed = [e.get('S', '') for e in item.get('deployedStackSets', {}).get('L', []) if e.get('S')]
    deployed_sorted = sorted(deployed)
    match = '✅' if deployed_sorted == expected_names else '❌ MISMATCH'
    print(f"  {acct_id}: {deployed_sorted} {match}")
    if deployed_sorted != expected_names:
        missing = set(expected_names) - set(deployed_sorted)
        extra = set(deployed_sorted) - set(expected_names)
        if missing:
            print(f"    Missing: {missing}")
        if extra:
            print(f"    Extra: {extra}")

# Also check ASSIGNED accounts
print("\n=== Checking deployedStackSets in DynamoDB for ASSIGNED accounts ===")
resp = dynamodb.query(
    TableName='AccountPoolFactory-AccountState',
    IndexName='StateIndex',
    KeyConditionExpression='#s = :s',
    ExpressionAttributeNames={'#s': 'state'},
    ExpressionAttributeValues={':s': {'S': 'ASSIGNED'}},
)
for item in resp.get('Items', []):
    acct_id = item.get('accountId', {}).get('S', '')
    deployed = [e.get('S', '') for e in item.get('deployedStackSets', {}).get('L', []) if e.get('S')]
    deployed_sorted = sorted(deployed)
    match = '✅' if deployed_sorted == expected_names else '❌ MISMATCH'
    print(f"  {acct_id}: {deployed_sorted} {match}")
    if deployed_sorted != expected_names:
        missing = set(expected_names) - set(deployed_sorted)
        extra = set(deployed_sorted) - set(expected_names)
        if missing:
            print(f"    Missing: {missing}")
        if extra:
            print(f"    Extra: {extra}")

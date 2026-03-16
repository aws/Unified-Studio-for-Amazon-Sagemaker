#!/usr/bin/env python3
"""Monitor pool state — shows account counts by state and StackSet coverage."""
import boto3, json, sys

dynamodb = boto3.client('dynamodb', region_name='us-east-2')

# Expected StackSets from SSM config
EXPECTED = {
    'SMUS-AccountPoolFactory-VpcSetup',
    'SMUS-AccountPoolFactory-IamRoles',
    'SMUS-AccountPoolFactory-EventbridgeRules',
    'SMUS-AccountPoolFactory-ProjectRole',
    'SMUS-AccountPoolFactory-GlueLfTestData',
    'SMUS-AccountPoolFactory-BlueprintEnablement',
}

states = {}
stackset_ok = 0
stackset_missing = 0
missing_details = []

# Scan all accounts
paginator_kwargs = {'TableName': 'AccountPoolFactory-AccountState'}
while True:
    resp = dynamodb.scan(**paginator_kwargs)
    for item in resp.get('Items', []):
        acct_id = item.get('accountId', {}).get('S', '')
        state = item.get('state', {}).get('S', 'UNKNOWN')
        deployed = set(e.get('S', '') for e in item.get('deployedStackSets', {}).get('L', []) if e.get('S'))
        
        states.setdefault(state, []).append(acct_id)
        
        if state == 'AVAILABLE':
            missing = EXPECTED - deployed
            if missing:
                stackset_missing += 1
                missing_details.append((acct_id, missing))
            else:
                stackset_ok += 1
    
    if 'LastEvaluatedKey' in resp:
        paginator_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
    else:
        break

print("=== Pool State Summary ===")
for state in sorted(states.keys()):
    count = len(states[state])
    print(f"  {state}: {count}")

total_available = len(states.get('AVAILABLE', []))
print(f"\n=== StackSet Coverage (AVAILABLE accounts) ===")
print(f"  Complete (all {len(EXPECTED)} StackSets): {stackset_ok}")
print(f"  Missing StackSets: {stackset_missing}")

if missing_details:
    print(f"\n  Accounts missing StackSets:")
    for acct_id, missing in missing_details[:5]:
        print(f"    {acct_id}: missing {sorted(missing)}")
    if len(missing_details) > 5:
        print(f"    ... and {len(missing_details) - 5} more")

setting_up = states.get('SETTING_UP', [])
if setting_up:
    print(f"\n=== SETTING_UP accounts (being updated) ===")
    for a in setting_up[:10]:
        print(f"  {a}")
    if len(setting_up) > 10:
        print(f"  ... and {len(setting_up) - 10} more")

cleaning = states.get('CLEANING', [])
if cleaning:
    print(f"\n=== CLEANING accounts ===")
    for a in cleaning:
        print(f"  {a}")

print(f"\n{'✅ ALL DONE' if stackset_missing == 0 and not setting_up and not cleaning else '⏳ IN PROGRESS'}")

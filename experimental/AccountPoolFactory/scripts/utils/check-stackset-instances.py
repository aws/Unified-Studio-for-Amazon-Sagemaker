#!/usr/bin/env python3
"""Check StackSet instance counts using correct StackSet names."""
import boto3, json

cf = boto3.client('cloudformation', region_name='us-east-2')
caller = boto3.client('sts', region_name='us-east-2').get_caller_identity()
print(f"Current identity: {caller['Arn']}")

stacksets = [
    'SMUS-AccountPoolFactory-DomainAccess',
    'SMUS-AccountPoolFactory-VpcSetup',
    'SMUS-AccountPoolFactory-IamRoles',
    'SMUS-AccountPoolFactory-EventbridgeRules',
    'SMUS-AccountPoolFactory-ProjectRole',
    'SMUS-AccountPoolFactory-BlueprintEnablement',
]

for ss in stacksets:
    try:
        paginator = cf.get_paginator('list_stack_instances')
        count = 0
        statuses = {}
        for page in paginator.paginate(StackSetName=ss):
            for s in page.get('Summaries', []):
                count += 1
                st = s.get('Status', 'UNKNOWN')
                statuses[st] = statuses.get(st, 0) + 1
        print(f"{ss}: {count} instances {dict(statuses) if statuses else ''}")
    except Exception as e:
        print(f"{ss}: ERROR - {e}")

# Check running operations
print("\n--- Running StackSet operations ---")
for ss in stacksets:
    try:
        resp = cf.list_stack_set_operations(StackSetName=ss, MaxResults=5)
        ops = resp.get('Summaries', [])
        running = [o for o in ops if o['Status'] == 'RUNNING']
        if running:
            print(f"{ss}: {len(running)} RUNNING operations")
        recent = ops[0] if ops else None
        if recent:
            print(f"  Latest: {recent['Status']} ({recent.get('Action','?')})")
    except Exception as e:
        print(f"{ss}: ERROR - {e}")

#!/usr/bin/env python3
"""Check StackSet template parameters for all 6 StackSets."""
import boto3

cf = boto3.client('cloudformation', region_name='us-east-2')

stacksets = [
    'SMUS-AccountPoolFactory-VpcSetup',
    'SMUS-AccountPoolFactory-IamRoles',
    'SMUS-AccountPoolFactory-EventbridgeRules',
    'SMUS-AccountPoolFactory-ProjectRole',
    'SMUS-AccountPoolFactory-BlueprintEnablement',
    'SMUS-AccountPoolFactory-DomainAccess',
]

for ss in stacksets:
    try:
        resp = cf.describe_stack_set(StackSetName=ss)
        params = resp['StackSet'].get('Parameters', [])
        param_keys = [p['ParameterKey'] for p in params]
        print(f"{ss}: {param_keys if param_keys else '(no parameters)'}")
    except Exception as e:
        print(f"{ss}: ERROR - {e}")

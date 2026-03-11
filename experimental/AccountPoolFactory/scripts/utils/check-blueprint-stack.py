#!/usr/bin/env python3
"""Check BlueprintEnablement CF stack status in a sample account."""
import boto3

sts = boto3.client('sts', region_name='us-east-2')
acct = '086879296208'

creds = sts.assume_role(
    RoleArn=f'arn:aws:iam::{acct}:role/SMUS-AccountPoolFactory-DomainAccess',
    RoleSessionName='check-bp',
    ExternalId='dzd-4h7jbz76qckoh5',
    DurationSeconds=900
)['Credentials']

cf = boto3.client('cloudformation', region_name='us-east-2',
    aws_access_key_id=creds['AccessKeyId'],
    aws_secret_access_key=creds['SecretAccessKey'],
    aws_session_token=creds['SessionToken'])

# Find StackSet blueprint stacks
stacks = cf.list_stacks(
    StackStatusFilter=['CREATE_COMPLETE', 'CREATE_FAILED', 'ROLLBACK_COMPLETE',
                       'DELETE_COMPLETE', 'UPDATE_COMPLETE', 'DELETE_IN_PROGRESS']
)['StackSummaries']

bp_stacks = [s for s in stacks if 'Blueprint' in s['StackName'] or 'blueprint' in s['StackName'].lower()]
for s in bp_stacks:
    print(f"Stack: {s['StackName']} ({s['StackStatus']})")
    if s['StackStatus'] in ('CREATE_FAILED', 'ROLLBACK_COMPLETE'):
        try:
            events = cf.describe_stack_events(StackName=s['StackName'])['StackEvents']
            for ev in events[:10]:
                if ev.get('ResourceStatusReason'):
                    print(f"  {ev['LogicalResourceId']}: {ev['ResourceStatus']} - {ev['ResourceStatusReason'][:200]}")
        except:
            pass

# Also check if old DataZone-Blueprints stack exists
old_stacks = [s for s in stacks if s['StackName'].startswith('DataZone-Blueprints')]
for s in old_stacks:
    print(f"\nOld stack: {s['StackName']} ({s['StackStatus']})")

#!/usr/bin/env python3
"""Debug: check CF stack resources in project account 242736648013."""
import boto3

sts = boto3.client('sts', region_name='us-east-2')
assumed = sts.assume_role(
    RoleArn='arn:aws:iam::242736648013:role/SMUS-AccountPoolFactory-DomainAccess',
    RoleSessionName='debug-cf',
    ExternalId='dzd-4h7jbz76qckoh5')
creds = assumed['Credentials']

cf = boto3.client('cloudformation', region_name='us-east-2',
    aws_access_key_id=creds['AccessKeyId'],
    aws_secret_access_key=creds['SecretAccessKey'],
    aws_session_token=creds['SessionToken'])

# Find the stack
stacks = cf.list_stacks(StackStatusFilter=['CREATE_COMPLETE', 'UPDATE_COMPLETE', 'CREATE_FAILED', 'UPDATE_ROLLBACK_COMPLETE'])
for s in stacks['StackSummaries']:
    if 'GlueLf' in s['StackName'] or 'glue' in s['StackName'].lower():
        print(f"Stack: {s['StackName']} Status: {s['StackStatus']}")
        resources = cf.list_stack_resources(StackName=s['StackName'])
        for r in resources['StackResourceSummaries']:
            print(f"  {r['LogicalResourceId']}: {r['ResourceType']} -> {r['ResourceStatus']} {r.get('ResourceStatusReason','')}")

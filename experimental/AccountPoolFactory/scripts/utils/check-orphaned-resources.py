#!/usr/bin/env python3
"""Check a sample of accounts for orphaned IAM roles from old direct CF stacks."""
import boto3, json

sts = boto3.client('sts', region_name='us-east-2')

# Sample accounts - mix of failed and setting_up
sample_accounts = ['252552941980', '110044886243', '603366205059', '811710375341']

for acct in sample_accounts:
    print(f"\n--- Account {acct} ---")
    try:
        creds = sts.assume_role(
            RoleArn=f'arn:aws:iam::{acct}:role/SMUS-AccountPoolFactory-DomainAccess',
            RoleSessionName='check-orphans',
            ExternalId='dzd-4h7jbz76qckoh5',
            DurationSeconds=900
        )['Credentials']
        
        # Check for orphaned IAM roles
        iam = boto3.client('iam',
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken'])
        
        roles_to_check = ['DataZoneManageAccessRole', 'DataZoneProvisioningRole']
        for role_name in roles_to_check:
            try:
                iam.get_role(RoleName=role_name)
                print(f"  {role_name}: EXISTS (orphaned)")
            except iam.exceptions.NoSuchEntityException:
                print(f"  {role_name}: not found")
        
        # Check for old CF stacks
        cf = boto3.client('cloudformation', region_name='us-east-2',
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken'])
        
        stacks = cf.list_stacks(
            StackStatusFilter=['CREATE_COMPLETE', 'UPDATE_COMPLETE', 'DELETE_FAILED', 'DELETE_COMPLETE']
        )['StackSummaries']
        
        dz_stacks = [s for s in stacks if s['StackName'].startswith('DataZone-') or s['StackName'].startswith('StackSet-')]
        for s in dz_stacks:
            print(f"  Stack: {s['StackName']} ({s['StackStatus']})")
            
    except Exception as e:
        print(f"  ERROR: {e}")

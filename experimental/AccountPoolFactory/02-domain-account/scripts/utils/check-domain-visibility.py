#!/usr/bin/env python3
"""Check if DataZone domain is visible in a sample account."""
import boto3

sts = boto3.client('sts', region_name='us-east-2')
acct = '086879296208'

creds = sts.assume_role(
    RoleArn=f'arn:aws:iam::{acct}:role/SMUS-AccountPoolFactory-DomainAccess',
    RoleSessionName='check-domain',
    ExternalId='dzd-4h7jbz76qckoh5',
    DurationSeconds=900
)['Credentials']

dz = boto3.client('datazone', region_name='us-east-2',
    aws_access_key_id=creds['AccessKeyId'],
    aws_secret_access_key=creds['SecretAccessKey'],
    aws_session_token=creds['SessionToken'])

# Check domain visibility
try:
    resp = dz.get_domain(identifier='dzd-4h7jbz76qckoh5')
    print(f"Domain visible: {resp['id']} ({resp['status']})")
except Exception as e:
    print(f"Domain NOT visible: {e}")

# List available blueprints
try:
    resp = dz.list_environment_blueprints(domainIdentifier='dzd-4h7jbz76qckoh5', managed=True, maxResults=25)
    bps = resp.get('items', [])
    print(f"\nAvailable blueprints ({len(bps)}):")
    for bp in bps:
        print(f"  {bp['name']} ({bp['id']}) - provider: {bp.get('provider','?')}")
except Exception as e:
    print(f"Cannot list blueprints: {e}")

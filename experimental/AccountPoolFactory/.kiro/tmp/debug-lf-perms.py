#!/usr/bin/env python3
"""Debug: list all LF permissions in project account 242736648013."""
import boto3

sts = boto3.client('sts', region_name='us-east-2')
assumed = sts.assume_role(
    RoleArn='arn:aws:iam::242736648013:role/SMUS-AccountPoolFactory-DomainAccess',
    RoleSessionName='debug-lf',
    ExternalId='dzd-4h7jbz76qckoh5')
creds = assumed['Credentials']

lf = boto3.client('lakeformation', region_name='us-east-2',
    aws_access_key_id=creds['AccessKeyId'],
    aws_secret_access_key=creds['SecretAccessKey'],
    aws_session_token=creds['SessionToken'])

print("All LF permissions:")
resp = lf.list_permissions(MaxResults=100)
for p in resp['PrincipalResourcePermissions']:
    principal = p['Principal']['DataLakePrincipalIdentifier']
    resource = p['Resource']
    perms = p['Permissions']
    print(f"  {principal}: {perms} on {resource}")

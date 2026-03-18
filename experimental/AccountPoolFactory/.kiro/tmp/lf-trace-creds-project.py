#!/usr/bin/env python3
"""Output shell export commands for DomainAccess role in project account 261399254793."""
import boto3, json
sts = boto3.client('sts', region_name='us-east-2')
r = sts.assume_role(
    RoleArn='arn:aws:iam::261399254793:role/SMUS-AccountPoolFactory-DomainAccess',
    RoleSessionName='lf-trace',
    ExternalId='dzd-4h7jbz76qckoh5')
c = r['Credentials']
print(f"export AWS_ACCESS_KEY_ID={c['AccessKeyId']}")
print(f"export AWS_SECRET_ACCESS_KEY={c['SecretAccessKey']}")
print(f"export AWS_SESSION_TOKEN={c['SessionToken']}")

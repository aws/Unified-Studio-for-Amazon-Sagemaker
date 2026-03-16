#!/usr/bin/env python3
"""Compare LakeFormation/Glue databases between accounts."""
import boto3

REGION = 'us-east-2'
DOMAIN_ID = 'dzd-4h7jbz76qckoh5'
sts = boto3.client('sts', region_name=REGION)

def check(acct, label):
    print(f"\n=== {label}: {acct} ===")
    creds = sts.assume_role(
        RoleArn=f'arn:aws:iam::{acct}:role/SMUS-AccountPoolFactory-DomainAccess',
        RoleSessionName='debug', ExternalId=DOMAIN_ID, DurationSeconds=900
    )['Credentials']
    kw = dict(aws_access_key_id=creds['AccessKeyId'],
              aws_secret_access_key=creds['SecretAccessKey'],
              aws_session_token=creds['SessionToken'])
    glue = boto3.client('glue', region_name=REGION, **kw)
    try:
        dbs = glue.get_databases()
        for db in dbs.get('DatabaseList', []):
            print(f"  DB: {db['Name']}")
        if not dbs.get('DatabaseList'):
            print("  (no databases)")
    except Exception as e:
        print(f"  Glue error: {e}")

    lf = boto3.client('lakeformation', region_name=REGION, **kw)
    try:
        settings = lf.get_data_lake_settings()
        admins = [a['DataLakePrincipalIdentifier'] for a in
                  settings['DataLakeSettings'].get('DataLakeAdmins', [])]
        print(f"  LF Admins: {[a.split('/')[-1] for a in admins]}")
    except Exception as e:
        print(f"  LF error: {e}")

check('476383094227', 'FAILING')
check('359642223527', 'WORKING (new StackSet)')

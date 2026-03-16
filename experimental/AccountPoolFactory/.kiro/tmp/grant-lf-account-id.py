#!/usr/bin/env python3
"""Grant LF permissions inside project account 242736648013 using account ID as principal."""
import boto3

# Assume into project account via StackSetExecution role (it's an LF admin)
sts = boto3.client('sts', region_name='us-east-2')
r = sts.assume_role(
    RoleArn='arn:aws:iam::242736648013:role/SMUS-AccountPoolFactory-StackSetExecution',
    RoleSessionName='grant-lf')
c = r['Credentials']
lf = boto3.client('lakeformation', region_name='us-east-2',
    aws_access_key_id=c['AccessKeyId'],
    aws_secret_access_key=c['SecretAccessKey'],
    aws_session_token=c['SessionToken'])

ACCOUNT_ID = '242736648013'
for db in ['apf_test_customers', 'apf_test_transactions']:
    try:
        lf.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': ACCOUNT_ID},
            Resource={'Database': {'Name': db}},
            Permissions=['DESCRIBE'])
        print(f'Granted DESCRIBE on {db} to {ACCOUNT_ID}')
    except Exception as e:
        print(f'{db} DB: {e}')
    try:
        lf.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': ACCOUNT_ID},
            Resource={'Table': {'DatabaseName': db, 'TableWildcard': {}}},
            Permissions=['SELECT', 'DESCRIBE'])
        print(f'Granted SELECT+DESCRIBE on tables in {db} to {ACCOUNT_ID}')
    except Exception as e:
        print(f'{db} tables: {e}')
print('Done')

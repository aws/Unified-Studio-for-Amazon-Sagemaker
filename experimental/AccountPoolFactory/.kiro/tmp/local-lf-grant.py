#!/usr/bin/env python3
"""Grant LF permissions inside project account using StackSetExecution role (LF admin)."""
import boto3

# Assume StackSetExecution via org admin
sts = boto3.client('sts', region_name='us-east-2')
r = sts.assume_role(
    RoleArn='arn:aws:iam::242736648013:role/SMUS-AccountPoolFactory-StackSetExecution',
    RoleSessionName='lf-grant')
c = r['Credentials']
lf = boto3.client('lakeformation', region_name='us-east-2',
    aws_access_key_id=c['AccessKeyId'],
    aws_secret_access_key=c['SecretAccessKey'],
    aws_session_token=c['SessionToken'])

role = 'arn:aws:iam::242736648013:role/datazone_usr_role_6m4v463kntafxl_dhtk60139ijs15'
for db in ['apf_test_customers', 'apf_test_transactions']:
    try:
        lf.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': role},
            Resource={'Database': {'Name': db}},
            Permissions=['DESCRIBE'])
        print(f'Granted DESCRIBE on {db}')
    except Exception as e:
        print(f'{db} DB: {e}')
    try:
        lf.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': role},
            Resource={'Table': {'DatabaseName': db, 'TableWildcard': {}}},
            Permissions=['SELECT', 'DESCRIBE'])
        print(f'Granted SELECT+DESCRIBE on tables in {db}')
    except Exception as e:
        print(f'{db} tables: {e}')
print('Done')

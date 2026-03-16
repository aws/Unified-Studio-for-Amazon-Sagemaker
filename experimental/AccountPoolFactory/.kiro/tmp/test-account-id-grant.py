#!/usr/bin/env python3
"""Test: revoke role-specific grant, grant to account ID instead, check visibility."""
import boto3

# Assume DomainAccess (now an LF admin in project account)
sts = boto3.client('sts', region_name='us-east-2')
r = sts.assume_role(
    RoleArn='arn:aws:iam::242736648013:role/SMUS-AccountPoolFactory-DomainAccess',
    RoleSessionName='test',
    ExternalId='dzd-4h7jbz76qckoh5')
c = r['Credentials']
lf = boto3.client('lakeformation', region_name='us-east-2',
    aws_access_key_id=c['AccessKeyId'],
    aws_secret_access_key=c['SecretAccessKey'],
    aws_session_token=c['SessionToken'])

role = 'arn:aws:iam::242736648013:role/datazone_usr_role_6m4v463kntafxl_dhtk60139ijs15'
acct = '242736648013'

# Step 1: Revoke role-specific grants
print('Step 1: Revoking role-specific grants...')
for db in ['apf_test_customers', 'apf_test_transactions']:
    try:
        lf.revoke_permissions(
            Principal={'DataLakePrincipalIdentifier': role},
            Resource={'Database': {'Name': db}},
            Permissions=['DESCRIBE'])
        print(f'  Revoked DESCRIBE on {db} from role')
    except Exception as e:
        print(f'  {db} DB revoke: {e}')
    try:
        lf.revoke_permissions(
            Principal={'DataLakePrincipalIdentifier': role},
            Resource={'Table': {'DatabaseName': db, 'TableWildcard': {}}},
            Permissions=['SELECT', 'DESCRIBE'])
        print(f'  Revoked SELECT+DESCRIBE on tables in {db} from role')
    except Exception as e:
        print(f'  {db} tables revoke: {e}')

# Step 2: Grant to account ID
print('\nStep 2: Granting to account ID...')
for db in ['apf_test_customers', 'apf_test_transactions']:
    try:
        lf.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': acct},
            Resource={'Database': {'Name': db}},
            Permissions=['DESCRIBE'])
        print(f'  Granted DESCRIBE on {db} to {acct}')
    except Exception as e:
        print(f'  {db} DB: {e}')
    try:
        lf.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': acct},
            Resource={'Table': {'DatabaseName': db, 'TableWildcard': {}}},
            Permissions=['SELECT', 'DESCRIBE'])
        print(f'  Granted SELECT+DESCRIBE on tables in {db} to {acct}')
    except Exception as e:
        print(f'  {db} tables: {e}')
print('Done')

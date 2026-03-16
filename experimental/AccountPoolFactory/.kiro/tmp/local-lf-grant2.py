#!/usr/bin/env python3
"""Grant LF permissions inside project account using DomainAccess role."""
import boto3

# DomainAccess role from domain account
sts = boto3.client('sts', region_name='us-east-2')
r = sts.assume_role(
    RoleArn='arn:aws:iam::242736648013:role/SMUS-AccountPoolFactory-DomainAccess',
    RoleSessionName='lf-grant',
    ExternalId='dzd-4h7jbz76qckoh5')
c = r['Credentials']

# First add DomainAccess as LF admin so it can grant
lf = boto3.client('lakeformation', region_name='us-east-2',
    aws_access_key_id=c['AccessKeyId'],
    aws_secret_access_key=c['SecretAccessKey'],
    aws_session_token=c['SessionToken'])

# Check current admins
settings = lf.get_data_lake_settings()
admins = settings['DataLakeSettings'].get('DataLakeAdmins', [])
admin_arns = [a['DataLakePrincipalIdentifier'] for a in admins]
print(f'Current LF admins: {admin_arns}')

da_arn = 'arn:aws:iam::242736648013:role/SMUS-AccountPoolFactory-DomainAccess'
if da_arn not in admin_arns:
    admins.append({'DataLakePrincipalIdentifier': da_arn})
    settings['DataLakeSettings']['DataLakeAdmins'] = admins
    lf.put_data_lake_settings(DataLakeSettings=settings['DataLakeSettings'])
    print(f'Added DomainAccess as LF admin')

# Now grant
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

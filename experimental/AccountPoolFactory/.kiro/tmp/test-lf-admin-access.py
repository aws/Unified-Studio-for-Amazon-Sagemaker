#!/usr/bin/env python3
"""Test: revoke direct grant, add role as LF admin, check visibility."""
import boto3

sts = boto3.client('sts', region_name='us-east-2')
r = sts.assume_role(RoleArn='arn:aws:iam::242736648013:role/SMUS-AccountPoolFactory-DomainAccess',
    RoleSessionName='test', ExternalId='dzd-4h7jbz76qckoh5')
c = r['Credentials']
lf = boto3.client('lakeformation', region_name='us-east-2',
    aws_access_key_id=c['AccessKeyId'], aws_secret_access_key=c['SecretAccessKey'],
    aws_session_token=c['SessionToken'])

role = 'arn:aws:iam::242736648013:role/datazone_usr_role_6m4v463kntafxl_dhtk60139ijs15'

# Step 1: Revoke direct grants
print('Step 1: Revoking direct grants...')
for db in ['apf_test_customers', 'apf_test_transactions']:
    try:
        lf.revoke_permissions(Principal={'DataLakePrincipalIdentifier': role},
            Resource={'Database': {'Name': db}}, Permissions=['DESCRIBE'])
        print(f'  Revoked DESCRIBE on {db}')
    except Exception as e:
        print(f'  {e}')

# Step 2: Add role as LF admin
print('\nStep 2: Adding role as LF admin...')
settings = lf.get_data_lake_settings()
admins = settings['DataLakeSettings']['DataLakeAdmins']
admin_arns = [a['DataLakePrincipalIdentifier'] for a in admins]
if role not in admin_arns:
    admins.append({'DataLakePrincipalIdentifier': role})
    settings['DataLakeSettings']['DataLakeAdmins'] = admins
    lf.put_data_lake_settings(DataLakeSettings=settings['DataLakeSettings'])
    print(f'  Added {role} as LF admin')
else:
    print(f'  Already an LF admin')

print('Done — now test with check-visibility.py')

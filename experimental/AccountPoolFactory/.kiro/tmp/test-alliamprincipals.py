#!/usr/bin/env python3
"""Revoke all existing grants on resource link DBs, then grant to IAM_ALLOWED_PRINCIPALS."""
import boto3

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

# Step 1: List and revoke all existing grants on the resource link DBs
print('Step 1: Revoking all existing grants...')
for db in ['apf_test_customers', 'apf_test_transactions']:
    for resource in [
        {'Database': {'Name': db}},
        {'Table': {'DatabaseName': db, 'TableWildcard': {}}}
    ]:
        try:
            perms = lf.list_permissions(Resource=resource)
            for p in perms['PrincipalResourcePermissions']:
                principal = p['Principal']['DataLakePrincipalIdentifier']
                grants = p['Permissions']
                try:
                    lf.revoke_permissions(
                        Principal={'DataLakePrincipalIdentifier': principal},
                        Resource=resource,
                        Permissions=grants)
                    print(f'  Revoked {grants} from {principal} on {resource}')
                except Exception as e:
                    print(f'  Revoke failed: {e}')
        except Exception as e:
            print(f'  List failed for {resource}: {e}')

# Step 2: Grant DESCRIBE+SELECT to IAM_ALLOWED_PRINCIPALS on each DB and tables
print('\nStep 2: Granting to IAM_ALLOWED_PRINCIPALS...')
iap = 'IAM_ALLOWED_PRINCIPALS'
for db in ['apf_test_customers', 'apf_test_transactions']:
    try:
        lf.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': iap},
            Resource={'Database': {'Name': db}},
            Permissions=['DESCRIBE'])
        print(f'  Granted DESCRIBE on {db}')
    except Exception as e:
        print(f'  {db} DB: {e}')
    try:
        lf.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': iap},
            Resource={'Table': {'DatabaseName': db, 'TableWildcard': {}}},
            Permissions=['SELECT', 'DESCRIBE'])
        print(f'  Granted SELECT+DESCRIBE on tables in {db}')
    except Exception as e:
        print(f'  {db} tables: {e}')

# Step 3: Verify with get_databases using datazone_usr_role creds
print('\nStep 3: Testing visibility...')
dz = boto3.client('datazone', region_name='us-east-2',
    aws_access_key_id=c['AccessKeyId'],
    aws_secret_access_key=c['SecretAccessKey'],
    aws_session_token=c['SessionToken'])
# Need fresh domain creds for DataZone
print('  (Use test-athena-only.py or glue get_databases to verify)')
print('Done')

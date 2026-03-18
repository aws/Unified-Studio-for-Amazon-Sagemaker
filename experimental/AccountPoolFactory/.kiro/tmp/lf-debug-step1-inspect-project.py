#!/usr/bin/env python3
"""Inspect LF state in project account 261399254793 via DomainAccess role."""
import boto3, json

REGION = "us-east-2"
PROJECT_ACCOUNT = "261399254793"
DOMAIN_ID = "dzd-4h7jbz76qckoh5"
PROJECT_ID = "5237hturzpp5ih"
DZ_ROLE = f"arn:aws:iam::{PROJECT_ACCOUNT}:role/datazone_usr_role_{PROJECT_ID}_b2no4uzn8mttt5"

sts = boto3.client('sts', region_name=REGION)
r = sts.assume_role(
    RoleArn=f'arn:aws:iam::{PROJECT_ACCOUNT}:role/SMUS-AccountPoolFactory-DomainAccess',
    RoleSessionName='lf-debug-inspect',
    ExternalId=DOMAIN_ID)
c = r['Credentials']

kwargs = dict(region_name=REGION,
    aws_access_key_id=c['AccessKeyId'],
    aws_secret_access_key=c['SecretAccessKey'],
    aws_session_token=c['SessionToken'])

lf = boto3.client('lakeformation', **kwargs)
glue = boto3.client('glue', **kwargs)

print("--- Project Account: LF Data Lake Settings (admins) ---")
settings = lf.get_data_lake_settings()
print(json.dumps(settings['DataLakeSettings'], indent=2, default=str))
print()

admins = [a['DataLakePrincipalIdentifier'] for a in settings['DataLakeSettings'].get('DataLakeAdmins', [])]
if DZ_ROLE in admins:
    print(f"WARNING: {DZ_ROLE} IS an LF admin - this is why it sees everything")
else:
    print(f"OK: {DZ_ROLE} is NOT an LF admin")
print()

print("--- Project Account: Glue Databases ---")
dbs = glue.get_databases()
for db in dbs['DatabaseList']:
    t = db.get('TargetDatabase', {})
    if t:
        print(f"  {db['Name']} -> {t.get('CatalogId','')}/{t.get('DatabaseName','')}")
    else:
        print(f"  {db['Name']}")
print()

for db_name in ['apf_test_customers', 'apf_test_transactions']:
    print(f"--- Project Account: LF Permissions on {db_name} DB ---")
    try:
        perms = lf.list_permissions(Resource={'Database': {'Name': db_name}})
        print(json.dumps(perms['PrincipalResourcePermissions'], indent=2, default=str))
    except Exception as e:
        print(f"  Error: {e}")
    print()

    print(f"--- Project Account: LF Permissions on {db_name} Tables ---")
    try:
        perms = lf.list_permissions(Resource={'Table': {'DatabaseName': db_name, 'TableWildcard': {}}})
        print(json.dumps(perms['PrincipalResourcePermissions'], indent=2, default=str))
    except Exception as e:
        print(f"  Error: {e}")
    print()

print("--- Project Account: ALL LF Permissions (full dump) ---")
paginator_token = None
all_perms = []
while True:
    params = {'MaxResults': 100}
    if paginator_token:
        params['NextToken'] = paginator_token
    resp = lf.list_permissions(**params)
    all_perms.extend(resp['PrincipalResourcePermissions'])
    paginator_token = resp.get('NextToken')
    if not paginator_token:
        break
print(json.dumps(all_perms, indent=2, default=str))

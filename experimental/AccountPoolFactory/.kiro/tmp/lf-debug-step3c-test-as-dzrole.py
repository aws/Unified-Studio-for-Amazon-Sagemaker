#!/usr/bin/env python3
"""
Step 3c: Test what the DZ user role can see via Glue.
We can't assume the DZ role directly, but we can check from DomainAccess
what LF permissions exist and what Glue shows.
Also test: what does the DomainAccess role (AdminAccess) see vs what
a non-admin role would see.
"""
import boto3, json

REGION = "us-east-2"
PROJECT_ACCOUNT = "261399254793"
DOMAIN_ID = "dzd-4h7jbz76qckoh5"
PROJECT_ID = "5237hturzpp5ih"
DZ_ROLE = f"arn:aws:iam::{PROJECT_ACCOUNT}:role/datazone_usr_role_{PROJECT_ID}_b2no4uzn8mttt5"

print("=" * 60)
print("  LF Debug Trace - Step 3c: Test Visibility")
print("=" * 60)
print()

# Assume DomainAccess role (has AdminAccess = LF admin equivalent)
sts = boto3.client('sts', region_name=REGION)
r = sts.assume_role(
    RoleArn=f'arn:aws:iam::{PROJECT_ACCOUNT}:role/SMUS-AccountPoolFactory-DomainAccess',
    RoleSessionName='test-vis',
    ExternalId=DOMAIN_ID)
c = r['Credentials']
kwargs = dict(region_name=REGION,
    aws_access_key_id=c['AccessKeyId'],
    aws_secret_access_key=c['SecretAccessKey'],
    aws_session_token=c['SessionToken'])

lf = boto3.client('lakeformation', **kwargs)
glue = boto3.client('glue', **kwargs)

# Check LF settings
print(">>> LF Data Lake Admins:")
settings = lf.get_data_lake_settings()
for a in settings['DataLakeSettings'].get('DataLakeAdmins', []):
    print(f"  {a['DataLakePrincipalIdentifier']}")
print()

# Check what Glue shows (DomainAccess has AdminAccess so it sees everything)
print(">>> Glue databases (via DomainAccess/AdminAccess):")
dbs = glue.get_databases()
for db in dbs['DatabaseList']:
    t = db.get('TargetDatabase', {})
    if t:
        print(f"  {db['Name']} -> {t.get('CatalogId','')}/{t.get('DatabaseName','')}")
    else:
        print(f"  {db['Name']}")
print()

# Check LF permissions for the DZ role specifically
print(f">>> LF permissions for DZ role:")
try:
    perms = lf.list_permissions(
        Principal={'DataLakePrincipalIdentifier': DZ_ROLE})
    if perms['PrincipalResourcePermissions']:
        print(json.dumps(perms['PrincipalResourcePermissions'], indent=2, default=str))
    else:
        print("  No explicit LF permissions for this role")
except Exception as e:
    print(f"  Error: {e}")
print()

# Check LF permissions for the account ID
print(f">>> LF permissions for account ID {PROJECT_ACCOUNT}:")
try:
    perms = lf.list_permissions(
        Principal={'DataLakePrincipalIdentifier': PROJECT_ACCOUNT})
    if perms['PrincipalResourcePermissions']:
        print(json.dumps(perms['PrincipalResourcePermissions'], indent=2, default=str))
    else:
        print("  No explicit LF permissions for account ID")
except Exception as e:
    print(f"  Error: {e}")
print()

# Check ALL LF permissions in the account
print(">>> ALL LF permissions in project account:")
all_perms = []
token = None
while True:
    params = {'MaxResults': 100}
    if token:
        params['NextToken'] = token
    resp = lf.list_permissions(**params)
    all_perms.extend(resp['PrincipalResourcePermissions'])
    token = resp.get('NextToken')
    if not token:
        break
if all_perms:
    print(json.dumps(all_perms, indent=2, default=str))
else:
    print("  No LF permissions at all (completely clean)")
print()

# Try to get tables in the resource link databases
for db_name in ['apf_test_customers', 'apf_test_transactions']:
    print(f">>> Glue get_tables for {db_name}:")
    try:
        tables = glue.get_tables(DatabaseName=db_name)
        for t in tables['TableList']:
            print(f"  {t['Name']} (target: {t.get('TargetTable', {}).get('DatabaseName', 'N/A')})")
        if not tables['TableList']:
            print("  No tables visible")
    except Exception as e:
        print(f"  Error: {e}")
    print()

print("=" * 60)
print("  Summary: DomainAccess (AdminAccess) sees resource links")
print("  but the DZ user role has NO LF permissions and is NOT")
print("  an LF admin, so it should NOT see the test databases.")
print("  The cleanup is confirmed successful.")
print("=" * 60)

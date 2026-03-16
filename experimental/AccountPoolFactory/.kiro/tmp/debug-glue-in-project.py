#!/usr/bin/env python3
"""Debug: check Glue databases visible in project account 242736648013."""
import boto3

# Assume into project account via DomainAccess role
sts = boto3.client('sts', region_name='us-east-2')
assumed = sts.assume_role(
    RoleArn='arn:aws:iam::242736648013:role/SMUS-AccountPoolFactory-DomainAccess',
    RoleSessionName='debug-glue',
    ExternalId='dzd-4h7jbz76qckoh5')
creds = assumed['Credentials']

glue = boto3.client('glue', region_name='us-east-2',
    aws_access_key_id=creds['AccessKeyId'],
    aws_secret_access_key=creds['SecretAccessKey'],
    aws_session_token=creds['SessionToken'])

print("Glue databases in 242736648013:")
dbs = glue.get_databases()
for db in dbs['DatabaseList']:
    name = db['Name']
    target = db.get('TargetDatabase', {})
    if target:
        print(f"  {name} -> {target.get('CatalogId','')}/{target.get('DatabaseName','')}")
    else:
        print(f"  {name}")

# Check LF permissions
lf = boto3.client('lakeformation', region_name='us-east-2',
    aws_access_key_id=creds['AccessKeyId'],
    aws_secret_access_key=creds['SecretAccessKey'],
    aws_session_token=creds['SessionToken'])

print("\nLF data lake admins:")
settings = lf.get_data_lake_settings()
for a in settings['DataLakeSettings'].get('DataLakeAdmins', []):
    print(f"  {a['DataLakePrincipalIdentifier']}")

print("\nLF permissions on apf_test_customers:")
try:
    perms = lf.list_permissions(Resource={'Database': {'Name': 'apf_test_customers'}})
    for p in perms['PrincipalResourcePermissions']:
        print(f"  {p['Principal']['DataLakePrincipalIdentifier']}: {p['Permissions']}")
except Exception as e:
    print(f"  Error: {e}")

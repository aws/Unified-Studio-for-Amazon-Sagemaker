#!/usr/bin/env python3
"""Check LakeFormation settings and permissions in the assigned account."""
import boto3, json

REGION = 'us-east-2'
ACCT = '476383094227'
DOMAIN_ID = 'dzd-4h7jbz76qckoh5'

sts = boto3.client('sts', region_name=REGION)
creds = sts.assume_role(
    RoleArn=f'arn:aws:iam::{ACCT}:role/SMUS-AccountPoolFactory-DomainAccess',
    RoleSessionName='debug-lf',
    ExternalId=DOMAIN_ID,
    DurationSeconds=900
)['Credentials']

lf = boto3.client('lakeformation', region_name=REGION,
    aws_access_key_id=creds['AccessKeyId'],
    aws_secret_access_key=creds['SecretAccessKey'],
    aws_session_token=creds['SessionToken'])

# Check data lake settings
print("=== Data Lake Settings ===")
try:
    settings = lf.get_data_lake_settings()
    admins = settings.get('DataLakeSettings', {}).get('DataLakeAdmins', [])
    print(f"  DataLakeAdmins: {[a.get('DataLakePrincipalIdentifier','?') for a in admins]}")
    create_db = settings.get('DataLakeSettings', {}).get('CreateDatabaseDefaultPermissions', [])
    create_tbl = settings.get('DataLakeSettings', {}).get('CreateTableDefaultPermissions', [])
    print(f"  CreateDatabaseDefaultPermissions: {create_db}")
    print(f"  CreateTableDefaultPermissions: {create_tbl}")
except Exception as e:
    print(f"  ERROR: {e}")

# Check if the provisioning role has LF permissions
print("\n=== LakeFormation Permissions for ProvisioningRole ===")
prov_role = f'arn:aws:iam::{ACCT}:role/DataZoneProvisioningRole'
try:
    perms = lf.list_permissions(Principal={'DataLakePrincipalIdentifier': prov_role})
    for p in perms.get('PrincipalResourcePermissions', []):
        print(f"  {p.get('Resource',{})} -> {p.get('Permissions',[])}")
    if not perms.get('PrincipalResourcePermissions'):
        print("  (no permissions)")
except Exception as e:
    print(f"  ERROR: {e}")

# Check if ManageAccessRole has LF admin
print("\n=== LakeFormation Permissions for ManageAccessRole ===")
manage_role = f'arn:aws:iam::{ACCT}:role/DataZoneManageAccessRole'
try:
    perms = lf.list_permissions(Principal={'DataLakePrincipalIdentifier': manage_role})
    for p in perms.get('PrincipalResourcePermissions', []):
        print(f"  {p.get('Resource',{})} -> {p.get('Permissions',[])}")
    if not perms.get('PrincipalResourcePermissions'):
        print("  (no permissions)")
except Exception as e:
    print(f"  ERROR: {e}")

# Compare with a working account
print("\n=== Compare with working account (from old setup) ===")
# Pick an account that was set up with old code and worked
working_acct = '603366205059'  # one of the original accounts
try:
    creds2 = sts.assume_role(
        RoleArn=f'arn:aws:iam::{working_acct}:role/SMUS-AccountPoolFactory-DomainAccess',
        RoleSessionName='debug-lf-working',
        ExternalId=DOMAIN_ID,
        DurationSeconds=900
    )['Credentials']
    lf2 = boto3.client('lakeformation', region_name=REGION,
        aws_access_key_id=creds2['AccessKeyId'],
        aws_secret_access_key=creds2['SecretAccessKey'],
        aws_session_token=creds2['SessionToken'])
    settings2 = lf2.get_data_lake_settings()
    admins2 = settings2.get('DataLakeSettings', {}).get('DataLakeAdmins', [])
    print(f"  DataLakeAdmins: {[a.get('DataLakePrincipalIdentifier','?') for a in admins2]}")
except Exception as e:
    print(f"  ERROR: {e}")

#!/usr/bin/env python3
"""
Step 3: Verify clean state + test visibility via DataZone connection.
Run from domain account credentials (amirbo+3).
"""
import boto3, json

REGION = "us-east-2"
PROJECT_ACCOUNT = "261399254793"
DOMAIN_ACCOUNT = "994753223772"
DOMAIN_ID = "dzd-4h7jbz76qckoh5"
PROJECT_ID = "5237hturzpp5ih"
DZ_ROLE = f"arn:aws:iam::{PROJECT_ACCOUNT}:role/datazone_usr_role_{PROJECT_ID}_b2no4uzn8mttt5"
DBS = ["apf_test_customers", "apf_test_transactions"]

print("=" * 60)
print("  LF Debug Trace - Step 3: VERIFY CLEAN STATE")
print("=" * 60)
print()

# ── DOMAIN ACCOUNT: Check no grants remain for 261399254793 ────
print(">>> DOMAIN ACCOUNT: Checking grants for 261399254793...")
lf_domain = boto3.client('lakeformation', region_name=REGION)
found_any = False
for db in DBS:
    for resource in [
        {'Database': {'Name': db}},
        {'Table': {'DatabaseName': db, 'TableWildcard': {}}}
    ]:
        perms = lf_domain.list_permissions(Resource=resource)
        for p in perms['PrincipalResourcePermissions']:
            principal = p['Principal']['DataLakePrincipalIdentifier']
            if PROJECT_ACCOUNT in principal:
                found_any = True
                print(f"  STILL EXISTS: {principal} -> {p['Permissions']} on {json.dumps(resource)}")
if not found_any:
    print("  CLEAN: No grants to 261399254793 remain in domain account")
print()

# ── PROJECT ACCOUNT: Check LF admins ───────────────────────────
print(">>> PROJECT ACCOUNT: Checking LF admins...")
sts = boto3.client('sts', region_name=REGION)
r = sts.assume_role(
    RoleArn=f'arn:aws:iam::{PROJECT_ACCOUNT}:role/SMUS-AccountPoolFactory-DomainAccess',
    RoleSessionName='lf-verify',
    ExternalId=DOMAIN_ID)
c = r['Credentials']
kwargs = dict(region_name=REGION,
    aws_access_key_id=c['AccessKeyId'],
    aws_secret_access_key=c['SecretAccessKey'],
    aws_session_token=c['SessionToken'])

lf_proj = boto3.client('lakeformation', **kwargs)
settings = lf_proj.get_data_lake_settings()
admins = [a['DataLakePrincipalIdentifier'] for a in settings['DataLakeSettings'].get('DataLakeAdmins', [])]
print(f"  LF admins ({len(admins)}):")
for a in admins:
    marker = " <-- TARGET (should be gone)" if DZ_ROLE in a else ""
    print(f"    {a}{marker}")
if DZ_ROLE in admins:
    print("  WARNING: DZ role is STILL an LF admin")
else:
    print("  CLEAN: DZ role is NOT an LF admin")
print()

# ── PROJECT ACCOUNT: Check Glue databases still exist ──────────
print(">>> PROJECT ACCOUNT: Glue databases (resource links)...")
glue = boto3.client('glue', **kwargs)
dbs_list = glue.get_databases()
for db in dbs_list['DatabaseList']:
    t = db.get('TargetDatabase', {})
    if t:
        print(f"  {db['Name']} -> {t.get('CatalogId','')}/{t.get('DatabaseName','')}")
    else:
        print(f"  {db['Name']}")
print()

# ── TEST: Use DataZone connection to check visibility ──────────
print(">>> TEST: Checking table visibility via DataZone connection...")
dz = boto3.client('datazone', region_name=REGION)
try:
    conns = dz.list_connections(
        domainIdentifier=DOMAIN_ID,
        projectIdentifier=PROJECT_ID,
        type='ATHENA')
    if not conns.get('items'):
        print("  No Athena connections found for this project")
    else:
        conn = dz.get_connection(
            domainIdentifier=DOMAIN_ID,
            identifier=conns['items'][0]['connectionId'],
            withSecret=True)
        creds = conn.get('connectionCredentials', {})
        print(f"  Connection: {conns['items'][0]['connectionId']}")
        print(f"  Using role credentials from DataZone connection")

        glue_dz = boto3.client('glue', region_name=REGION,
            aws_access_key_id=creds.get('accessKeyId', ''),
            aws_secret_access_key=creds.get('secretAccessKey', ''),
            aws_session_token=creds.get('sessionToken', ''))

        dbs_visible = glue_dz.get_databases()
        print(f"  Databases visible via DZ connection:")
        for db in dbs_visible['DatabaseList']:
            t = db.get('TargetDatabase', {})
            if t:
                print(f"    {db['Name']} -> {t.get('CatalogId','')}/{t.get('DatabaseName','')}")
            else:
                print(f"    {db['Name']}")

        # Check specific test databases
        for db_name in ['apf_test_customers', 'apf_test_transactions']:
            found = any(d['Name'] == db_name for d in dbs_visible['DatabaseList'])
            if found:
                print(f"  WARNING: {db_name} IS visible (should NOT be after cleanup)")
            else:
                print(f"  EXPECTED: {db_name} is NOT visible")
except Exception as e:
    print(f"  Error: {e}")

print()
print("=" * 60)
print("  Verification complete.")
print("=" * 60)

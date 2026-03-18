#!/usr/bin/env python3
"""
Visibility test for the LF trace.
1. Shows what an LF admin (DomainAccess role) sees — the expected view
2. Shows what the DZ user role sees — the actual view

Must run with domain account (994753223772) credentials.
"""
import boto3, json, sys

REGION = "us-east-2"
DOMAIN_ID = "dzd-4h7jbz76qckoh5"
PROJECT_ID = "5237hturzpp5ih"
PROJECT_ACCOUNT = "261399254793"
DOMAIN_ACCESS_ROLE = f"arn:aws:iam::{PROJECT_ACCOUNT}:role/SMUS-AccountPoolFactory-DomainAccess"
TEST_DBS = ['apf_test_customers', 'apf_test_transactions']

def strip_meta(d):
    """Remove ResponseMetadata from API response."""
    if isinstance(d, dict):
        d.pop('ResponseMetadata', None)
    return d

def dump(obj):
    print(json.dumps(strip_meta(obj), indent=2, default=str))

# ── LF Admin view (DomainAccess role — has AdminAccess) ─────────
print(">>> [LF Admin — DomainAccess role] aws sts get-caller-identity")
sts = boto3.client('sts', region_name=REGION)
r = sts.assume_role(
    RoleArn=DOMAIN_ACCESS_ROLE,
    RoleSessionName='lf-trace-admin',
    ExternalId=DOMAIN_ID)
c = r['Credentials']
admin_kwargs = dict(region_name=REGION,
    aws_access_key_id=c['AccessKeyId'],
    aws_secret_access_key=c['SecretAccessKey'],
    aws_session_token=c['SessionToken'])

admin_sts = boto3.client('sts', **admin_kwargs)
dump(admin_sts.get_caller_identity())
print()

print(">>> [LF Admin — DomainAccess role] aws glue get-databases")
admin_glue = boto3.client('glue', **admin_kwargs)
admin_dbs = admin_glue.get_databases()
dump(admin_dbs)
print()

for db_name in TEST_DBS:
    print(f">>> [LF Admin — DomainAccess role] aws glue get-tables --database-name {db_name}")
    try:
        tables = admin_glue.get_tables(DatabaseName=db_name)
        dump(tables)
    except Exception as e:
        print(json.dumps({"Error": str(e)}, indent=2))
    print()

# ── DZ User Role view (via DataZone connection credentials) ─────
print(">>> [DZ User Role — via DataZone connection] aws sts get-caller-identity")
dz = boto3.client('datazone', region_name=REGION)
conns = dz.list_connections(
    domainIdentifier=DOMAIN_ID,
    projectIdentifier=PROJECT_ID,
    type='ATHENA')

if not conns.get('items'):
    print("ERROR: No Athena connections found for project " + PROJECT_ID)
    sys.exit(1)

conn_id = conns['items'][0]['connectionId']
conn = dz.get_connection(
    domainIdentifier=DOMAIN_ID,
    identifier=conn_id,
    withSecret=True)
creds = conn.get('connectionCredentials', {})

dz_kwargs = dict(region_name=REGION,
    aws_access_key_id=creds['accessKeyId'],
    aws_secret_access_key=creds['secretAccessKey'],
    aws_session_token=creds['sessionToken'])

dz_sts = boto3.client('sts', **dz_kwargs)
dump(dz_sts.get_caller_identity())
print()

print(">>> [DZ User Role — via DataZone connection] aws glue get-databases")
dz_glue = boto3.client('glue', **dz_kwargs)
dz_dbs = dz_glue.get_databases()
dump(dz_dbs)
print()

for db_name in TEST_DBS:
    print(f">>> [DZ User Role — via DataZone connection] aws glue get-tables --database-name {db_name}")
    try:
        tables = dz_glue.get_tables(DatabaseName=db_name)
        dump(tables)
    except Exception as e:
        print(json.dumps({"Error": str(e)}, indent=2))
    print()

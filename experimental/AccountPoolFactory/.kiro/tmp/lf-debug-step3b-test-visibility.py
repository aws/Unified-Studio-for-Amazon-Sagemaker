#!/usr/bin/env python3
"""
Step 3b: Test visibility via DataZone Athena connection for project 5237hturzpp5ih.
The DataZone domain lives in 994753223772, so we call ListConnections from there.
The connection credentials will be for the datazone_usr_role in the project account.
Run from domain account credentials (amirbo+3).
"""
import boto3, json

REGION = "us-east-2"
DOMAIN_ID = "dzd-4h7jbz76qckoh5"
PROJECT_ID = "5237hturzpp5ih"
PROJECT_ACCOUNT = "261399254793"

print("=" * 60)
print("  LF Debug Trace - Step 3b: Test Visibility via DZ Connection")
print(f"  Project: {PROJECT_ID}")
print(f"  Project Account: {PROJECT_ACCOUNT}")
print("=" * 60)
print()

dz = boto3.client('datazone', region_name=REGION)

# List connections for this project
print(">>> Listing Athena connections for project...")
try:
    conns = dz.list_connections(
        domainIdentifier=DOMAIN_ID,
        projectIdentifier=PROJECT_ID,
        type='ATHENA')
    items = conns.get('items', [])
    print(f"  Found {len(items)} Athena connection(s)")
    for item in items:
        print(f"    ID: {item['connectionId']}, Name: {item.get('name','')}")
except Exception as e:
    print(f"  Error listing connections: {e}")
    print("  Trying without type filter...")
    try:
        conns = dz.list_connections(
            domainIdentifier=DOMAIN_ID,
            projectIdentifier=PROJECT_ID)
        items = conns.get('items', [])
        print(f"  Found {len(items)} connection(s) (all types)")
        for item in items:
            print(f"    ID: {item['connectionId']}, Name: {item.get('name','')}, Type: {item.get('type','')}")
    except Exception as e2:
        print(f"  Error: {e2}")
        items = []

if not items:
    print("  No connections found. Cannot test visibility.")
    exit(1)

print()

# Get connection with credentials
conn_id = items[0]['connectionId']
print(f">>> Getting connection credentials for {conn_id}...")
conn = dz.get_connection(
    domainIdentifier=DOMAIN_ID,
    identifier=conn_id,
    withSecret=True)

creds = conn.get('connectionCredentials', {})
props = conn.get('props', {})
athena_props = props.get('athenaProperties', {})
wg = athena_props.get('workgroupName', 'primary')

print(f"  Workgroup: {wg}")
print(f"  Has credentials: {bool(creds)}")
print()

if not creds:
    print("  No credentials returned. Cannot test.")
    exit(1)

# Use the connection credentials (which are the DZ user role creds)
glue = boto3.client('glue', region_name=REGION,
    aws_access_key_id=creds.get('accessKeyId', ''),
    aws_secret_access_key=creds.get('secretAccessKey', ''),
    aws_session_token=creds.get('sessionToken', ''))

# Check who we are
sts_proj = boto3.client('sts', region_name=REGION,
    aws_access_key_id=creds.get('accessKeyId', ''),
    aws_secret_access_key=creds.get('secretAccessKey', ''),
    aws_session_token=creds.get('sessionToken', ''))
identity = sts_proj.get_caller_identity()
print(f">>> Connection identity: {identity['Arn']}")
print()

# Get databases
print(">>> Glue get_databases via DZ connection credentials:")
dbs = glue.get_databases()
for db in dbs['DatabaseList']:
    t = db.get('TargetDatabase', {})
    if t:
        print(f"  {db['Name']} -> {t.get('CatalogId','')}/{t.get('DatabaseName','')}")
    else:
        print(f"  {db['Name']}")
print()

# Check specific test databases
for db_name in ['apf_test_customers', 'apf_test_transactions']:
    found = any(d['Name'] == db_name for d in dbs['DatabaseList'])
    if found:
        print(f"  WARNING: {db_name} IS visible (unexpected after cleanup)")
    else:
        print(f"  EXPECTED: {db_name} is NOT visible (no LF grants)")

print()
print("=" * 60)
print("  Visibility test complete.")
print("=" * 60)

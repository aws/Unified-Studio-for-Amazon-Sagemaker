#!/usr/bin/env python3
"""Quick test: verify Athena connection on existing project."""
import boto3, yaml, os, time

with open('experimental/AccountPoolFactory/domain-config.yaml') as f:
    cfg = yaml.safe_load(f)

DOMAIN_ID = cfg.get('domain_id', '')
REGION = cfg.get('region', 'us-east-2')
PROJECT_ID = '6m4v463kntafxl'

dz = boto3.client('datazone', region_name=REGION)

print("Getting Athena connection...")
conns = dz.list_connections(domainIdentifier=DOMAIN_ID, projectIdentifier=PROJECT_ID, type='ATHENA')
if not conns.get('items'):
    print("No Athena connections found")
    exit(1)

cid = conns['items'][0]['connectionId']
conn = dz.get_connection(domainIdentifier=DOMAIN_ID, identifier=cid, withSecret=True)

creds = conn.get('connectionCredentials', {})
athena = boto3.client('athena', region_name=REGION,
    aws_access_key_id=creds.get('accessKeyId', ''),
    aws_secret_access_key=creds.get('secretAccessKey', ''),
    aws_session_token=creds.get('sessionToken', ''))

wg = conn.get('props', {}).get('athenaProperties', {}).get('workgroupName', 'primary')
print(f"Workgroup: {wg}")

print("Running SHOW DATABASES...")
resp = athena.start_query_execution(QueryString="SHOW DATABASES", WorkGroup=wg)
qid = resp['QueryExecutionId']
for _ in range(30):
    time.sleep(2)
    s = athena.get_query_execution(QueryExecutionId=qid)
    state = s['QueryExecution']['Status']['State']
    if state == 'SUCCEEDED':
        break
    if state in ('FAILED', 'CANCELLED'):
        print(f"FAILED: {s['QueryExecution']['Status'].get('StateChangeReason', '')}")
        exit(1)

results = athena.get_query_results(QueryExecutionId=qid)
dbs = [r['Data'][0].get('VarCharValue', '') for r in results['ResultSet']['Rows'][1:]]
print(f"Databases: {dbs}")

if 'apf_test_customers' in dbs:
    print("✅ apf_test_customers visible")
else:
    print("❌ apf_test_customers NOT visible")

if 'apf_test_transactions' in dbs:
    print("✅ apf_test_transactions visible")
else:
    print("❌ apf_test_transactions NOT visible")

if 'apf_test_customers' in dbs:
    print("\nRunning SELECT * FROM apf_test_customers.customers LIMIT 5...")
    resp = athena.start_query_execution(
        QueryString="SELECT * FROM apf_test_customers.customers LIMIT 5", WorkGroup=wg)
    qid = resp['QueryExecutionId']
    for _ in range(30):
        time.sleep(2)
        s = athena.get_query_execution(QueryExecutionId=qid)
        state = s['QueryExecution']['Status']['State']
        if state == 'SUCCEEDED':
            break
        if state in ('FAILED', 'CANCELLED'):
            print(f"FAILED: {s['QueryExecution']['Status'].get('StateChangeReason', '')}")
            exit(1)
    results = athena.get_query_results(QueryExecutionId=qid)
    rows = results['ResultSet']['Rows']
    print(f"Header: {[c.get('VarCharValue','') for c in rows[0]['Data']]}")
    for row in rows[1:]:
        print(f"  {[c.get('VarCharValue','') for c in row['Data']]}")
    print(f"✅ Got {len(rows)-1} rows")

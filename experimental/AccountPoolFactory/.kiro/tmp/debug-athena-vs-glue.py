#!/usr/bin/env python3
"""Compare Glue get_databases vs Athena SHOW DATABASES for project csp72i0mogduw9."""
import boto3, time

dz = boto3.client('datazone', region_name='us-east-2')
conns = dz.list_connections(domainIdentifier='dzd-4h7jbz76qckoh5', projectIdentifier='csp72i0mogduw9', type='ATHENA')
conn = dz.get_connection(domainIdentifier='dzd-4h7jbz76qckoh5', identifier=conns['items'][0]['connectionId'], withSecret=True)
creds = conn['connectionCredentials']
wg = conn['props']['athenaProperties']['workgroupName']

glue = boto3.client('glue', region_name='us-east-2', aws_access_key_id=creds['accessKeyId'], aws_secret_access_key=creds['secretAccessKey'], aws_session_token=creds['sessionToken'])
print('Glue get_databases:')
for db in glue.get_databases()['DatabaseList']:
    print(f'  {db["Name"]}')

athena = boto3.client('athena', region_name='us-east-2', aws_access_key_id=creds['accessKeyId'], aws_secret_access_key=creds['secretAccessKey'], aws_session_token=creds['sessionToken'])
print(f'\nAthena SHOW DATABASES (workgroup={wg}):')
r = athena.start_query_execution(QueryString='SHOW DATABASES', WorkGroup=wg)
qid = r['QueryExecutionId']
for _ in range(30):
    time.sleep(2)
    s = athena.get_query_execution(QueryExecutionId=qid)['QueryExecution']['Status']
    if s['State'] == 'SUCCEEDED': break
    if s['State'] in ('FAILED','CANCELLED'):
        print(f'  FAILED: {s.get("StateChangeReason","")}')
        exit()
results = athena.get_query_results(QueryExecutionId=qid)
for row in results['ResultSet']['Rows'][1:]:
    print(f'  {row["Data"][0].get("VarCharValue","")}')

#!/usr/bin/env python3
"""Check if databases are visible via datazone_usr_role."""
import boto3
dz = boto3.client('datazone', region_name='us-east-2')
conns = dz.list_connections(domainIdentifier='dzd-4h7jbz76qckoh5', projectIdentifier='6m4v463kntafxl', type='ATHENA')
conn = dz.get_connection(domainIdentifier='dzd-4h7jbz76qckoh5', identifier=conns['items'][0]['connectionId'], withSecret=True)
creds = conn['connectionCredentials']
glue = boto3.client('glue', region_name='us-east-2', aws_access_key_id=creds['accessKeyId'], aws_secret_access_key=creds['secretAccessKey'], aws_session_token=creds['sessionToken'])
dbs = glue.get_databases()
for db in dbs['DatabaseList']:
    t = db.get('TargetDatabase',{})
    if t:
        print(f'{db["Name"]} -> {t["CatalogId"]}/{t["DatabaseName"]}')
    else:
        print(db['Name'])

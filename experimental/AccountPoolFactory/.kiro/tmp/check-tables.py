#!/usr/bin/env python3
import boto3
glue = boto3.client('glue', region_name='us-east-2')
for db in ['apf_test_customers', 'apf_test_transactions']:
    tables = glue.get_tables(DatabaseName=db)['TableList']
    print(f'{db}: {len(tables)} tables')
    for t in tables:
        print(f'  {t["Name"]}: location={t["StorageDescriptor"]["Location"]}')

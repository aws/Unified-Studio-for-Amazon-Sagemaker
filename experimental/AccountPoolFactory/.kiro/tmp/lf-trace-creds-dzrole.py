#!/usr/bin/env python3
"""Output shell export commands for DZ user role via DataZone connection credentials."""
import boto3
dz = boto3.client('datazone', region_name='us-east-2')
conns = dz.list_connections(
    domainIdentifier='dzd-4h7jbz76qckoh5',
    projectIdentifier='5237hturzpp5ih',
    type='ATHENA')
conn = dz.get_connection(
    domainIdentifier='dzd-4h7jbz76qckoh5',
    identifier=conns['items'][0]['connectionId'],
    withSecret=True)
c = conn['connectionCredentials']
print(f"export AWS_ACCESS_KEY_ID={c['accessKeyId']}")
print(f"export AWS_SECRET_ACCESS_KEY={c['secretAccessKey']}")
print(f"export AWS_SESSION_TOKEN={c['sessionToken']}")

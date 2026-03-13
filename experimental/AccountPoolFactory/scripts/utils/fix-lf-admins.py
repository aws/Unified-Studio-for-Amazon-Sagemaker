#!/usr/bin/env python3
"""Check and fix LakeFormation admins in all AVAILABLE accounts."""
import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed

REGION = 'us-east-2'
DOMAIN_ID = 'dzd-4h7jbz76qckoh5'
sts = boto3.client('sts', region_name=REGION)

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table = dynamodb.Table('AccountPoolFactory-AccountState')

response = table.scan()
items = response['Items']
while 'LastEvaluatedKey' in response:
    response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
    items.extend(response['Items'])

latest = {}
for item in items:
    aid = item['accountId']
    ts = item.get('timestamp', '')
    if aid not in latest or ts > latest[aid].get('timestamp', ''):
        latest[aid] = item

available = [aid for aid, item in latest.items()
             if item.get('state') == 'AVAILABLE' and item.get('deployedStackSets')]

def check_and_fix(acct):
    try:
        creds = sts.assume_role(
            RoleArn=f'arn:aws:iam::{acct}:role/SMUS-AccountPoolFactory-DomainAccess',
            RoleSessionName='fix-lf', ExternalId=DOMAIN_ID, DurationSeconds=900
        )['Credentials']
        lf = boto3.client('lakeformation', region_name=REGION,
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken'])
        settings = lf.get_data_lake_settings()
        admins = settings.get('DataLakeSettings', {}).get('DataLakeAdmins', [])
        if admins:
            lf.put_data_lake_settings(DataLakeSettings={
                'DataLakeAdmins': [],
                'CreateDatabaseDefaultPermissions': [],
                'CreateTableDefaultPermissions': [],
            })
            return acct, 'FIXED'
        return acct, 'OK'
    except Exception as e:
        return acct, f'ERROR: {e}'

print(f"Checking {len(available)} AVAILABLE accounts...")
fixed = 0
errors = 0
with ThreadPoolExecutor(max_workers=10) as ex:
    futures = {ex.submit(check_and_fix, a): a for a in available}
    for f in as_completed(futures):
        acct, result = f.result()
        if result == 'FIXED':
            fixed += 1
            print(f"  {acct}: FIXED (had stale LF admins)")
        elif result != 'OK':
            errors += 1
            print(f"  {acct}: {result}")

print(f"\nDone: {fixed} fixed, {errors} errors, {len(available)-fixed-errors} already clean")

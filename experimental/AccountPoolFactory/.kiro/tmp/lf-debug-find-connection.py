#!/usr/bin/env python3
"""Find the Athena connection for project 5237hturzpp5ih by listing environments."""
import boto3, json

REGION = "us-east-2"
DOMAIN_ID = "dzd-4h7jbz76qckoh5"
PROJECT_ID = "5237hturzpp5ih"
PROJECT_ACCOUNT = "261399254793"

dz = boto3.client('datazone', region_name=REGION)

print(">>> Listing environments for project...")
try:
    envs = dz.list_environments(
        domainIdentifier=DOMAIN_ID,
        projectIdentifier=PROJECT_ID)
    for env in envs.get('items', []):
        print(json.dumps({
            'id': env.get('id'),
            'name': env.get('name'),
            'status': env.get('status'),
            'provider': env.get('environmentProfileId'),
            'accountId': env.get('awsAccountId'),
        }, indent=2))
except Exception as e:
    print(f"  Error: {e}")

print()
print(">>> Getting project details...")
try:
    proj = dz.get_project(domainIdentifier=DOMAIN_ID, identifier=PROJECT_ID)
    print(json.dumps({
        'id': proj.get('id'),
        'name': proj.get('name'),
        'status': proj.get('status'),
    }, indent=2))
except Exception as e:
    print(f"  Error: {e}")

print()
print(">>> Trying to assume DZ user role directly...")
sts = boto3.client('sts', region_name=REGION)
dz_role = f"arn:aws:iam::{PROJECT_ACCOUNT}:role/datazone_usr_role_{PROJECT_ID}_b2no4uzn8mttt5"
try:
    # Try via DomainAccess role first
    r = sts.assume_role(
        RoleArn=f'arn:aws:iam::{PROJECT_ACCOUNT}:role/SMUS-AccountPoolFactory-DomainAccess',
        RoleSessionName='find-conn',
        ExternalId=DOMAIN_ID)
    c = r['Credentials']
    sts2 = boto3.client('sts', region_name=REGION,
        aws_access_key_id=c['AccessKeyId'],
        aws_secret_access_key=c['SecretAccessKey'],
        aws_session_token=c['SessionToken'])
    # Now assume the DZ user role from within the project account
    r2 = sts2.assume_role(
        RoleArn=dz_role,
        RoleSessionName='test-visibility')
    c2 = r2['Credentials']
    
    glue = boto3.client('glue', region_name=REGION,
        aws_access_key_id=c2['AccessKeyId'],
        aws_secret_access_key=c2['SecretAccessKey'],
        aws_session_token=c2['SessionToken'])
    
    who = boto3.client('sts', region_name=REGION,
        aws_access_key_id=c2['AccessKeyId'],
        aws_secret_access_key=c2['SecretAccessKey'],
        aws_session_token=c2['SessionToken'])
    print(f"  Identity: {who.get_caller_identity()['Arn']}")
    
    print("  Glue databases visible:")
    dbs = glue.get_databases()
    for db in dbs['DatabaseList']:
        t = db.get('TargetDatabase', {})
        if t:
            print(f"    {db['Name']} -> {t.get('CatalogId','')}/{t.get('DatabaseName','')}")
        else:
            print(f"    {db['Name']}")
    
    for db_name in ['apf_test_customers', 'apf_test_transactions']:
        found = any(d['Name'] == db_name for d in dbs['DatabaseList'])
        status = "VISIBLE" if found else "NOT visible"
        print(f"  {db_name}: {status}")
        
except Exception as e:
    print(f"  Error: {e}")

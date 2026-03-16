#!/usr/bin/env python3
import boto3
sts = boto3.client('sts', region_name='us-east-2')
r = sts.assume_role(RoleArn='arn:aws:iam::242736648013:role/SMUS-AccountPoolFactory-DomainAccess', RoleSessionName='fix', ExternalId='dzd-4h7jbz76qckoh5')
c = r['Credentials']
lf = boto3.client('lakeformation', region_name='us-east-2', aws_access_key_id=c['AccessKeyId'], aws_secret_access_key=c['SecretAccessKey'], aws_session_token=c['SessionToken'])
for db in ['apf_test_customers', 'apf_test_transactions']:
    lf.grant_permissions(Principal={'DataLakePrincipalIdentifier': 'IAM_ALLOWED_PRINCIPALS'}, Resource={'Database': {'Name': db}}, Permissions=['ALL'])
    print(f'Granted ALL on {db}')
print('Done')

#!/bin/bash
eval $(isengardcli credentials amirbo+3@amazon.com)
ACCOUNT_ID="${1:?Usage: $0 ACCOUNT_ID}"
python3 -c "
import boto3
lf = boto3.client('lakeformation', region_name='us-east-2')
acct = '$ACCOUNT_ID'
for db in ['apf_test_customers', 'apf_test_transactions']:
    try:
        lf.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': acct},
            Resource={'Database': {'Name': db}},
            Permissions=['DESCRIBE'],
            PermissionsWithGrantOption=['DESCRIBE'])
        print(f'  Granted DESCRIBE on {db}')
    except Exception as e:
        print(f'  DB {db}: {e}')
    try:
        lf.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': acct},
            Resource={'Table': {'DatabaseName': db, 'TableWildcard': {}}},
            Permissions=['SELECT', 'DESCRIBE'],
            PermissionsWithGrantOption=['SELECT', 'DESCRIBE'])
        print(f'  Granted SELECT+DESCRIBE on tables in {db}')
    except Exception as e:
        print(f'  Tables {db}: {e}')
print('Done')
"

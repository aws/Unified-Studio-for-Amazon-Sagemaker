import boto3

region = 'us-east-2'
lf = boto3.client('lakeformation', region_name=region)
sts = boto3.client('sts')
iam = boto3.client('iam')

account_id = sts.get_caller_identity()['Account']
print(f"Account: {account_id}")

role_names = ['Admin']

databases = ['covid19_db', 'covid19_summary_db']
tables = [
    ('covid19_db', 'us_simplified'),
    ('covid19_summary_db', 'us_state_summary')
]

for role_name in role_names:
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
    print(f"\nGranting to {role_arn}")
    
    for db in databases:
        lf.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': role_arn},
            Resource={'Database': {'Name': db}},
            Permissions=['DESCRIBE']
        )
        print(f"  ✓ Database {db}")
    
    for db, table in tables:
        lf.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': role_arn},
            Resource={'Table': {'DatabaseName': db, 'Name': table}},
            Permissions=['DESCRIBE']
        )
        lf.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': role_arn},
            Resource={'TableWithColumns': {'DatabaseName': db, 'Name': table, 'ColumnWildcard': {}}},
            Permissions=['SELECT']
        )
        print(f"  ✓ Table {db}.{table}")

print("\n✓ All permissions granted")

import sys
import boto3
import time
from awsglue.utils import getResolvedOptions

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'BUCKET_NAME', 'REGION_NAME', 'ROLES'])

lf = boto3.client('lakeformation', region_name=args['REGION_NAME'])
athena = boto3.client('athena', region_name=args['REGION_NAME'])
sts = boto3.client('sts')

account_id = sts.get_caller_identity()['Account']
role_names = args['ROLES'].split(',')
roles = [f"arn:aws:iam::{account_id}:role/{name}" for name in role_names]

databases = ['covid19_db', 'covid19_summary_db']
tables = [
    ('covid19_db', 'us_simplified'),
    ('covid19_summary_db', 'us_state_summary')
]

print("Granting Lake Formation permissions...")
for role_arn in roles:
    for db in databases:
        lf.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': role_arn},
            Resource={'Database': {'Name': db}},
            Permissions=['DESCRIBE']
        )
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
    print(f"✓ Granted permissions to {role_arn}")

print("Validating data with Athena...")
s3_output = f"s3://{args['BUCKET_NAME']}/athena-results/" if args['REGION_NAME'] == 'us-east-1' else f"s3://sagemaker-{args['REGION_NAME']}-{account_id}/athena-results/"
query_id = athena.start_query_execution(
    QueryString='SELECT COUNT(*) FROM covid19_db.us_simplified',
    ResultConfiguration={'OutputLocation': s3_output}
)['QueryExecutionId']

for _ in range(30):
    time.sleep(2)
    status = athena.get_query_execution(QueryExecutionId=query_id)
    state = status['QueryExecution']['Status']['State']
    if state == 'SUCCEEDED':
        result = athena.get_query_results(QueryExecutionId=query_id)
        count = result['ResultSet']['Rows'][1]['Data'][0]['VarCharValue']
        print(f"✓ Table validated: {count} rows")
        break
    elif state in ['FAILED', 'CANCELLED']:
        raise Exception(f"Query {state}")

print("✓ Permission check completed")

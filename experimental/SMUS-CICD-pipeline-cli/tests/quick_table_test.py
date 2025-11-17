#!/usr/bin/env python3
# TODO: Replace {account_id} placeholders with test_config.get_account_id()
"""Quick test to validate covid19_db.us_simplified table."""
import boto3
import time

region = 'us-east-2'

# Grant Lake Formation permissions
sts = boto3.client('sts', region_name=region)
caller = sts.get_caller_identity()
arn = caller['Arn']

# Convert assumed-role ARN to IAM role ARN
if ':assumed-role/' in arn:
    parts = arn.split(':assumed-role/')
    role_name = parts[1].split('/')[0]
    role_arn = f"{parts[0]}:role/{role_name}".replace(':sts:', ':iam:')
else:
    role_arn = arn.replace(':sts:', ':iam:')

lf = boto3.client('lakeformation', region_name=region)

print(f"Granting permissions to: {role_arn}")

# Database permissions
try:
    lf.grant_permissions(
        Principal={'DataLakePrincipalIdentifier': role_arn},
        Resource={'Database': {'Name': 'covid19_db'}},
        Permissions=['DESCRIBE']
    )
    print("✅ Database permissions granted")
except Exception as e:
    print(f"⚠️ Database permissions: {e}")

# Table permissions
try:
    lf.grant_permissions(
        Principal={'DataLakePrincipalIdentifier': role_arn},
        Resource={'Table': {'DatabaseName': 'covid19_db', 'Name': 'us_simplified'}},
        Permissions=['DESCRIBE']
    )
    print("✅ Table DESCRIBE granted")
except Exception as e:
    print(f"⚠️ Table permissions: {e}")

# Column permissions
try:
    lf.grant_permissions(
        Principal={'DataLakePrincipalIdentifier': role_arn},
        Resource={'TableWithColumns': {
            'DatabaseName': 'covid19_db',
            'Name': 'us_simplified',
            'ColumnWildcard': {}
        }},
        Permissions=['SELECT']
    )
    print("✅ Column SELECT granted")
except Exception as e:
    print(f"⚠️ Column permissions: {e}")

# Test queries
athena = boto3.client('athena', region_name=region)
output_location = 's3://amazon-sagemaker-{account_id}-us-east-2-5330xnk7amt221/athena-results/'

# Query 1: Row count
print("\n📊 Testing row count...")
query_id = athena.start_query_execution(
    QueryString='SELECT COUNT(*) as row_count FROM covid19_db.us_simplified',
    ResultConfiguration={'OutputLocation': output_location}
)['QueryExecutionId']

time.sleep(5)
result = athena.get_query_results(QueryExecutionId=query_id)
row_count = int(result['ResultSet']['Rows'][1]['Data'][0]['VarCharValue'])
print(f"✅ Row count: {row_count:,}")
assert row_count > 1000000, f"Expected >1M rows, got {row_count:,}"

# Query 2: First 10 records
print("\n📋 Testing first 10 records...")
query_id = athena.start_query_execution(
    QueryString='SELECT * FROM covid19_db.us_simplified LIMIT 10',
    ResultConfiguration={'OutputLocation': output_location}
)['QueryExecutionId']

for _ in range(10):
    time.sleep(3)
    status = athena.get_query_execution(QueryExecutionId=query_id)
    state = status['QueryExecution']['Status']['State']
    if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
        break

if state != 'SUCCEEDED':
    error_msg = status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
    print(f"❌ Query failed: {error_msg}")
    exit(1)

result = athena.get_query_results(QueryExecutionId=query_id)
rows = result['ResultSet']['Rows']

# Validate
assert len(rows) >= 2, f"Expected at least 2 rows, got {len(rows)}"

first_data_row = rows[1]['Data']
date_value = first_data_row[0].get('VarCharValue', '')

print(f"First record date: {date_value}")

# Check for Python code
assert not date_value.startswith('import '), f"Table has Python code: {date_value}"
assert not date_value.startswith('def '), f"Table has Python code: {date_value}"

# Check date format
import re
assert re.match(r'\d{4}-\d{2}-\d{2}', date_value), f"Invalid date: {date_value}"

print(f"✅ First record date: {date_value}")
print("✅ All validations passed!")

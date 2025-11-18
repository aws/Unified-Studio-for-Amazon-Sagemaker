import os
import boto3

region = os.environ.get('AWS_REGION', 'us-east-2')
# Get account ID from STS
sts = boto3.client('sts')
account_id = sts.get_caller_identity()['Account']

qs = boto3.client('quicksight', region_name=region)

# Delete dashboards starting with "deployed-test"
dashboards = qs.list_dashboards(AwsAccountId=account_id)['DashboardSummaryList']
for dash in dashboards:
    if dash['DashboardId'].startswith('deployed-test'):
        try:
            qs.delete_dashboard(AwsAccountId=account_id, DashboardId=dash['DashboardId'])
            print(f"✓ Deleted dashboard: {dash['DashboardId']}")
        except Exception as e:
            print(f"✗ Error deleting dashboard {dash['DashboardId']}: {e}")

# Delete datasets starting with "deployed-test"
datasets = qs.list_data_sets(AwsAccountId=account_id)['DataSetSummaries']
for ds in datasets:
    if ds['DataSetId'].startswith('deployed-test'):
        try:
            qs.delete_data_set(AwsAccountId=account_id, DataSetId=ds['DataSetId'])
            print(f"✓ Deleted dataset: {ds['DataSetId']}")
        except Exception as e:
            print(f"✗ Error deleting dataset {ds['DataSetId']}: {e}")

# Delete data sources starting with "deployed-test"
sources = qs.list_data_sources(AwsAccountId=account_id)['DataSources']
for src in sources:
    if src['DataSourceId'].startswith('deployed-test'):
        try:
            qs.delete_data_source(AwsAccountId=account_id, DataSourceId=src['DataSourceId'])
            print(f"✓ Deleted data source: {src['DataSourceId']}")
        except Exception as e:
            print(f"✗ Error deleting data source {src['DataSourceId']}: {e}")

print("✓ Cleanup complete")

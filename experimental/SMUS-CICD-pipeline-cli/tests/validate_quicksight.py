#!/usr/bin/env python3
"""Quick validation script for QuickSight deployed resources."""

import boto3
import json

REGION = "us-east-2"
PREFIX = "deployed-test-covid"

def main():
    qs = boto3.client("quicksight", region_name=REGION)
    sts = boto3.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    
    print(f"AWS Account: {account_id}")
    print(f"Region: {REGION}")
    print(f"Looking for resources with prefix: {PREFIX}")
    print("=" * 80)
    
    # List dashboards
    print("\n📊 DASHBOARDS:")
    dashboards = qs.list_dashboards(AwsAccountId=account_id)
    deployed = [d for d in dashboards["DashboardSummaryList"] if PREFIX in d["DashboardId"]]
    
    if not deployed:
        print(f"  ❌ No dashboards found with prefix '{PREFIX}'")
    else:
        for dash in deployed:
            print(f"\n  Dashboard ID: {dash['DashboardId']}")
            print(f"  Name: {dash['Name']}")
            print(f"  Version: {dash.get('PublishedVersionNumber', 'N/A')}")
            
            # Get permissions
            perms = qs.describe_dashboard_permissions(
                AwsAccountId=account_id,
                DashboardId=dash["DashboardId"]
            )
            print(f"  Permissions: {len(perms['Permissions'])} principals")
            for perm in perms["Permissions"]:
                principal = perm["Principal"].split("/")[-1]
                print(f"    - {principal}: {len(perm['Actions'])} actions")
    
    # List datasets
    print("\n📁 DATASETS:")
    datasets = qs.list_data_sets(AwsAccountId=account_id)
    deployed_ds = [d for d in datasets["DataSetSummaries"] if PREFIX in d["DataSetId"]]
    
    if not deployed_ds:
        print(f"  ❌ No datasets found with prefix '{PREFIX}'")
    else:
        for ds in deployed_ds:
            print(f"  - {ds['DataSetId']}: {ds['Name']}")
    
    # List data sources
    print("\n🔌 DATA SOURCES:")
    sources = qs.list_data_sources(AwsAccountId=account_id)
    deployed_src = [s for s in sources["DataSources"] if PREFIX in s["DataSourceId"]]
    
    if not deployed_src:
        print(f"  ❌ No data sources found with prefix '{PREFIX}'")
    else:
        for src in deployed_src:
            print(f"  - {src['DataSourceId']}: {src['Name']} ({src['Type']})")
    
    print("\n" + "=" * 80)
    print(f"Summary: {len(deployed)} dashboards, {len(deployed_ds)} datasets, {len(deployed_src)} data sources")

if __name__ == "__main__":
    main()

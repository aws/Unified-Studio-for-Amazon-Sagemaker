#!/usr/bin/env python3
"""
Athena connectivity test for SMUS CI/CD pipeline validation.
Tests that the deployed project can connect to Athena and list databases/tables.
"""

import os
import boto3
import pytest
from botocore.exceptions import ClientError, NoCredentialsError


def test_environment_variables():
    """Test that required environment variables are set."""
    required_vars = ["SMUS_REGION", "SMUS_PROJECT_NAME", "SMUS_TARGET_NAME"]

    print("\n🔧 Environment Variables:")
    for var in required_vars:
        value = os.environ.get(var)
        print(f"  {var}: {value}")
        assert value, f"Environment variable {var} is not set"

    print("✅ All required environment variables are set\n")


def test_athena_connectivity():
    """Test Athena connectivity and list databases/tables."""
    region = os.environ.get("SMUS_REGION", "us-east-1")

    print(f"\n🔍 Testing Athena connectivity in region: {region}")

    # Create Athena client
    athena_client = boto3.client("athena", region_name=region)

    # Test 1: List data catalogs
    print("\n📊 Listing data catalogs...")
    catalogs = athena_client.list_data_catalogs()

    assert catalogs["DataCatalogsSummary"], "No data catalogs found"
    print(f"✅ Found {len(catalogs['DataCatalogsSummary'])} data catalogs:")

    for i, catalog in enumerate(catalogs["DataCatalogsSummary"][:5]):  # Show first 5
        print(f"  {i+1}. {catalog['CatalogName']} ({catalog['Type']})")

    # Test 2: List databases in default catalog
    print(f"\n📚 Listing databases in AwsDataCatalog...")
    databases = athena_client.list_databases(CatalogName="AwsDataCatalog")

    assert databases["DatabaseList"], "No databases found"
    print(f"✅ Found {len(databases['DatabaseList'])} databases:")

    for i, db in enumerate(databases["DatabaseList"][:10]):  # Show first 10
        print(f"  {i+1}. {db['Name']}")

        # Test 3: Try to list tables in first few databases
        if i < 3 and db["Name"]:  # Only check first 3 databases
            try:
                tables = athena_client.list_table_metadata(
                    CatalogName="AwsDataCatalog", DatabaseName=db["Name"]
                )
                table_count = len(tables["TableMetadataList"])
                print(f"     📋 {table_count} tables")

                # Show first few tables
                for j, table in enumerate(tables["TableMetadataList"][:5]):
                    print(f"       {j+1}. {table['Name']}")

            except ClientError as e:
                print(f"     ⚠️ Could not list tables: {e.response['Error']['Code']}")

    print("\n✅ Athena connectivity test completed successfully!")


if __name__ == "__main__":
    # Run tests directly if called as script
    test_environment_variables()
    test_athena_connectivity()
    print("🎉 All tests passed!")

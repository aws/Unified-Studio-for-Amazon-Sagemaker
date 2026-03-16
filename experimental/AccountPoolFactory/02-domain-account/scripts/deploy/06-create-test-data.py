#!/usr/bin/env python3
"""
Phase 1: Create Glue/Lake Formation test data in the domain account (994753223772).

This script provisions sample Glue databases and tables with minimal test data,
registers them in Lake Formation, and configures LF-only access control so that
cross-account sharing works via StackSet 07.

Run in domain account:
    eval $(isengardcli credentials amirbo+3@amazon.com)
    ./02-domain-account/scripts/deploy/06-create-test-data.py

Steps performed (in order):
    1. Add caller as Lake Formation data lake admin
    2. Create S3 bucket and upload sample CSV data
    3. Create Glue databases (apf_test_customers, apf_test_transactions)
    4. Revoke IAM_ALLOWED_PRINCIPALS from databases
    5. Create Glue tables (customers, transactions)
    6. Register S3 location with Lake Formation and grant permissions

Idempotent — safe to re-run.
"""

import sys
import os
import json
import boto3
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REGION = "us-east-2"
BUCKET_PREFIX = "apf-test-data"

# Test databases to create
DATABASES = {
    "apf_test_customers": "Sample customer data for testing Lake Formation sharing",
    "apf_test_transactions": "Sample transaction data for testing Lake Formation sharing",
}

# Table definitions
TABLES = {
    "apf_test_customers": {
        "customers": {
            "columns": [
                {"Name": "customer_id", "Type": "string"},
                {"Name": "name", "Type": "string"},
                {"Name": "email", "Type": "string"},
                {"Name": "city", "Type": "string"},
                {"Name": "signup_date", "Type": "string"},
            ],
            "input_format": "org.apache.hadoop.mapred.TextInputFormat",
            "output_format": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
            "serde": "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe",
            "serde_params": {"field.delim": ",", "skip.header.line.count": "1"},
        }
    },
    "apf_test_transactions": {
        "transactions": {
            "columns": [
                {"Name": "transaction_id", "Type": "string"},
                {"Name": "customer_id", "Type": "string"},
                {"Name": "amount", "Type": "double"},
                {"Name": "currency", "Type": "string"},
                {"Name": "transaction_date", "Type": "string"},
            ],
            "input_format": "org.apache.hadoop.mapred.TextInputFormat",
            "output_format": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
            "serde": "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe",
            "serde_params": {"field.delim": ",", "skip.header.line.count": "1"},
        }
    },
}

# Output emoji constants
PASS = "✅"
FAIL = "❌"
INFO = "ℹ️ "


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def setup_lf_admin(lf_client, sts_client):
    """Add the caller's IAM role as a Lake Formation data lake administrator.

    Must be called BEFORE creating databases so LF-only access control works.
    Additive — preserves existing data lake administrators.

    Returns the caller's IAM role ARN.
    """
    try:
        # 1. Get the caller's identity
        identity = sts_client.get_caller_identity()
        caller_arn = identity["Arn"]

        # 2. Convert assumed-role ARN to IAM role ARN
        #    arn:aws:sts::ACCOUNT:assumed-role/ROLE_NAME/SESSION
        #    → arn:aws:iam::ACCOUNT:role/ROLE_NAME
        arn_parts = caller_arn.split(":")
        account_id = arn_parts[4]
        resource = arn_parts[5]  # e.g. "assumed-role/ROLE_NAME/SESSION"

        if resource.startswith("assumed-role/"):
            role_name = resource.split("/")[1]
            role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
        else:
            # Already an IAM role or user ARN — use as-is
            role_arn = caller_arn

        print(f"  Caller role ARN: {role_arn}")

        # 3. Get current data lake settings
        settings = lf_client.get_data_lake_settings()
        dl_settings = settings.get("DataLakeSettings", {})
        current_admins = dl_settings.get("DataLakeAdmins", [])

        # 4. Check if role is already an admin
        existing_arns = [a.get("DataLakePrincipalIdentifier", "") for a in current_admins]
        if role_arn in existing_arns:
            print(f"  {INFO} Role is already a Lake Formation admin, skipping")
            return role_arn

        # 5. Add the role to the existing admins list (preserving existing)
        #    Filter out stale/invalid principals that would cause PutDataLakeSettings to fail
        iam = boto3.client("iam", region_name=REGION)
        valid_admins = []
        for admin in current_admins:
            arn = admin.get("DataLakePrincipalIdentifier", "")
            if ":role/" in arn:
                role_name_part = arn.split(":role/")[-1]
                try:
                    iam.get_role(RoleName=role_name_part)
                    valid_admins.append(admin)
                except ClientError:
                    print(f"  {INFO} Removing stale admin: {arn}")
            else:
                valid_admins.append(admin)

        valid_admins.append({"DataLakePrincipalIdentifier": role_arn})
        dl_settings["DataLakeAdmins"] = valid_admins

        # 6. Put updated settings
        lf_client.put_data_lake_settings(DataLakeSettings=dl_settings)
        print(f"  {PASS} Added role as Lake Formation admin")

        return role_arn

    except ClientError as e:
        print(f"  {FAIL} Error setting up LF admin: {e}")
        raise
    except Exception as e:
        print(f"  {FAIL} Unexpected error in setup_lf_admin: {e}")
        raise

def create_s3_bucket_and_data(s3_client, bucket_name, region):
    """Create S3 bucket and upload sample CSV data files.

    Creates the bucket with LocationConstraint for the given region and uploads
    two CSV files: customers/customers.csv and transactions/transactions.csv
    with 3-5 sample rows each.

    Idempotent — handles AlreadyOwnedByYou/BucketAlreadyOwnedByYou gracefully.

    Returns the bucket name.
    """
    # 1. Create S3 bucket (with LocationConstraint for non-us-east-1 regions)
    try:
        s3_client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={"LocationConstraint": region},
        )
        print(f"  {PASS} Created S3 bucket: {bucket_name}")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            print(f"  {INFO} Bucket {bucket_name} already exists, skipping creation")
        else:
            print(f"  {FAIL} Error creating bucket: {e}")
            raise

    # 2. Upload customers/customers.csv
    customers_csv = (
        "customer_id,name,email,city,signup_date\n"
        "C001,Alice Johnson,alice@example.com,Seattle,2024-01-15\n"
        "C002,Bob Smith,bob@example.com,Portland,2024-02-20\n"
        "C003,Carol White,carol@example.com,Denver,2024-03-10\n"
    )
    s3_client.put_object(
        Bucket=bucket_name,
        Key="customers/customers.csv",
        Body=customers_csv.encode("utf-8"),
    )
    print(f"  {PASS} Uploaded customers/customers.csv (3 rows)")

    # 3. Upload transactions/transactions.csv
    transactions_csv = (
        "transaction_id,customer_id,amount,currency,transaction_date\n"
        "T001,C001,150.00,USD,2024-06-01\n"
        "T002,C002,89.50,USD,2024-06-02\n"
        "T003,C001,220.75,USD,2024-06-03\n"
    )
    s3_client.put_object(
        Bucket=bucket_name,
        Key="transactions/transactions.csv",
        Body=transactions_csv.encode("utf-8"),
    )
    print(f"  {PASS} Uploaded transactions/transactions.csv (3 rows)")

    return bucket_name



def create_glue_databases(glue_client, databases):
    """Create Glue databases. Idempotent — skips if already exists.

    Args:
        glue_client: boto3 Glue client in the domain account.
        databases: dict of {db_name: description}.

    Returns:
        List of database names.
    """
    created = []
    for db_name, description in databases.items():
        try:
            glue_client.create_database(
                DatabaseInput={
                    "Name": db_name,
                    "Description": description,
                }
            )
            print(f"  {PASS} Created database: {db_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "AlreadyExistsException":
                print(f"  {INFO} Database {db_name} already exists, skipping")
            else:
                print(f"  {FAIL} Error creating database {db_name}: {e}")
                raise
        created.append(db_name)
    return created


def revoke_iam_allowed_principals(lf_client, databases):
    """Remove IAM_ALLOWED_PRINCIPALS from all databases.

    By default, Glue databases have IAM_ALLOWED_PRINCIPALS which bypasses
    Lake Formation permissions entirely. This must be revoked so LF-only
    access control works for cross-account sharing.

    Idempotent — safe to re-run if already revoked.

    Args:
        lf_client: boto3 Lake Formation client in the domain account.
        databases: dict of {db_name: description}.
    """
    for db_name in databases:
        try:
            lf_client.batch_revoke_permissions(
                Entries=[
                    {
                        "Id": f"revoke-iap-{db_name}",
                        "Principal": {
                            "DataLakePrincipalIdentifier": "IAM_ALLOWED_PRINCIPALS"
                        },
                        "Resource": {
                            "Database": {"Name": db_name}
                        },
                        "Permissions": ["ALL"],
                        "PermissionsWithGrantOption": ["ALL"],
                    }
                ]
            )
            print(f"  {PASS} Revoked IAM_ALLOWED_PRINCIPALS from {db_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "InvalidInputException":
                print(f"  {INFO} IAM_ALLOWED_PRINCIPALS already revoked from {db_name}, skipping")
            else:
                print(f"  {FAIL} Error revoking IAM_ALLOWED_PRINCIPALS from {db_name}: {e}")
                raise


def create_glue_tables(glue_client, tables, bucket_name):
    """Create Glue tables pointing to S3 CSV data. Idempotent.

    Args:
        glue_client: boto3 Glue client in the domain account.
        tables: dict mapping {db_name: {table_name: table_def}}.
        bucket_name: S3 bucket name containing the data.

    Returns:
        List of (db_name, table_name) tuples.
    """
    created = []
    for db_name, db_tables in tables.items():
        for table_name, table_def in db_tables.items():
            try:
                glue_client.create_table(
                    DatabaseName=db_name,
                    TableInput={
                        "Name": table_name,
                        "StorageDescriptor": {
                            "Columns": table_def["columns"],
                            "Location": f"s3://{bucket_name}/{table_name}/",
                            "InputFormat": table_def["input_format"],
                            "OutputFormat": table_def["output_format"],
                            "SerdeInfo": {
                                "SerializationLibrary": table_def["serde"],
                                "Parameters": table_def["serde_params"],
                            },
                        },
                    },
                )
                print(f"  {PASS} Created table: {db_name}.{table_name}")
            except ClientError as e:
                if e.response["Error"]["Code"] == "AlreadyExistsException":
                    print(f"  {INFO} Table {db_name}.{table_name} already exists, skipping")
                else:
                    print(f"  {FAIL} Error creating table {db_name}.{table_name}: {e}")
                    raise
            created.append((db_name, table_name))
    return created


def register_lakeformation(lf_client, bucket_name, account_id):
    """Register S3 location with Lake Formation and grant permissions.

    Registers the S3 bucket as a Lake Formation resource and grants the
    domain account ALL permissions on all databases and tables.

    Idempotent — handles AlreadyExistsException and InvalidInputException.

    Args:
        lf_client: boto3 Lake Formation client in the domain account.
        bucket_name: S3 bucket name to register.
        account_id: Domain account ID (for granting permissions).
    """
    # 1. Register S3 location with Lake Formation
    resource_arn = f"arn:aws:s3:::{bucket_name}"
    try:
        lf_client.register_resource(
            ResourceArn=resource_arn,
            RoleArn=f"arn:aws:iam::{account_id}:role/APF-LakeFormation-TestData"
        )
        print(f"  {PASS} Registered S3 location: {resource_arn}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "AlreadyExistsException":
            print(f"  {INFO} S3 location already registered, skipping")
        else:
            print(f"  {FAIL} Error registering S3 location: {e}")
            raise

    # 2. Grant domain account ALL permissions on each database
    account_principal = f"arn:aws:iam::{account_id}:root"
    for db_name in DATABASES:
        try:
            lf_client.grant_permissions(
                Principal={"DataLakePrincipalIdentifier": account_principal},
                Resource={"Database": {"Name": db_name}},
                Permissions=["ALL"],
                PermissionsWithGrantOption=["ALL"],
            )
            print(f"  {PASS} Granted ALL on database {db_name} to account {account_id}")
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in ("AlreadyExistsException", "InvalidInputException"):
                print(f"  {INFO} Permissions on database {db_name} already granted, skipping")
            else:
                print(f"  {FAIL} Error granting database permissions on {db_name}: {e}")
                raise

    # 3. Grant domain account ALL permissions on all tables in each database
    for db_name in DATABASES:
        try:
            lf_client.grant_permissions(
                Principal={"DataLakePrincipalIdentifier": account_principal},
                Resource={
                    "Table": {
                        "DatabaseName": db_name,
                        "TableWildcard": {},
                    }
                },
                Permissions=["ALL"],
                PermissionsWithGrantOption=["ALL"],
            )
            print(f"  {PASS} Granted ALL on all tables in {db_name} to account {account_id}")
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in ("AlreadyExistsException", "InvalidInputException"):
                print(f"  {INFO} Permissions on tables in {db_name} already granted, skipping")
            else:
                print(f"  {FAIL} Error granting table permissions on {db_name}: {e}")
                raise


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Main entry point — run in domain account."""
    print("=" * 60)
    print("Phase 1: Create Glue/Lake Formation test data")
    print("=" * 60)

    # Get account ID from STS
    sts = boto3.client("sts", region_name=REGION)
    account_id = sts.get_caller_identity()["Account"]
    bucket_name = f"{BUCKET_PREFIX}-{account_id}"

    # Create boto3 clients
    s3 = boto3.client("s3", region_name=REGION)
    glue = boto3.client("glue", region_name=REGION)
    lf = boto3.client("lakeformation", region_name=REGION)

    # Step 1: Add caller as Lake Formation admin
    print("\nStep 1: Setting up Lake Formation admin role...")
    setup_lf_admin(lf, sts)

    # Step 2: Create S3 bucket and upload sample data
    print("\nStep 2: Creating S3 bucket and uploading sample data...")
    create_s3_bucket_and_data(s3, bucket_name, REGION)

    # Step 3: Create Glue databases
    print("\nStep 3: Creating Glue databases...")
    db_names = create_glue_databases(glue, DATABASES)

    # Step 4: Revoke IAM_ALLOWED_PRINCIPALS from databases
    print("\nStep 4: Revoking IAM_ALLOWED_PRINCIPALS from databases...")
    revoke_iam_allowed_principals(lf, DATABASES)

    # Step 5: Create Glue tables
    print("\nStep 5: Creating Glue tables...")
    table_pairs = create_glue_tables(glue, TABLES, bucket_name)

    # Step 6: Register with Lake Formation and grant permissions
    print("\nStep 6: Registering with Lake Formation...")
    register_lakeformation(lf, bucket_name, account_id)

    # Summary
    print("\n" + "=" * 60)
    print(f"{PASS} Done! Test data infrastructure is ready.")
    print(f"  Bucket: s3://{bucket_name}")
    print(f"  Databases: {db_names}")
    print(f"  Tables: {table_pairs}")
    print("=" * 60)


if __name__ == "__main__":
    main()

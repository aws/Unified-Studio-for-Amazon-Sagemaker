#!/usr/bin/env python3
"""
Setup COVID-19 dataset in SageMaker Unified Studio domain.
Uses local COVID-19 data, uploads to S3, creates Glue tables, and tests with Athena.
"""

import argparse
import boto3
import pandas as pd
import time
from pathlib import Path


def get_domain_id_by_name(domain_name, region):
    """Get DataZone domain ID by name."""
    try:
        datazone = boto3.client("datazone", region_name=region)
        response = datazone.list_domains()

        for domain in response.get("items", []):
            if domain.get("name") == domain_name:
                return domain.get("id")

        print(f"❌ Domain '{domain_name}' not found")
        return None

    except Exception as e:
        print(f"❌ Error finding domain: {e}")
        return None


def create_datazone_project(domain_name, project_name, region):
    """Create DataZone project and return project details."""
    try:
        domain_id = get_domain_id_by_name(domain_name, region)
        if not domain_id:
            return None

        datazone = boto3.client("datazone", region_name=region)

        # Check if project already exists
        try:
            projects = datazone.list_projects(domainIdentifier=domain_id)
            for project in projects.get("items", []):
                if project.get("name") == project_name:
                    print(f"📋 Project '{project_name}' already exists")
                    return {"projectId": project.get("id"), "domainId": domain_id}
        except Exception:
            pass

        # Get available project profiles
        try:
            profiles_response = datazone.list_project_profiles(
                domainIdentifier=domain_id
            )
            profiles = profiles_response.get("items", [])

            if not profiles:
                print("❌ No project profiles available in domain")
                return None

            # Use the first available project profile
            project_profile_id = profiles[0].get("id")
            print(f"📋 Using project profile: {project_profile_id}")

        except Exception as e:
            print(f"❌ Error getting project profiles: {e}")
            return None

        # Create new project
        response = datazone.create_project(
            domainIdentifier=domain_id,
            name=project_name,
            description="COVID-19 data lake administration project",
            projectProfileId=project_profile_id,
        )

        project_id = response.get("id")
        print(f"✅ Created DataZone project: {project_name} ({project_id})")

        return {"projectId": project_id, "domainId": domain_id}

    except Exception as e:
        print(f"❌ Error creating project: {e}")
        return None


def get_idc_user_id(username, domain_id, region):
    """Get IDC user ID for a username."""
    try:
        # Get Identity Center instance from DataZone domain
        datazone = boto3.client("datazone", region_name=region)
        domain_response = datazone.get_domain(identifier=domain_id)

        sso_domain_details = domain_response.get("singleSignOn", {})
        idc_instance_arn = sso_domain_details.get("idcInstanceArn")

        if not idc_instance_arn:
            print(f"❌ No Identity Center instance found for domain")
            return None

        # Get Identity Store ID from instance ARN
        sso_admin = boto3.client("sso-admin", region_name=region)
        instances = sso_admin.list_instances()

        identity_store_id = None
        for instance in instances.get("Instances", []):
            if instance.get("InstanceArn") == idc_instance_arn:
                identity_store_id = instance.get("IdentityStoreId")
                break

        if not identity_store_id:
            print(f"❌ No Identity Store ID found")
            return None

        # Search for user by username
        identitystore = boto3.client("identitystore", region_name=region)
        response = identitystore.list_users(
            IdentityStoreId=identity_store_id,
            Filters=[{"AttributePath": "UserName", "AttributeValue": username}],
        )

        users = response.get("Users", [])
        if users:
            user_id = users[0].get("UserId")
            print(f"✅ Found IDC user ID for {username}: {user_id}")
            return user_id

        print(f"❌ User {username} not found in Identity Center")
        return None

    except Exception as e:
        print(f"❌ Error getting IDC user ID for {username}: {e}")
        return None


def add_project_member(domain_id, project_id, username, region):
    """Add user as project owner."""
    try:
        # Get IDC user ID
        user_id = get_idc_user_id(username, domain_id, region)
        if not user_id:
            return False

        datazone = boto3.client("datazone", region_name=region)

        # Add user as project member with OWNER designation
        response = datazone.create_project_membership(
            domainIdentifier=domain_id,
            projectIdentifier=project_id,
            member={"userIdentifier": user_id},
            designation="PROJECT_OWNER",
        )

        print(f"✅ Added {username} as project owner")
        return True

    except Exception as e:
        print(f"❌ Error adding project member {username}: {e}")
        return False
    """Get the IAM role ARN for the DataZone project."""
    try:
        datazone = boto3.client("datazone", region_name=region)

        # Get project details
        response = datazone.get_project(
            domainIdentifier=domain_id, identifier=project_id
        )

        # Look for project role in various possible locations
        project_details = response.get("project", {})

        # Try to find role ARN in project configuration
        # DataZone projects typically have associated service roles
        iam = boto3.client("iam", region_name=region)

        # Look for DataZone project roles by naming convention
        role_name_patterns = [
            f"DataZoneProjectRole-{project_id}",
            f"AmazonDataZoneProjectRole-{project_id}",
            f"DataZone-{domain_id}-{project_id}-ProjectRole",
        ]

        for role_pattern in role_name_patterns:
            try:
                role_response = iam.get_role(RoleName=role_pattern)
                role_arn = role_response["Role"]["Arn"]
                print(f"✅ Found project role: {role_arn}")
                return role_arn
            except iam.exceptions.NoSuchEntityException:
                continue

        # If no specific role found, create a generic project role ARN pattern
        account_id = boto3.client("sts").get_caller_identity()["Account"]
        role_arn = f"arn:aws:iam::{account_id}:role/DataZoneProjectRole-{project_id}"
        print(f"📋 Using inferred role ARN: {role_arn}")
        return role_arn

    except Exception as e:
        print(f"❌ Error getting project role: {e}")
        return None


def wait_for_project_ready(domain_id, project_id, region, max_wait=300):
    """Wait for DataZone project to be fully created with all environments."""
    import time

    datazone = boto3.client("datazone", region_name=region)
    start_time = time.time()

    print(f"⏳ Waiting for project to be fully ready...")

    while time.time() - start_time < max_wait:
        try:
            # Check project status
            project_response = datazone.get_project(
                domainIdentifier=domain_id, identifier=project_id
            )

            project_status = project_response.get("projectStatus", "UNKNOWN")
            deployment_details = project_response.get(
                "environmentDeploymentDetails", {}
            )
            overall_status = deployment_details.get(
                "overallDeploymentStatus", "UNKNOWN"
            )

            print(
                f"📋 Project status: {project_status}, Deployment status: {overall_status}"
            )

            if project_status == "ACTIVE" and overall_status == "SUCCESSFUL":
                # Check if tooling environment is ready
                envs_response = datazone.list_environments(
                    domainIdentifier=domain_id, projectIdentifier=project_id
                )

                tooling_env = None
                for env in envs_response.get("items", []):
                    if "tooling" in env.get("name", "").lower():
                        tooling_env = env
                        break

                if tooling_env:
                    env_status = tooling_env.get("status", "UNKNOWN")
                    print(f"📋 Tooling environment status: {env_status}")

                    if env_status == "ACTIVE":
                        # Check if environment has provisionedResources
                        env_detail = datazone.get_environment(
                            domainIdentifier=domain_id, identifier=tooling_env.get("id")
                        )

                        provisioned_resources = env_detail.get(
                            "provisionedResources", []
                        )
                        user_role_found = any(
                            resource.get("name") == "userRoleArn"
                            for resource in provisioned_resources
                        )

                        if user_role_found:
                            print(f"✅ Project fully ready with user role provisioned")
                            return True
                        else:
                            print(f"⏳ Waiting for user role to be provisioned...")
                    else:
                        print(f"⏳ Waiting for tooling environment to be active...")
                else:
                    print(f"⏳ Waiting for tooling environment to be created...")
            else:
                print(f"⏳ Waiting for project deployment to complete...")

            time.sleep(10)

        except Exception as e:
            print(f"⚠️ Error checking project status: {e}")
            time.sleep(10)

    print(f"⏰ Timeout waiting for project to be ready after {max_wait} seconds")
    return False


def get_project_role_arn(domain_id, project_id, region):
    """Get the DataZone project user role ARN from tooling environment provisionedResources."""
    try:
        datazone = boto3.client("datazone", region_name=region)

        # Get project environments
        envs_response = datazone.list_environments(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )

        environments = envs_response.get("items", [])
        print(f"📋 Found {len(environments)} environments")

        # Look for tooling environment
        for env in environments:
            env_name = env.get("name", "").lower()
            env_id = env.get("id")

            if "tooling" in env_name or "tool" in env_name:
                print(f"📋 Found tooling environment: {env_name} ({env_id})")

                try:
                    # Get environment details
                    env_detail = datazone.get_environment(
                        domainIdentifier=domain_id, identifier=env_id
                    )

                    # Look for userRoleArn in provisionedResources
                    provisioned_resources = env_detail.get("provisionedResources", [])

                    for resource in provisioned_resources:
                        resource_name = resource.get("name", "")
                        resource_value = resource.get("value", "")

                        if resource_name == "userRoleArn":
                            print(
                                f"✅ Found user role ARN in provisionedResources: {resource_value}"
                            )

                            # Verify this matches the expected pattern
                            expected_pattern = (
                                f"datazone_usr_role_{project_id}_{env_id}"
                            )
                            if expected_pattern in resource_value:
                                print(
                                    f"✅ Role matches expected pattern: {expected_pattern}"
                                )
                            else:
                                print(
                                    f"⚠️ Role doesn't match expected pattern: {expected_pattern}"
                                )

                            return resource_value

                    print(f"❌ No userRoleArn found in provisionedResources")

                except Exception as e:
                    print(f"❌ Error getting tooling environment details: {e}")
                    continue

        print(f"❌ No tooling environment found")
        return None

    except Exception as e:
        print(f"❌ Error getting project role: {e}")
        return None


def register_lake_formation_location(s3_location, region):
    """Register S3 location with Lake Formation using current session role."""
    try:
        lakeformation = boto3.client("lakeformation", region_name=region)

        # Register the S3 location with service-linked role (current session)
        lakeformation.register_resource(
            ResourceArn=s3_location, UseServiceLinkedRole=True
        )
        print(f"✅ Registered S3 location with Lake Formation: {s3_location}")
        return True

    except lakeformation.exceptions.AlreadyExistsException:
        print(f"📋 S3 location already registered: {s3_location}")
        return True
    except Exception as e:
        print(f"❌ Error registering S3 location: {e}")
        return False


def grant_lake_formation_permissions(database_name, role_arn, region, s3_bucket):
    """Grant Lake Formation permissions to project role."""
    try:
        lakeformation = boto3.client("lakeformation", region_name=region)
        glue = boto3.client("glue", region_name=region)

        # Register S3 location with Lake Formation first
        s3_location = f"arn:aws:s3:::{s3_bucket}/covid19-data/"
        if not register_lake_formation_location(s3_location, region):
            print("⚠️ Failed to register S3 location, continuing with permissions...")

        # Grant database permissions
        try:
            lakeformation.grant_permissions(
                Principal={"DataLakePrincipalIdentifier": role_arn},
                Resource={"Database": {"Name": database_name}},
                Permissions=["ALL"],
                PermissionsWithGrantOption=["ALL"],
            )
            print(f"✅ Granted database permissions to {role_arn}")
        except Exception as e:
            print(f"⚠️ Database permissions: {e}")

        # Get all tables in database and grant permissions
        try:
            tables_response = glue.get_tables(DatabaseName=database_name)
            tables = tables_response.get("TableList", [])

            for table in tables:
                table_name = table["Name"]
                try:
                    lakeformation.grant_permissions(
                        Principal={"DataLakePrincipalIdentifier": role_arn},
                        Resource={
                            "Table": {"DatabaseName": database_name, "Name": table_name}
                        },
                        Permissions=["ALL"],
                        PermissionsWithGrantOption=["ALL"],
                    )
                    print(f"✅ Granted table permissions for {table_name}")
                except Exception as e:
                    print(f"⚠️ Table {table_name} permissions: {e}")

            # Also grant permissions on all tables using wildcard
            try:
                lakeformation.grant_permissions(
                    Principal={"DataLakePrincipalIdentifier": role_arn},
                    Resource={"Table": {"DatabaseName": database_name, "Name": "*"}},
                    Permissions=["ALL"],
                    PermissionsWithGrantOption=["ALL"],
                )
                print(
                    f"✅ Granted wildcard table permissions for all tables in {database_name}"
                )
            except Exception as e:
                print(f"⚠️ Wildcard table permissions: {e}")

        except Exception as e:
            print(f"❌ Error getting tables: {e}")

        return True

    except Exception as e:
        print(f"❌ Error granting Lake Formation permissions: {e}")
        return False
    """Get the S3 bucket associated with the domain."""
    try:
        s3 = boto3.client("s3", region_name=region)
        response = s3.list_buckets()

        for bucket in response["Buckets"]:
            bucket_name = bucket["Name"]
            if (
                domain_name.lower() in bucket_name.lower()
                and "datazone" in bucket_name.lower()
            ):
                return bucket_name

        bucket_name = f"datazone-{domain_name.lower()}-{region}"
        print(f"Using bucket: {bucket_name}")
        return bucket_name

    except Exception as e:
        print(f"Error finding domain bucket: {e}")
        return f"datazone-{domain_name.lower()}-{region}"


def get_domain_bucket(domain_name, region):
    """Get the S3 bucket associated with the domain."""
    try:
        s3 = boto3.client("s3", region_name=region)
        response = s3.list_buckets()

        for bucket in response["Buckets"]:
            bucket_name = bucket["Name"]
            if (
                domain_name.lower() in bucket_name.lower()
                and "datazone" in bucket_name.lower()
            ):
                return bucket_name

        bucket_name = f"datazone-{domain_name.lower()}-{region}"
        print(f"Using bucket: {bucket_name}")
        return bucket_name

    except Exception as e:
        print(f"Error finding domain bucket: {e}")
        return f"datazone-{domain_name.lower()}-{region}"


def upload_to_s3(file_path, bucket, s3_key, region):
    """Upload file to S3."""
    s3 = boto3.client("s3", region_name=region)
    try:
        s3.upload_file(file_path, bucket, s3_key)
        print(f"✅ Uploaded {s3_key}")
        return True
    except Exception as e:
        print(f"❌ Failed to upload {s3_key}: {e}")
        return False


def infer_glue_schema(df):
    """Infer Glue table schema from pandas DataFrame."""
    columns = []
    for col_name, dtype in df.dtypes.items():
        if pd.api.types.is_integer_dtype(dtype):
            glue_type = "bigint"
        elif pd.api.types.is_float_dtype(dtype):
            glue_type = "double"
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            glue_type = "timestamp"
        else:
            glue_type = "string"

        columns.append(
            {
                "Name": col_name.replace(" ", "_").replace("-", "_").lower(),
                "Type": glue_type,
            }
        )

    return columns


def create_glue_table(table_name, database_name, s3_location, columns, region):
    """Create Glue table."""
    glue = boto3.client("glue", region_name=region)

    try:
        glue.create_table(
            DatabaseName=database_name,
            TableInput={
                "Name": table_name,
                "StorageDescriptor": {
                    "Columns": columns,
                    "Location": s3_location,
                    "InputFormat": "org.apache.hadoop.mapred.TextInputFormat",
                    "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
                    "SerdeInfo": {
                        "SerializationLibrary": "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe",
                        "Parameters": {
                            "field.delim": ",",
                            "skip.header.line.count": "1",
                        },
                    },
                },
                "Parameters": {
                    "classification": "csv",
                    "delimiter": ",",
                    "skip.header.line.count": "1",
                },
            },
        )
        print(f"✅ Created table: {table_name}")
        return True
    except Exception as e:
        print(f"❌ Failed to create table {table_name}: {e}")
        return False


def test_athena_query(database_name, table_name, region, bucket_name):
    """Test table with Athena query and return record count."""
    athena = boto3.client("athena", region_name=region)

    query = f"SELECT COUNT(*) as row_count FROM {database_name}.{table_name}"

    try:
        response = athena.start_query_execution(
            QueryString=query,
            ResultConfiguration={
                "OutputLocation": f"s3://{bucket_name}/athena-results/"
            },
        )

        query_id = response["QueryExecutionId"]

        # Wait for query completion
        for _ in range(30):
            result = athena.get_query_execution(QueryExecutionId=query_id)
            status = result["QueryExecution"]["Status"]["State"]

            if status == "SUCCEEDED":
                # Get query results
                results = athena.get_query_results(QueryExecutionId=query_id)
                rows = results["ResultSet"]["Rows"]
                if len(rows) > 1:  # Skip header row
                    count = int(rows[1]["Data"][0]["VarCharValue"])
                    if count > 0:
                        print(
                            f"✅ Athena query succeeded for {table_name}: {count:,} records"
                        )
                        return True
                    else:
                        print(f"❌ Table {table_name} is empty (0 records)")
                        return False
                else:
                    print(f"❌ No data returned for {table_name}")
                    return False
            elif status in ["FAILED", "CANCELLED"]:
                print(
                    f"❌ Athena query failed for {table_name}: {result['QueryExecution']['Status'].get('StateChangeReason', '')}"
                )
                return False

            time.sleep(2)

        print(f"⏰ Athena query timeout for {table_name}")
        return False

    except Exception as e:
        print(f"❌ Athena query error for {table_name}: {e}")
        return False


def create_datazone_data_source(domain_id, project_id, database_name, region):
    """Create DataZone data source for the database."""
    try:
        datazone = boto3.client("datazone", region_name=region)

        # Create data source without environment ID for V2 domains
        data_source_name = f"covid19-data-source"

        response = datazone.create_data_source(
            domainIdentifier=domain_id,
            projectIdentifier=project_id,
            name=data_source_name,
            description=f"COVID-19 dataset from {database_name} database",
            type="GLUE",
            configuration={
                "glueRunConfiguration": {
                    "relationalFilterConfigurations": [
                        {"databaseName": database_name, "schemaName": "default"}
                    ]
                }
            },
            enableSetting="ENABLED",
            publishOnImport=True,
        )

        data_source_id = response.get("id")
        print(f"✅ Created data source: {data_source_name} ({data_source_id})")

        return data_source_id

    except Exception as e:
        print(f"❌ Error creating data source: {e}")
        return None


def run_data_source(domain_id, data_source_id, region):
    """Run the DataZone data source to ingest data."""
    try:
        datazone = boto3.client("datazone", region_name=region)

        # Start data source run
        response = datazone.start_data_source_run(
            domainIdentifier=domain_id, dataSourceIdentifier=data_source_id
        )

        run_id = response.get("id")
        run_status = response.get("status")

        print(f"✅ Started data source run: {run_id}")
        print(f"📋 Initial status: {run_status}")

        return run_id

    except Exception as e:
        print(f"❌ Error starting data source run: {e}")
        return None


def wait_for_data_source_run(domain_id, data_source_id, run_id, region, max_wait=300):
    """Wait for data source run to complete."""
    import time

    datazone = boto3.client("datazone", region_name=region)
    start_time = time.time()

    print(f"⏳ Waiting for data source run to complete...")

    while time.time() - start_time < max_wait:
        try:
            response = datazone.get_data_source_run(
                domainIdentifier=domain_id, identifier=run_id
            )

            status = response.get("status")
            print(f"📋 Run status: {status}")

            if status == "SUCCESS":
                print(f"✅ Data source run completed successfully")

                # Show ingested assets
                assets_created = response.get("assetCreationCount", 0)
                assets_updated = response.get("assetUpdateCount", 0)
                print(f"📊 Assets created: {assets_created}, updated: {assets_updated}")

                return True
            elif status in ["FAILED", "ABORTED"]:
                error_message = response.get("errorMessage", "Unknown error")
                print(f"❌ Data source run failed: {error_message}")
                return False

            time.sleep(10)

        except Exception as e:
            print(f"⚠️ Error checking run status: {e}")
            time.sleep(10)

    print(f"⏰ Timeout waiting for data source run after {max_wait} seconds")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Setup COVID-19 dataset for SMUS domain"
    )
    parser.add_argument("domain_name", help="SageMaker Unified Studio domain name")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--database", default="covid19_db", help="Glue database name")
    parser.add_argument(
        "--data-path", default="./covid-19-data", help="Local COVID-19 data path"
    )
    parser.add_argument(
        "--project-name", default="covid-lake-admin", help="DataZone project name"
    )

    args = parser.parse_args()

    print(f"🚀 Setting up COVID-19 data for domain: {args.domain_name}")
    print(f"📂 Using local data from: {args.data_path}")

    # Check if data path exists
    data_path = Path(args.data_path)
    if not data_path.exists():
        print(f"❌ Data path does not exist: {args.data_path}")
        return

    # Create DataZone project
    print(f"\n🏗️ Creating DataZone project: {args.project_name}")
    project_info = create_datazone_project(
        args.domain_name, args.project_name, args.region
    )
    if not project_info:
        print("❌ Failed to create DataZone project")
        return

    # Wait for project to be fully ready
    if not wait_for_project_ready(
        project_info["domainId"], project_info["projectId"], args.region
    ):
        print("❌ Project not ready within timeout, continuing anyway...")

    # Add Eng1 as project owner
    print(f"\n👤 Adding Eng1 as project owner...")
    add_project_member(
        project_info["domainId"], project_info["projectId"], "Eng1", args.region
    )

    # Get domain bucket
    bucket_name = get_domain_bucket(args.domain_name, args.region)

    # Create Glue database
    glue = boto3.client("glue", region_name=args.region)
    try:
        glue.create_database(
            DatabaseInput={
                "Name": args.database,
                "Description": "COVID-19 dataset for testing",
            }
        )
        print(f"✅ Created database: {args.database}")
    except glue.exceptions.AlreadyExistsException:
        print(f"📋 Database {args.database} already exists")
    except Exception as e:
        print(f"❌ Failed to create database: {e}")
        return

    # Find CSV files
    csv_files = list(data_path.glob("**/*.csv"))
    print(f"📊 Found {len(csv_files)} CSV files")

    successful_tables = 0

    for csv_file in csv_files[:5]:  # Limit to first 5 files for testing
        try:
            # Read CSV to infer schema
            df = pd.read_csv(csv_file, nrows=1000)  # Sample for schema
            if df.empty:
                continue

            # Generate table name
            table_name = csv_file.stem.replace("-", "_").replace(" ", "_").lower()
            s3_prefix = f"covid19-data/{table_name}/"
            s3_key = f"{s3_prefix}{csv_file.name}"
            s3_location = f"s3://{bucket_name}/{s3_prefix}"

            print(f"\n📋 Processing: {table_name}")

            # Upload to S3
            if not upload_to_s3(str(csv_file), bucket_name, s3_key, args.region):
                continue

            # Infer schema
            columns = infer_glue_schema(df)

            # Create Glue table
            table_created = create_glue_table(
                table_name, args.database, s3_location, columns, args.region
            )
            if not table_created:
                # Table might already exist, continue to test it
                print(f"📋 Table {table_name} already exists, testing...")

            # Test with Athena (regardless of table creation status)
            if test_athena_query(args.database, table_name, args.region, bucket_name):
                successful_tables += 1

        except Exception as e:
            print(f"❌ Error processing {csv_file}: {e}")
            continue

    # Grant Lake Formation permissions to project role
    print(f"\n🔐 Setting up Lake Formation permissions...")
    project_role_arn = get_project_role_arn(
        project_info["domainId"], project_info["projectId"], args.region
    )
    if project_role_arn:
        grant_lake_formation_permissions(
            args.database, project_role_arn, args.region, bucket_name
        )

    # Create and run DataZone data source
    print(f"\n📊 Creating DataZone data source...")
    data_source_id = create_datazone_data_source(
        project_info["domainId"], project_info["projectId"], args.database, args.region
    )

    if data_source_id:
        print(f"\n🚀 Running data source to ingest COVID-19 data...")
        run_id = run_data_source(project_info["domainId"], data_source_id, args.region)

        if run_id:
            wait_for_data_source_run(
                project_info["domainId"], data_source_id, run_id, args.region
            )

    print(
        f"\n🎉 Successfully created {successful_tables} queryable tables in {args.database}"
    )
    print(f"📍 Data location: s3://{bucket_name}/covid19-data/")
    print(f"🏗️ DataZone project: {args.project_name} ({project_info['projectId']})")
    print(f"🔍 Test queries in Athena using database: {args.database}")


if __name__ == "__main__":
    main()

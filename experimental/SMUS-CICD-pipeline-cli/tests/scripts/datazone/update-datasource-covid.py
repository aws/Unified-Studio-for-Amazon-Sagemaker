#!/usr/bin/env python3
"""
Find DataZone data source linked to default_lakehouse connection,
add covid19_db to it, and run it.
"""

import boto3
import time


def find_default_data_source(domain_id, project_id, region):
    """Find the default data source (usually has wildcard database filter)."""
    try:
        datazone = boto3.client("datazone", region_name=region)

        # List data sources in the project
        response = datazone.list_data_sources(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )

        data_sources = response.get("items", [])
        print(f"📋 Found {len(data_sources)} data sources")

        for ds in data_sources:
            ds_id = ds.get("dataSourceId")
            ds_name = ds.get("name", "Unknown")
            ds_type = ds.get("type", "Unknown")

            # Get data source details
            try:
                detail_response = datazone.get_data_source(
                    domainIdentifier=domain_id, identifier=ds_id
                )

                # Check if it's a GLUE data source with default configuration
                if ds_type == "GLUE" and "default-datasource" in ds_name:
                    config = detail_response.get("configuration", {})
                    glue_config = config.get("glueRunConfiguration", {})
                    filters = glue_config.get("relationalFilterConfigurations", [])

                    # Check if it has wildcard or is the main default data source
                    has_wildcard = any(
                        filter_config.get("databaseName") == "*"
                        for filter_config in filters
                    )

                    if has_wildcard or "covid-lake-admin-default" in ds_name:
                        print(f"✅ Found default data source: {ds_name} ({ds_id})")
                        print(f"📋 Current database filters: {len(filters)}")
                        for filter_config in filters:
                            db_name = filter_config.get("databaseName", "Unknown")
                            schema_name = filter_config.get("schemaName", "default")
                            print(f"   - {db_name}.{schema_name}")
                        return ds_id, ds_name

            except Exception as e:
                print(f"⚠️ Error getting data source details for {ds_id}: {e}")
                continue

        print("❌ No suitable default data source found")
        return None, None

    except Exception as e:
        print(f"❌ Error listing data sources: {e}")
        return None, None


def update_data_source_with_covid_db(domain_id, data_source_id, region):
    """Update data source to include covid19_db."""
    try:
        datazone = boto3.client("datazone", region_name=region)

        # Get current data source configuration
        response = datazone.get_data_source(
            domainIdentifier=domain_id, identifier=data_source_id
        )

        current_config = response.get("configuration", {})
        glue_config = current_config.get("glueRunConfiguration", {})
        current_filters = glue_config.get("relationalFilterConfigurations", [])

        print(f"📋 Current database filters: {len(current_filters)}")

        # Check if covid19_db is already included
        covid_db_exists = any(
            filter_config.get("databaseName") == "covid19_db"
            for filter_config in current_filters
        )

        if covid_db_exists:
            print(f"📋 covid19_db already included in data source")
            return True

        # Add covid19_db to the filters
        new_filter = {"databaseName": "covid19_db", "schemaName": "default"}

        updated_filters = current_filters + [new_filter]

        # Update data source configuration
        updated_config = {
            "glueRunConfiguration": {"relationalFilterConfigurations": updated_filters}
        }

        datazone.update_data_source(
            domainIdentifier=domain_id,
            identifier=data_source_id,
            configuration=updated_config,
        )

        print(f"✅ Added covid19_db to data source configuration")
        print(f"📋 Total databases now: {len(updated_filters)}")

        return True

    except Exception as e:
        print(f"❌ Error updating data source: {e}")
        return False


def wait_for_data_source_ready(domain_id, data_source_id, region, max_wait=180):
    """Wait for data source to be ready after update."""
    datazone = boto3.client("datazone", region_name=region)
    start_time = time.time()

    print(f"⏳ Waiting for data source to be ready...")

    while time.time() - start_time < max_wait:
        try:
            response = datazone.get_data_source(
                domainIdentifier=domain_id, identifier=data_source_id
            )

            status = response.get("status")
            print(f"📋 Data source status: {status}")

            if status == "READY":
                print(f"✅ Data source is ready")
                return True
            elif status in ["FAILED", "DELETING"]:
                print(f"❌ Data source in failed state: {status}")
                return False

            time.sleep(10)

        except Exception as e:
            print(f"⚠️ Error checking data source status: {e}")
            time.sleep(10)

    print(f"⏰ Timeout waiting for data source to be ready")
    return False


def run_data_source(domain_id, data_source_id, region):
    """Run the data source."""
    try:
        datazone = boto3.client("datazone", region_name=region)

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


def wait_for_run_completion(domain_id, run_id, region, max_wait=300):
    """Wait for data source run to complete."""
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
                assets_created = response.get("assetCreationCount", 0)
                assets_updated = response.get("assetUpdateCount", 0)
                print(f"✅ Data source run completed successfully")
                print(f"📊 Assets created: {assets_created}, updated: {assets_updated}")
                return True
            elif status in ["FAILED", "ABORTED"]:
                error_message = response.get("errorMessage", "Unknown error")
                print(f"❌ Data source run failed: {error_message}")
                return False

            time.sleep(15)

        except Exception as e:
            print(f"⚠️ Error checking run status: {e}")
            time.sleep(15)

    print(f"⏰ Timeout after {max_wait} seconds")
    return False


def main():
    # Known values
    domain_id = "<DOMAIN_ID>"
    project_id = "d8ipo2t2p8oalj"
    region = "us-east-1"

    print(f"🔍 Finding default data source in project: {project_id}")

    # Find the default data source
    data_source_id, data_source_name = find_default_data_source(
        domain_id, project_id, region
    )

    if not data_source_id:
        print("❌ No lakehouse data source found")
        return

    # Update data source to include covid19_db
    print(f"\n📝 Updating data source to include covid19_db...")
    if not update_data_source_with_covid_db(domain_id, data_source_id, region):
        print("❌ Failed to update data source")
        return

    # Wait for data source to be ready
    print(f"\n⏳ Waiting for data source to be ready...")
    if not wait_for_data_source_ready(domain_id, data_source_id, region):
        print("❌ Data source not ready, cannot run")
        return

    # Run the data source
    print(f"\n🚀 Running data source: {data_source_name}")
    run_id = run_data_source(domain_id, data_source_id, region)

    if run_id:
        wait_for_run_completion(domain_id, run_id, region)

    print(f"\n🎉 Process complete!")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Fix the data source configuration by removing schema name.
"""

import boto3


def fix_data_source():
    domain_id = "<DOMAIN_ID>"
    data_source_id = "4cwzmlddk64enb"  # The failed data source
    region = "us-east-1"

    datazone = boto3.client("datazone", region_name=region)

    print(f"🔧 Fixing data source configuration...")

    # Update with correct configuration (no schema name)
    updated_config = {
        "glueRunConfiguration": {
            "relationalFilterConfigurations": [
                {
                    "databaseName": "*",
                    "filterExpressions": [{"expression": "*", "type": "INCLUDE"}],
                },
                {
                    "databaseName": "covid19_db",
                    "filterExpressions": [{"expression": "*", "type": "INCLUDE"}],
                },
            ]
        }
    }

    try:
        datazone.update_data_source(
            domainIdentifier=domain_id,
            identifier=data_source_id,
            configuration=updated_config,
        )

        print(f"✅ Fixed data source configuration")
        print(f"📋 Removed schema name, added filter expressions")

        return True

    except Exception as e:
        print(f"❌ Error fixing data source: {e}")
        return False


if __name__ == "__main__":
    fix_data_source()

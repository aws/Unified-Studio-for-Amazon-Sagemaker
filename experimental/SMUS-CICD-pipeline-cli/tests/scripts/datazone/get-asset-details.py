#!/usr/bin/env python3
"""
Get COVID-19 asset details to understand structure.
"""

import boto3
import json


def get_asset_details():
    domain_id = "<DOMAIN_ID>"
    asset_id = "5wv8ic57ncebhj"  # time_series_19_covid_combined
    region = "us-east-1"

    datazone = boto3.client("datazone", region_name=region)

    print(f"📋 Getting asset details...")

    try:
        response = datazone.get_asset(domainIdentifier=domain_id, identifier=asset_id)

        print(json.dumps(response, indent=2, default=str))

    except Exception as e:
        print(f"❌ Error getting asset: {e}")


if __name__ == "__main__":
    get_asset_details()

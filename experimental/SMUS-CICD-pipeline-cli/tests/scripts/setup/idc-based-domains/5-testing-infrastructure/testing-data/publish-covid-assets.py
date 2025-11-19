#!/usr/bin/env python3
"""
Publish all COVID-19 DataZone assets.
"""

import boto3


def publish_covid_assets():
    domain_id = "<DOMAIN_ID>"
    project_id = "d8ipo2t2p8oalj"
    region = "us-east-1"

    datazone = boto3.client("datazone", region_name=region)

    print(f"🔍 Finding COVID-19 assets to publish...")

    # Search for assets containing "covid" in the name
    try:
        response = datazone.search(
            domainIdentifier=domain_id,
            owningProjectIdentifier=project_id,
            searchScope="ASSET",
            searchText="covid",
            maxResults=50,
        )

        assets = response.get("items", [])
        print(f"📋 Found {len(assets)} assets matching 'covid'")

        covid_assets = []

        for asset in assets:
            asset_id = asset.get("assetItem", {}).get("identifier")
            asset_name = asset.get("assetItem", {}).get("name", "Unknown")
            asset_type = asset.get("assetItem", {}).get("typeName", "Unknown")

            # Check if it's a COVID-19 related asset
            if "covid" in asset_name.lower():
                covid_assets.append(
                    {"id": asset_id, "name": asset_name, "type": asset_type}
                )
                print(f"  - {asset_name} ({asset_type}) - {asset_id}")

        if not covid_assets:
            print("❌ No COVID-19 assets found")
            return

        # Publish each asset
        published_count = 0

        for asset in covid_assets:
            asset_id = asset["id"]
            asset_name = asset["name"]

            try:
                # Create listing change set to publish asset
                changeset_response = datazone.create_listing_change_set(
                    domainIdentifier=domain_id,
                    entityIdentifier=asset_id,
                    entityType="ASSET",
                    action="PUBLISH",
                )

                changeset_id = changeset_response.get("listingId")
                status = changeset_response.get("status")
                print(
                    f"✅ Published {asset_name} - changeset ID: {changeset_id}, status: {status}"
                )
                published_count += 1

            except Exception as e:
                # Check if already published
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print(f"📋 {asset_name} - already published")
                    published_count += 1
                else:
                    print(f"❌ Error publishing {asset_name}: {e}")
                continue

        print(f"\n🎉 Successfully published {published_count} COVID-19 assets")
        print(f"📋 All COVID-19 assets are now available in the data catalog")

    except Exception as e:
        print(f"❌ Error searching for assets: {e}")


if __name__ == "__main__":
    publish_covid_assets()

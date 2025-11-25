#!/usr/bin/env python3
"""
Get detailed information about COVID listings.
"""

import boto3
import json


def get_listing_details():
    domain_id = "<DOMAIN_ID>"
    region = "us-east-1"

    datazone = boto3.client("datazone", region_name=region)

    print(f"🔍 Getting detailed listing information...")

    try:
        # Search listings for covid assets
        response = datazone.search_listings(
            domainIdentifier=domain_id, searchText="covid", maxResults=50
        )

        print(f"📋 Full search response:")
        print(json.dumps(response, indent=2, default=str))

        listings = response.get("items", [])

        for i, listing in enumerate(listings, 1):
            print(f"\n{'='*60}")
            print(f"LISTING {i}:")
            print(f"{'='*60}")
            print(json.dumps(listing, indent=2, default=str))

            # Try to get listing details if we have an ID
            listing_item = listing.get("listingItem", {})
            listing_id = listing_item.get("listingId")

            if listing_id and listing_id != "Unknown":
                try:
                    detail_response = datazone.get_listing(
                        domainIdentifier=domain_id, identifier=listing_id
                    )

                    print(f"\n📋 Detailed listing info:")
                    print(json.dumps(detail_response, indent=2, default=str))

                except Exception as e:
                    print(f"❌ Error getting listing details: {e}")

    except Exception as e:
        print(f"❌ Error searching listings: {e}")


if __name__ == "__main__":
    get_listing_details()

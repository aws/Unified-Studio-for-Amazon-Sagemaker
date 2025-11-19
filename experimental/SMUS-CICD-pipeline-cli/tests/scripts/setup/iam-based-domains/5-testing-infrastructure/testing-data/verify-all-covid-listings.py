#!/usr/bin/env python3
"""
Verify all COVID-19 tables are published by searching with different terms.
"""

import boto3


def verify_all_covid_listings():
    domain_id = "<DOMAIN_ID>"
    region = "us-east-1"

    datazone = boto3.client("datazone", region_name=region)

    # Search terms to find all COVID tables
    search_terms = [
        "covid",
        "countries_aggregated",
        "reference",
        "time_series",
        "us_simplified",
        "worldwide_aggregate",
    ]

    all_listings = set()

    print(f"🔍 Searching for all COVID-19 listings...")

    for term in search_terms:
        try:
            response = datazone.search_listings(
                domainIdentifier=domain_id, searchText=term, maxResults=50
            )

            listings = response.get("items", [])
            print(f"\n📋 Search '{term}': {len(listings)} results")

            for listing in listings:
                asset_listing = listing.get("assetListing", {})
                name = asset_listing.get("name", "Unknown")
                listing_id = asset_listing.get("listingId", "Unknown")

                # Check if it's a COVID table
                covid_tables = [
                    "countries_aggregated",
                    "reference",
                    "time_series_19_covid_combined",
                    "us_simplified",
                    "worldwide_aggregate",
                ]
                if name in covid_tables:
                    all_listings.add((name, listing_id))
                    print(f"  ✅ {name} ({listing_id})")

        except Exception as e:
            print(f"❌ Error searching for '{term}': {e}")

    print(f"\n🎉 SUMMARY - Found {len(all_listings)} unique COVID-19 listings:")
    for name, listing_id in sorted(all_listings):
        print(f"  ✅ {name} ({listing_id})")

    # Also try searching without any text to see all listings
    print(f"\n🔍 Checking recent listings...")
    try:
        response = datazone.search_listings(domainIdentifier=domain_id, maxResults=20)

        recent_listings = response.get("items", [])
        print(f"📋 Recent listings: {len(recent_listings)}")

        covid_in_recent = 0
        for listing in recent_listings:
            asset_listing = listing.get("assetListing", {})
            name = asset_listing.get("name", "Unknown")
            listing_id = asset_listing.get("listingId", "Unknown")

            covid_tables = [
                "countries_aggregated",
                "reference",
                "time_series_19_covid_combined",
                "us_simplified",
                "worldwide_aggregate",
            ]
            if name in covid_tables:
                covid_in_recent += 1
                print(f"  ✅ {name} ({listing_id})")

        print(f"📊 COVID tables in recent listings: {covid_in_recent}")

    except Exception as e:
        print(f"❌ Error getting recent listings: {e}")


if __name__ == "__main__":
    verify_all_covid_listings()

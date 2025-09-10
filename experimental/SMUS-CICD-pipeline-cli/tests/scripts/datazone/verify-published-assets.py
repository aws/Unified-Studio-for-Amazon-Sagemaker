#!/usr/bin/env python3
"""
Verify COVID-19 assets are published by searching listings.
"""

import boto3

def verify_published_assets():
    domain_id = "<DOMAIN_ID>"
    region = "us-east-1"
    
    datazone = boto3.client('datazone', region_name=region)
    
    print(f"🔍 Searching listings for COVID-19 assets...")
    
    try:
        # Search listings for covid assets
        response = datazone.search_listings(
            domainIdentifier=domain_id,
            searchText='covid',
            maxResults=50
        )
        
        listings = response.get('items', [])
        print(f"📋 Found {len(listings)} listings matching 'covid'")
        
        if not listings:
            print("❌ No COVID-19 assets found in listings - they are NOT published")
            
            # Also try searching without text to see all listings
            print("\n🔍 Checking all listings...")
            all_response = datazone.search_listings(
                domainIdentifier=domain_id,
                maxResults=20
            )
            
            all_listings = all_response.get('items', [])
            print(f"📋 Total listings in domain: {len(all_listings)}")
            
            for listing in all_listings:
                listing_item = listing.get('listingItem', {})
                name = listing_item.get('name', 'Unknown')
                listing_id = listing_item.get('listingId', 'Unknown')
                print(f"  - {name} ({listing_id})")
            
        else:
            print("✅ COVID-19 assets found in listings:")
            for listing in listings:
                listing_item = listing.get('listingItem', {})
                name = listing_item.get('name', 'Unknown')
                listing_id = listing_item.get('listingId', 'Unknown')
                description = listing_item.get('description', 'No description')
                print(f"  ✅ {name} ({listing_id})")
                print(f"     Description: {description}")
        
    except Exception as e:
        print(f"❌ Error searching listings: {e}")

if __name__ == "__main__":
    verify_published_assets()

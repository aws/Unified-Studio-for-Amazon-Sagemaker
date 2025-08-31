#!/usr/bin/env python3
"""
Check COVID-19 asset status to see if they're already published.
"""

import boto3
import json

def check_asset_status():
    domain_id = "dzd_6je2k8b63qse07"
    project_id = "d8ipo2t2p8oalj"
    region = "us-east-1"
    
    datazone = boto3.client('datazone', region_name=region)
    
    print(f"🔍 Checking COVID-19 asset status...")
    
    # Search for assets containing "covid" in the name
    try:
        response = datazone.search(
            domainIdentifier=domain_id,
            owningProjectIdentifier=project_id,
            searchScope='ASSET',
            searchText='covid',
            maxResults=50
        )
        
        assets = response.get('items', [])
        print(f"📋 Found {len(assets)} assets matching 'covid'")
        
        for asset in assets:
            asset_item = asset.get('assetItem', {})
            asset_id = asset_item.get('identifier')
            asset_name = asset_item.get('name', 'Unknown')
            
            if 'covid' in asset_name.lower():
                print(f"\n📊 Asset: {asset_name} ({asset_id})")
                
                # Get detailed asset information
                try:
                    asset_detail = datazone.get_asset(
                        domainIdentifier=domain_id,
                        identifier=asset_id
                    )
                    
                    # Check if there are any status or publication fields
                    print(f"  Created: {asset_detail.get('createdAt')}")
                    print(f"  Revision: {asset_detail.get('revision')}")
                    
                    # Check forms for any publication status
                    forms = asset_detail.get('formsOutput', [])
                    for form in forms:
                        form_name = form.get('formName')
                        if 'subscription' in form_name.lower() or 'publish' in form_name.lower():
                            print(f"  {form_name}: {form.get('content')}")
                    
                    # Try to search for this asset in listings
                    try:
                        listing_response = datazone.search_listings(
                            domainIdentifier=domain_id,
                            searchText=asset_name,
                            maxResults=10
                        )
                        
                        listings = listing_response.get('items', [])
                        if listings:
                            print(f"  ✅ Found in {len(listings)} listings")
                            for listing in listings:
                                listing_item = listing.get('listingItem', {})
                                print(f"    - Listing: {listing_item.get('name')} ({listing_item.get('listingId')})")
                        else:
                            print(f"  ❌ Not found in any listings")
                            
                    except Exception as e:
                        print(f"  ⚠️ Error checking listings: {e}")
                    
                except Exception as e:
                    print(f"  ❌ Error getting asset details: {e}")
        
    except Exception as e:
        print(f"❌ Error searching for assets: {e}")

if __name__ == "__main__":
    check_asset_status()

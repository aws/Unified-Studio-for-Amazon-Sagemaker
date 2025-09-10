#!/usr/bin/env python3
"""
Find and publish ALL COVID-19 tables.
"""

import boto3

def publish_all_covid_tables():
    domain_id = "<DOMAIN_ID>"
    project_id = "d8ipo2t2p8oalj"
    region = "us-east-1"
    
    datazone = boto3.client('datazone', region_name=region)
    
    # List of COVID-19 table names we expect
    covid_tables = [
        'countries_aggregated',
        'reference', 
        'time_series_19_covid_combined',
        'us_simplified',
        'worldwide_aggregate'
    ]
    
    print(f"🔍 Finding ALL COVID-19 tables...")
    
    # Search for each table individually
    all_assets = []
    
    for table_name in covid_tables:
        try:
            response = datazone.search(
                domainIdentifier=domain_id,
                owningProjectIdentifier=project_id,
                searchScope='ASSET',
                searchText=table_name,
                maxResults=10
            )
            
            assets = response.get('items', [])
            for asset in assets:
                asset_item = asset.get('assetItem', {})
                asset_id = asset_item.get('identifier')
                asset_name = asset_item.get('name', 'Unknown')
                
                if asset_name == table_name:
                    all_assets.append({
                        'id': asset_id,
                        'name': asset_name
                    })
                    print(f"  ✅ Found: {asset_name} ({asset_id})")
                    break
            else:
                print(f"  ❌ Not found: {table_name}")
                
        except Exception as e:
            print(f"  ❌ Error searching for {table_name}: {e}")
    
    print(f"\n📋 Found {len(all_assets)} COVID-19 tables")
    
    if not all_assets:
        print("❌ No COVID-19 tables found")
        return
    
    # Process each asset: set approval not required and publish
    processed_count = 0
    
    for asset in all_assets:
        asset_id = asset['id']
        asset_name = asset['name']
        
        print(f"\n🔧 Processing: {asset_name}")
        
        try:
            # 1. Set approval not required
            asset_response = datazone.get_asset(
                domainIdentifier=domain_id,
                identifier=asset_id
            )
            
            forms_output = asset_response.get('formsOutput', [])
            updated_forms = []
            needs_update = False
            
            for form in forms_output:
                if form.get('formName') == 'SubscriptionTermsForm':
                    current_content = form.get('content', '{}')
                    if '"approvalRequired":"YES"' in current_content:
                        updated_form = {
                            'formName': form['formName'],
                            'content': '{"approvalRequired":"NO"}',
                            'typeIdentifier': form['typeName'],
                            'typeRevision': form['typeRevision']
                        }
                        updated_forms.append(updated_form)
                        needs_update = True
                        print(f"  📝 Will update approval to NO")
                    else:
                        updated_forms.append({
                            'formName': form['formName'],
                            'content': form['content'],
                            'typeIdentifier': form['typeName'],
                            'typeRevision': form['typeRevision']
                        })
                        print(f"  📋 Approval already NO")
                else:
                    updated_forms.append({
                        'formName': form['formName'],
                        'content': form['content'],
                        'typeIdentifier': form['typeName'],
                        'typeRevision': form['typeRevision']
                    })
            
            # Create new revision if needed
            if needs_update:
                datazone.create_asset_revision(
                    domainIdentifier=domain_id,
                    identifier=asset_id,
                    name=asset_response['name'],
                    typeRevision=asset_response['typeRevision'],
                    formsInput=updated_forms
                )
                print(f"  ✅ Updated approval setting")
            
            # 2. Publish asset
            try:
                changeset_response = datazone.create_listing_change_set(
                    domainIdentifier=domain_id,
                    entityIdentifier=asset_id,
                    entityType='ASSET',
                    action='PUBLISH'
                )
                
                changeset_id = changeset_response.get('listingId')
                print(f"  ✅ Published - listing ID: {changeset_id}")
                processed_count += 1
                
            except Exception as e:
                if 'already' in str(e).lower():
                    print(f"  📋 Already published")
                    processed_count += 1
                else:
                    print(f"  ❌ Error publishing: {e}")
            
        except Exception as e:
            print(f"  ❌ Error processing {asset_name}: {e}")
    
    print(f"\n🎉 Successfully processed {processed_count} COVID-19 tables")
    
    # Verify all are published
    print(f"\n🔍 Verifying all tables are published...")
    
    try:
        response = datazone.search_listings(
            domainIdentifier=domain_id,
            searchText='covid',
            maxResults=50
        )
        
        published_listings = response.get('items', [])
        print(f"📋 Found {len(published_listings)} COVID-19 listings:")
        
        for listing in published_listings:
            asset_listing = listing.get('assetListing', {})
            name = asset_listing.get('name', 'Unknown')
            listing_id = asset_listing.get('listingId', 'Unknown')
            print(f"  ✅ {name} ({listing_id})")
            
    except Exception as e:
        print(f"❌ Error verifying listings: {e}")

if __name__ == "__main__":
    publish_all_covid_tables()

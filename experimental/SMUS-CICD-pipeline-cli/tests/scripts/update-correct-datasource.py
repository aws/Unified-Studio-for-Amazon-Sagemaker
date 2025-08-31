#!/usr/bin/env python3
"""
Update the correct data source (with account catalogName) to include covid19_db.
"""

import boto3
import time

def update_and_run_data_source():
    domain_id = "dzd_6je2k8b63qse07"
    data_source_id = "b1s9jn2dfgi8tj"  # The one with catalogName = account number
    region = "us-east-1"
    
    datazone = boto3.client('datazone', region_name=region)
    
    print(f"📋 Updating correct data source with catalogName = account number...")
    
    # Get current configuration
    response = datazone.get_data_source(
        domainIdentifier=domain_id,
        identifier=data_source_id
    )
    
    current_config = response.get('configuration', {})
    glue_config = current_config.get('glueRunConfiguration', {})
    current_filters = glue_config.get('relationalFilterConfigurations', [])
    
    print(f"Current filters: {len(current_filters)}")
    for filter_config in current_filters:
        db_name = filter_config.get('databaseName')
        print(f"  - {db_name}")
    
    # Check if covid19_db already exists
    covid_exists = any(f.get('databaseName') == 'covid19_db' for f in current_filters)
    
    if covid_exists:
        print(f"📋 covid19_db already in data source")
    else:
        # Add covid19_db filter
        new_filter = {
            'databaseName': 'covid19_db',
            'filterExpressions': [
                {
                    'expression': '*',
                    'type': 'INCLUDE'
                }
            ]
        }
        
        updated_filters = current_filters + [new_filter]
        
        # Update configuration (omit dataAccessRole for connection-based data sources)
        updated_config = {
            'glueRunConfiguration': {
                'catalogName': glue_config.get('catalogName'),
                'autoImportDataQualityResult': glue_config.get('autoImportDataQualityResult', True),
                'relationalFilterConfigurations': updated_filters
            }
        }
        
        datazone.update_data_source(
            domainIdentifier=domain_id,
            identifier=data_source_id,
            configuration=updated_config
        )
        
        print(f"✅ Added covid19_db to data source")
        
        # Wait for ready status
        print(f"⏳ Waiting for data source to be ready...")
        for i in range(18):  # 3 minutes
            time.sleep(10)
            status_response = datazone.get_data_source(
                domainIdentifier=domain_id,
                identifier=data_source_id
            )
            status = status_response.get('status')
            print(f"Status: {status}")
            
            if status == 'READY':
                break
            elif status in ['FAILED', 'FAILED_UPDATE']:
                error_msg = status_response.get('errorMessage', {})
                print(f"❌ Update failed: {error_msg}")
                return
    
    # Run data source
    print(f"🚀 Starting data source run...")
    
    try:
        run_response = datazone.start_data_source_run(
            domainIdentifier=domain_id,
            dataSourceIdentifier=data_source_id
        )
        
        run_id = run_response.get('id')
        print(f"✅ Started run: {run_id}")
        
        # Monitor run
        for i in range(60):  # 10 minutes
            time.sleep(10)
            run_status_response = datazone.get_data_source_run(
                domainIdentifier=domain_id,
                identifier=run_id
            )
            
            run_status = run_status_response.get('status')
            print(f"Run status: {run_status}")
            
            if run_status == 'SUCCESS':
                assets_created = run_status_response.get('assetCreationCount', 0)
                assets_updated = run_status_response.get('assetUpdateCount', 0)
                print(f"🎉 Run completed! Created: {assets_created}, Updated: {assets_updated}")
                break
            elif run_status in ['FAILED', 'ABORTED']:
                error_msg = run_status_response.get('errorMessage', 'Unknown error')
                print(f"❌ Run failed: {error_msg}")
                break
                
    except Exception as e:
        print(f"❌ Error starting run: {e}")

if __name__ == "__main__":
    update_and_run_data_source()

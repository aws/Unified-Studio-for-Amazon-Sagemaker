#!/usr/bin/env python3
"""
Check status and run the data source.
"""

import boto3
import time

def run_data_source():
    domain_id = "<DOMAIN_ID>"
    data_source_id = "4cwzmlddk64enb"
    region = "us-east-1"
    
    datazone = boto3.client('datazone', region_name=region)
    
    # Check current status
    print(f"📋 Checking data source status...")
    response = datazone.get_data_source(
        domainIdentifier=domain_id,
        identifier=data_source_id
    )
    
    status = response.get('status')
    print(f"Status: {status}")
    
    if status != 'READY':
        print(f"⏳ Waiting for data source to be ready...")
        for i in range(30):  # Wait up to 5 minutes
            time.sleep(10)
            response = datazone.get_data_source(
                domainIdentifier=domain_id,
                identifier=data_source_id
            )
            status = response.get('status')
            print(f"Status: {status}")
            
            if status == 'READY':
                break
            elif status in ['FAILED', 'FAILED_UPDATE']:
                error_msg = response.get('errorMessage', {})
                print(f"❌ Data source failed: {error_msg}")
                return
    
    if status == 'READY':
        print(f"🚀 Starting data source run...")
        
        try:
            run_response = datazone.start_data_source_run(
                domainIdentifier=domain_id,
                dataSourceIdentifier=data_source_id
            )
            
            run_id = run_response.get('id')
            print(f"✅ Started run: {run_id}")
            
            # Monitor run
            for i in range(60):  # Wait up to 10 minutes
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
    else:
        print(f"❌ Data source not ready: {status}")

if __name__ == "__main__":
    run_data_source()

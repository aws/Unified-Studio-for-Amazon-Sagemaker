#!/usr/bin/env python3
"""
List all data sources and show their full details.
"""

import boto3
import json

def list_data_sources():
    domain_id = "<DOMAIN_ID>"
    project_id = "d8ipo2t2p8oalj"
    region = "us-east-1"
    
    datazone = boto3.client('datazone', region_name=region)
    
    print(f"📋 Listing data sources in project: {project_id}")
    
    # List data sources
    response = datazone.list_data_sources(
        domainIdentifier=domain_id,
        projectIdentifier=project_id
    )
    
    print(f"\n🔍 LIST DATA SOURCES RESPONSE:")
    print(json.dumps(response, indent=2, default=str))
    
    data_sources = response.get('items', [])
    
    for i, ds in enumerate(data_sources, 1):
        ds_id = ds.get('dataSourceId')
        print(f"\n{'='*60}")
        print(f"DATA SOURCE {i}: {ds_id}")
        print(f"{'='*60}")
        
        # Get detailed information
        try:
            detail_response = datazone.get_data_source(
                domainIdentifier=domain_id,
                identifier=ds_id
            )
            
            print(json.dumps(detail_response, indent=2, default=str))
            
        except Exception as e:
            print(f"❌ Error getting details: {e}")

if __name__ == "__main__":
    list_data_sources()

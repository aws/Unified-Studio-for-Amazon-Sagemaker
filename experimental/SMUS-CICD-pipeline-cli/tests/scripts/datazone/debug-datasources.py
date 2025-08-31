#!/usr/bin/env python3
"""
Debug script to see all data sources and their connections.
"""

import boto3

def debug_data_sources():
    domain_id = "dzd_6je2k8b63qse07"
    project_id = "d8ipo2t2p8oalj"
    region = "us-east-1"
    
    datazone = boto3.client('datazone', region_name=region)
    
    print(f"🔍 Debugging data sources in project: {project_id}")
    
    # List data sources
    response = datazone.list_data_sources(
        domainIdentifier=domain_id,
        projectIdentifier=project_id
    )
    
    data_sources = response.get('items', [])
    print(f"📋 Found {len(data_sources)} data sources")
    
    for i, ds in enumerate(data_sources, 1):
        ds_id = ds.get('dataSourceId')
        ds_name = ds.get('name', 'Unknown')
        ds_type = ds.get('type', 'Unknown')
        
        print(f"\n{i}. Data Source: {ds_name}")
        print(f"   ID: {ds_id}")
        print(f"   Type: {ds_type}")
        
        # Get detailed information
        try:
            detail_response = datazone.get_data_source(
                domainIdentifier=domain_id,
                identifier=ds_id
            )
            
            connection_name = detail_response.get('connectionName', 'None')
            environment_id = detail_response.get('environmentId', 'None')
            status = detail_response.get('status', 'Unknown')
            
            print(f"   Connection: {connection_name}")
            print(f"   Environment: {environment_id}")
            print(f"   Status: {status}")
            
            # Show configuration
            config = detail_response.get('configuration', {})
            if config:
                print(f"   Configuration keys: {list(config.keys())}")
                
                glue_config = config.get('glueRunConfiguration', {})
                if glue_config:
                    filters = glue_config.get('relationalFilterConfigurations', [])
                    print(f"   Database filters: {len(filters)}")
                    for filter_config in filters:
                        db_name = filter_config.get('databaseName', 'Unknown')
                        schema_name = filter_config.get('schemaName', 'default')
                        print(f"     - {db_name}.{schema_name}")
            
        except Exception as e:
            print(f"   ❌ Error getting details: {e}")
    
    # Also list project connections
    print(f"\n🔗 Project Connections:")
    try:
        conn_response = datazone.list_project_connections(
            domainIdentifier=domain_id,
            projectIdentifier=project_id
        )
        
        connections = conn_response.get('items', [])
        for conn in connections:
            conn_name = conn.get('name', 'Unknown')
            conn_id = conn.get('connectionId', 'Unknown')
            conn_type = conn.get('type', 'Unknown')
            print(f"   - {conn_name} ({conn_type}) - {conn_id}")
            
    except Exception as e:
        print(f"   ❌ Error listing connections: {e}")


if __name__ == "__main__":
    debug_data_sources()

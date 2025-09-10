#!/usr/bin/env python3
"""
Simple hardcoded test to reproduce DataZone ListConnections access error.
All values are hardcoded - no configuration loading.
"""

import boto3

def test_hardcoded_datazone_call():
    """Test DataZone ListConnections with hardcoded values."""
    
    print("=== Simple DataZone ListConnections Test ===")
    
    # Hardcoded values from our investigation
    region = "us-east-1"
    domain_id = "dzd_6je2k8b63qse07"
    project_id = "aodxxgjzro6k2v"
    
    print(f"Region: {region}")
    print(f"Domain ID: {domain_id}")
    print(f"Project ID: {project_id}")
    
    try:
        # Create DataZone client
        print(f"\nCreating DataZone client for region: {region}")
        datazone_client = boto3.client("datazone", region_name=region)
        
        # Make the call
        print(f"Calling ListConnections...")
        response = datazone_client.list_connections(
            domainIdentifier=domain_id,
            projectIdentifier=project_id
        )
        
        connections = response.get("items", [])
        print(f"✅ SUCCESS: Got {len(connections)} connections")
        
        for i, conn in enumerate(connections[:3]):  # Show first 3
            print(f"  {i+1}. {conn.get('name')} ({conn.get('type')})")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        print(f"Error type: {type(e).__name__}")
        
        # This should reproduce the access error we're seeing in GitHub Actions
        if "AccessDeniedException" in str(e):
            print("🎯 REPRODUCED: This is the same error as GitHub Actions!")
        
        return False
    
    return True

if __name__ == "__main__":
    test_hardcoded_datazone_call()

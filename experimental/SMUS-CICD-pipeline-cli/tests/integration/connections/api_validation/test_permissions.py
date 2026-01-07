#!/usr/bin/env python3

import boto3
import json
import pytest

def test_permissions():
    """Test basic DataZone permissions before attempting connection creation"""
    
    client = boto3.client('datazone', region_name='us-west-2')
    domain_id = "dzd_6je2k8b63qse07"
    env_id = "dsfuumu0am26jr"
    
    print("Testing DataZone permissions...")
    print("=" * 50)
    
    # Test 1: List connections (read permission)
    try:
        response = client.list_connections(
            domainIdentifier=domain_id,
            environmentIdentifier=env_id
        )
        print(f"✅ List connections: SUCCESS - Found {len(response.get('items', []))} connections")
        
        if response.get('items'):
            print("   Existing connections:")
            for conn in response['items'][:3]:  # Show first 3
                print(f"   - {conn['name']} ({conn['type']})")
        
    except Exception as e:
        print(f"❌ List connections: FAILED - {str(e)}")
        pytest.fail(f"List connections failed: {str(e)}")
    
    # Test 2: Try simple S3 connection creation
    print(f"\nTesting S3 connection creation...")
    try:
        response = client.create_connection(
            domainIdentifier=domain_id,
            environmentIdentifier=env_id,
            name="test-s3-permission-check",
            description="Permission test",
            props={
                "s3Properties": {
                    "s3Uri": "s3://test-bucket/data/"
                }
            }
        )
        
        print(f"✅ S3 connection creation: SUCCESS - {response['connectionId']}")
        
        # Clean up
        client.delete_connection(
            domainIdentifier=domain_id,
            identifier=response['connectionId']
        )
        print(f"   Cleaned up successfully")
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ S3 connection creation: FAILED - {error_msg}")
        
        if "AccessDeniedException" in error_msg:
            print("   → Permission issue: User may not be project owner or lack CreateConnection permission")
        elif "ValidationException" in error_msg:
            print("   → Schema issue: Parameters may be incorrect")
        
        pytest.fail(f"S3 connection creation failed: {error_msg}")

if __name__ == "__main__":
    success = test_permissions()
    if success:
        print(f"\n🎉 Permissions verified - ready to test all connection types")
    else:
        print(f"\n💥 Permission issues detected - need to resolve before proceeding")

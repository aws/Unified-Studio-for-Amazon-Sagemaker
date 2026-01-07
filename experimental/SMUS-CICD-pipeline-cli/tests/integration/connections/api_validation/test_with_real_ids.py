#!/usr/bin/env python3

import boto3
import time
import pytest

def test_s3_connection():
    """Test S3 connection creation with real IDs"""
    
    client = boto3.client('datazone', region_name='us-east-1')
    domain_id = "dzd_6je2k8b63qse07"
    env_id = "dsfuumu0am26jr"
    
    print("Testing S3 connection creation...")
    print(f"Domain: {domain_id}")
    print(f"Environment: {env_id}")
    print("=" * 50)
    
    try:
        response = client.create_connection(
            domainIdentifier=domain_id,
            environmentIdentifier=env_id,
            name=f"test-s3-{int(time.time())}",
            description="Test S3 connection",
            props={
                "s3Properties": {
                    "s3Uri": "s3://test-bucket/data/"
                }
            }
        )
        
        connection_id = response['connectionId']
        print(f"✅ S3 connection created: {connection_id}")
        
        # Clean up
        client.delete_connection(
            domainIdentifier=domain_id,
            identifier=connection_id
        )
        print(f"✅ Cleaned up: {connection_id}")
        
    except Exception as e:
        print(f"❌ Failed: {str(e)}")
        assert False, f"S3 connection test failed: {str(e)}"

if __name__ == "__main__":
    success = test_s3_connection()
    if success:
        print("\n🎉 Ready to test all connection types!")
    else:
        print("\n💥 Still have permission/access issues")

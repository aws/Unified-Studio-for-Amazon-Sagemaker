#!/usr/bin/env python3
"""Test script to verify DataZone create_project API call with customer-provided role."""

import boto3
import sys

# Configuration
DOMAIN_ID = "dzd-5b6m4h6c1yfch3"
REGION = "us-east-1"
PROJECT_NAME = "test-api-project"
ROLE_ARN = "arn:aws:iam::198737698272:role/SMUSCICDTestRole"

def main():
    client = boto3.client("datazone", region_name=REGION)
    
    # Get profile ID
    print(f"Getting project profiles for domain {DOMAIN_ID}...")
    response = client.list_project_profiles(domainIdentifier=DOMAIN_ID)
    profiles = response.get("items", [])
    
    if not profiles:
        print("❌ No project profiles found")
        return 1
    
    profile_id = profiles[0]["id"]
    profile_name = profiles[0]["name"]
    print(f"✓ Using profile: {profile_name} ({profile_id})")
    
    # Test 1: Create project WITH customerProvidedRoleConfigs
    print(f"\n=== Test 1: Create project WITH role ===")
    params = {
        "domainIdentifier": DOMAIN_ID,
        "name": PROJECT_NAME,
        "projectProfileId": profile_id,
        "customerProvidedRoleConfigs": [
            {
                "roleArn": ROLE_ARN,
                "roleDesignation": "PROJECT_OWNER"
            }
        ]
    }
    
    print(f"Parameters: {params}")
    
    try:
        response = client.create_project(**params)
        project_id = response["id"]
        print(f"✅ Project created successfully: {project_id}")
        
        # Clean up
        print(f"Deleting test project {project_id}...")
        client.delete_project(domainIdentifier=DOMAIN_ID, identifier=project_id)
        print("✓ Cleanup complete")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    # Test 2: Create project WITHOUT customerProvidedRoleConfigs
    print(f"\n=== Test 2: Create project WITHOUT role ===")
    params2 = {
        "domainIdentifier": DOMAIN_ID,
        "name": PROJECT_NAME + "-no-role",
        "projectProfileId": profile_id,
    }
    
    print(f"Parameters: {params2}")
    
    try:
        response = client.create_project(**params2)
        project_id = response["id"]
        print(f"✅ Project created successfully: {project_id}")
        
        # Clean up
        print(f"Deleting test project {project_id}...")
        client.delete_project(domainIdentifier=DOMAIN_ID, identifier=project_id)
        print("✓ Cleanup complete")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    print("\n✅ All tests passed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())

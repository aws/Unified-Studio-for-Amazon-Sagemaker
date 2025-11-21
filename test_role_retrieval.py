#!/usr/bin/env python3
"""Test script to verify role retrieval from DataZone projects."""

import boto3

def get_project_user_role_arn(project_id: str, domain_id: str, region: str) -> str:
    """Get the user role ARN from project's ToolingLite environment."""
    datazone_client = boto3.client("datazone", region_name=region)
    
    # List environments
    response = datazone_client.list_environments(
        domainIdentifier=domain_id,
        projectIdentifier=project_id
    )
    
    print(f"Found {len(response.get('items', []))} environments")
    
    # Check each environment
    for env in response.get("items", []):
        env_name = env.get("name", "")
        env_id = env.get("id", "")
        print(f"\nEnvironment: {env_name} (ID: {env_id})")
        
        # Look for ToolingLite or tooling environments
        if "tooling" in env_name.lower():
            print(f"  ✓ Found tooling environment: {env_name}")
            
            # Check provisioned resources
            for resource in env.get("provisionedResources", []):
                if resource.get("name") == "userRoleArn":
                    role_arn = resource.get("value")
                    print(f"  ✓ Found userRoleArn: {role_arn}")
                    return role_arn
    
    return None


if __name__ == "__main__":
    # Test with test-marketing project
    domain_id = "dzd-bldfaa58kwf1ev"
    project_id = "bbv3w6k2vk0753"
    region = "us-east-1"
    
    print(f"Testing role retrieval for project {project_id}")
    print(f"Domain: {domain_id}")
    print(f"Region: {region}\n")
    
    role_arn = get_project_user_role_arn(project_id, domain_id, region)
    
    if role_arn:
        print(f"\n✅ SUCCESS: Retrieved role ARN")
        print(f"Role: {role_arn}")
    else:
        print(f"\n❌ FAILED: Could not retrieve role ARN")

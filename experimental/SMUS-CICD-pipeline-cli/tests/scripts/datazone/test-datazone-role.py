#!/usr/bin/env python3
"""
Test script to find the best way to retrieve DataZone project user role.
"""

import boto3
import json

def test_datazone_apis():
    """Test various DataZone APIs to find project user role."""
    
    # Known values from our previous work
    domain_id = "<DOMAIN_ID>"
    project_id = "d8ipo2t2p8oalj"
    region = "us-east-1"
    expected_role = "arn:aws:iam::<ACCOUNT_ID>:role/datazone_usr_role_d8ipo2t2p8oalj_6hufhs8cbb5qjr"
    
    datazone = boto3.client('datazone', region_name=region)
    
    print(f"🔍 Testing DataZone APIs to find project user role")
    print(f"Domain ID: {domain_id}")
    print(f"Project ID: {project_id}")
    print(f"Expected Role: {expected_role}")
    print("=" * 80)
    
    # Test 1: Get Project
    print("\n1️⃣ Testing get_project()...")
    try:
        response = datazone.get_project(
            domainIdentifier=domain_id,
            identifier=project_id
        )
        
        # Look for role-related fields
        found_roles = []
        def find_roles(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    if 'role' in key.lower() and isinstance(value, str):
                        found_roles.append(f"{current_path}: {value}")
                    find_roles(value, current_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    find_roles(item, f"{path}[{i}]")
        
        find_roles(response)
        if found_roles:
            print("✅ Found role-related fields:")
            for role in found_roles:
                print(f"   {role}")
        else:
            print("❌ No role fields found")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: List Environments
    print("\n2️⃣ Testing list_environments()...")
    try:
        response = datazone.list_environments(
            domainIdentifier=domain_id,
            projectIdentifier=project_id
        )
        
        environments = response.get('items', [])
        print(f"📋 Found {len(environments)} environments")
        
        for env in environments:
            env_name = env.get('name', 'Unknown')
            env_id = env.get('id', 'Unknown')
            print(f"   - {env_name} ({env_id})")
            
            # Look for role in environment list item
            found_roles = []
            def find_roles(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key
                        if 'role' in key.lower() and isinstance(value, str):
                            found_roles.append(f"{current_path}: {value}")
                        find_roles(value, current_path)
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        find_roles(item, f"{path}[{i}]")
            
            find_roles(env)
            if found_roles:
                print(f"     ✅ Role fields in list:")
                for role in found_roles:
                    print(f"       {role}")
                    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: Get Environment (tooling)
    print("\n3️⃣ Testing get_environment() for tooling...")
    try:
        # Get tooling environment ID
        envs_response = datazone.list_environments(
            domainIdentifier=domain_id,
            projectIdentifier=project_id
        )
        
        tooling_env_id = None
        for env in envs_response.get('items', []):
            if 'tooling' in env.get('name', '').lower():
                tooling_env_id = env.get('id')
                break
        
        if tooling_env_id:
            print(f"📋 Getting tooling environment: {tooling_env_id}")
            response = datazone.get_environment(
                domainIdentifier=domain_id,
                identifier=tooling_env_id
            )
            
            # Check top-level fields
            print("🔍 Checking top-level fields...")
            top_level_roles = []
            for key, value in response.items():
                if 'role' in key.lower() and isinstance(value, str):
                    top_level_roles.append(f"{key}: {value}")
            
            if top_level_roles:
                print("✅ Top-level role fields:")
                for role in top_level_roles:
                    print(f"   {role}")
            else:
                print("❌ No top-level role fields")
            
            # Check specific nested locations
            locations_to_check = [
                ('deploymentProperties', response.get('deploymentProperties', {})),
                ('provisioningProperties', response.get('provisioningProperties', {})),
                ('userParameters', response.get('userParameters', [])),
                ('environmentActions', response.get('environmentActions', []))
            ]
            
            for location_name, location_data in locations_to_check:
                print(f"🔍 Checking {location_name}...")
                found_roles = []
                
                def find_roles(obj, path=""):
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            current_path = f"{path}.{key}" if path else key
                            if 'role' in key.lower() and isinstance(value, str):
                                found_roles.append(f"{current_path}: {value}")
                            find_roles(value, current_path)
                    elif isinstance(obj, list):
                        for i, item in enumerate(obj):
                            find_roles(item, f"{path}[{i}]")
                
                find_roles(location_data)
                if found_roles:
                    print(f"   ✅ Found in {location_name}:")
                    for role in found_roles:
                        print(f"     {role}")
                else:
                    print(f"   ❌ No roles in {location_name}")
        else:
            print("❌ No tooling environment found")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 4: Get Environment Credentials
    print("\n4️⃣ Testing get_environment_credentials()...")
    try:
        envs_response = datazone.list_environments(
            domainIdentifier=domain_id,
            projectIdentifier=project_id
        )
        
        tooling_env_id = None
        for env in envs_response.get('items', []):
            if 'tooling' in env.get('name', '').lower():
                tooling_env_id = env.get('id')
                break
        
        if tooling_env_id:
            response = datazone.get_environment_credentials(
                domainIdentifier=domain_id,
                environmentIdentifier=tooling_env_id
            )
            
            print("✅ Got environment credentials")
            print(f"📋 Response keys: {list(response.keys())}")
            
            # Look for role info in credentials
            found_roles = []
            def find_roles(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key
                        if 'role' in key.lower() and isinstance(value, str):
                            found_roles.append(f"{current_path}: {value}")
                        find_roles(value, current_path)
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        find_roles(item, f"{path}[{i}]")
            
            find_roles(response)
            if found_roles:
                print("✅ Role fields in credentials:")
                for role in found_roles:
                    print(f"   {role}")
            else:
                print("❌ No role fields in credentials")
                
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 5: List Project Memberships
    print("\n5️⃣ Testing list_project_memberships()...")
    try:
        response = datazone.list_project_memberships(
            domainIdentifier=domain_id,
            projectIdentifier=project_id
        )
        
        members = response.get('members', [])
        print(f"📋 Found {len(members)} project members")
        
        for i, member in enumerate(members):
            print(f"   Member {i+1}:")
            
            found_roles = []
            def find_roles(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key
                        if 'role' in key.lower() and isinstance(value, str):
                            found_roles.append(f"{current_path}: {value}")
                        find_roles(value, current_path)
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        find_roles(item, f"{path}[{i}]")
            
            find_roles(member)
            if found_roles:
                print("     ✅ Role fields:")
                for role in found_roles:
                    print(f"       {role}")
            else:
                print("     ❌ No role fields")
                
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 80)
    print("🎯 Summary: Testing complete!")


if __name__ == "__main__":
    test_datazone_apis()

#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, 'src')

from smus_cicd.helpers.utils import load_config
from smus_cicd.pipeline import PipelineManifest
from smus_cicd.helpers import datazone
import boto3
import json

# Load the test pipeline
manifest = PipelineManifest.from_file('tests/integration/multi_target_pipeline/multi_target_pipeline.yaml')
target_config = manifest.get_target('test')

# Prepare config
config = load_config()
config["domain"] = {
    "name": target_config.domain.name,
    "region": target_config.domain.region,
}
config["region"] = target_config.domain.region

project_name = target_config.project.name
domain_name = target_config.domain.name
region = target_config.domain.region

print(f"=== SEARCHING FOR PROJECT: {project_name} ===")
print(f"Domain: {domain_name}")
print(f"Region: {region}")

try:
    # Get domain ID
    domain_id = datazone.get_domain_id_by_name(domain_name, region)
    print(f"Domain ID: {domain_id}")
    
    if domain_id:
        # Get project ID
        project_id = datazone.get_project_id_by_name(project_name, domain_id, region)
        print(f"Project ID: {project_id}")
        
        if project_id:
            # List environments
            datazone_client = boto3.client("datazone", region_name=region)
            environments_response = datazone_client.list_environments(
                domainIdentifier=domain_id, 
                projectIdentifier=project_id
            )
            
            print(f"\n=== ENVIRONMENTS ({len(environments_response.get('items', []))}) ===")
            for env in environments_response.get('items', []):
                print(f"\nEnvironment: {env.get('name')}")
                print(f"  ID: {env.get('id')}")
                print(f"  Status: {env.get('status')}")
                print(f"  Profile: {env.get('environmentProfileId')}")
                print(f"  Blueprint: {env.get('environmentBlueprintId')}")
                
                # Get detailed environment info
                try:
                    env_detail = datazone_client.get_environment(
                        domainIdentifier=domain_id,
                        identifier=env.get('id')
                    )
                    
                    print(f"  Description: {env_detail.get('description', 'N/A')}")
                    
                    # Check for provisioned resources
                    provisioned_resources = env_detail.get('provisionedResources', [])
                    if provisioned_resources:
                        print(f"  Provisioned Resources ({len(provisioned_resources)}):")
                        for resource in provisioned_resources:
                            print(f"    - {resource.get('name')}: {resource.get('value')}")
                            print(f"      Type: {resource.get('type')}")
                    
                    # Check for user parameters
                    user_params = env_detail.get('userParameters', [])
                    if user_params:
                        print(f"  User Parameters ({len(user_params)}):")
                        for param in user_params:
                            print(f"    - {param.get('name')}: {param.get('value')}")
                    
                except Exception as e:
                    print(f"  Error getting environment details: {e}")
        else:
            print("Project not found")
    else:
        print("Domain not found")
        
except Exception as e:
    print(f"Error: {e}")

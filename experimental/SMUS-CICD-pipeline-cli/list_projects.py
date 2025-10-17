#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, 'src')

from smus_cicd.helpers import datazone
import boto3
import json

domain_name = "cicd-test-domain"
region = "us-east-2"

print(f"=== LISTING PROJECTS IN DOMAIN: {domain_name} ===")

try:
    # Get domain ID
    domain_id = datazone.get_domain_id_by_name(domain_name, region)
    print(f"Domain ID: {domain_id}")
    
    if domain_id:
        # List all projects
        datazone_client = boto3.client("datazone", region_name=region)
        projects_response = datazone_client.list_projects(
            domainIdentifier=domain_id
        )
        
        print(f"\n=== PROJECTS ({len(projects_response.get('items', []))}) ===")
        for project in projects_response.get('items', []):
            print(f"\nProject: {project.get('name')}")
            print(f"  ID: {project.get('id')}")
            print(f"  Status: {project.get('projectStatus')}")
            print(f"  Description: {project.get('description', 'N/A')}")
            
            # List environments for this project
            try:
                environments_response = datazone_client.list_environments(
                    domainIdentifier=domain_id, 
                    projectIdentifier=project.get('id')
                )
                
                print(f"  Environments ({len(environments_response.get('items', []))}):")
                for env in environments_response.get('items', []):
                    print(f"    - {env.get('name')} (Status: {env.get('status')})")
                    
                    # Check if this is a tooling environment
                    if 'tooling' in env.get('name', '').lower():
                        print(f"      *** TOOLING ENVIRONMENT FOUND ***")
                        
                        # Get detailed environment info
                        try:
                            env_detail = datazone_client.get_environment(
                                domainIdentifier=domain_id,
                                identifier=env.get('id')
                            )
                            
                            # Check for provisioned resources
                            provisioned_resources = env_detail.get('provisionedResources', [])
                            if provisioned_resources:
                                print(f"      Provisioned Resources ({len(provisioned_resources)}):")
                                for resource in provisioned_resources:
                                    print(f"        - {resource.get('name')}: {resource.get('value')}")
                                    print(f"          Type: {resource.get('type')}")
                                    
                                    # Look for role ARNs
                                    if 'role' in resource.get('name', '').lower() or 'arn:aws:iam' in str(resource.get('value', '')):
                                        print(f"          *** POTENTIAL USER ROLE: {resource.get('value')} ***")
                        
                        except Exception as e:
                            print(f"      Error getting tooling environment details: {e}")
                            
            except Exception as e:
                print(f"  Error listing environments: {e}")
    else:
        print("Domain not found")
        
except Exception as e:
    print(f"Error: {e}")

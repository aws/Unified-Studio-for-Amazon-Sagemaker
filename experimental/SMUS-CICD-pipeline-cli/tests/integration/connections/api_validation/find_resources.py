#!/usr/bin/env python3

import boto3

def find_datazone_resources():
    """Find available DataZone domains and projects"""
    
    client = boto3.client('datazone', region_name='us-west-2')
    
    print("Finding DataZone resources in current account...")
    print("=" * 60)
    
    # List domains
    try:
        response = client.list_domains()
        domains = response.get('items', [])
        print(f"✅ Found {len(domains)} domains:")
        
        for domain in domains:
            print(f"   - {domain['name']} ({domain['id']})")
            
            # For each domain, try to list projects
            try:
                projects_response = client.list_projects(domainIdentifier=domain['id'])
                projects = projects_response.get('items', [])
                print(f"     └─ {len(projects)} projects:")
                
                for project in projects[:3]:  # Show first 3 projects
                    print(f"        - {project['name']} ({project['id']})")
                    
                    # Try to list environments in first project
                    if projects:
                        try:
                            env_response = client.list_environments(
                                domainIdentifier=domain['id'],
                                projectIdentifier=project['id']
                            )
                            environments = env_response.get('items', [])
                            if environments:
                                print(f"          └─ {len(environments)} environments:")
                                for env in environments[:2]:
                                    print(f"             - {env['name']} ({env['id']})")
                        except Exception as env_e:
                            print(f"          └─ Cannot list environments: {str(env_e)[:50]}...")
                            
            except Exception as proj_e:
                print(f"     └─ Cannot list projects: {str(proj_e)[:50]}...")
            
            print()  # Empty line between domains
            
    except Exception as e:
        print(f"❌ Cannot list domains: {str(e)}")
        return None
    
    return domains

if __name__ == "__main__":
    domains = find_datazone_resources()
    
    if domains:
        print("\n" + "=" * 60)
        print("SUMMARY: Use these IDs for connection testing:")
        for domain in domains[:1]:  # Show first domain details
            print(f"Domain ID: {domain['id']}")
            try:
                projects_response = boto3.client('datazone', region_name='us-west-2').list_projects(
                    domainIdentifier=domain['id']
                )
                if projects_response.get('items'):
                    project = projects_response['items'][0]
                    print(f"Project ID: {project['id']}")
                    
                    # Get first environment
                    try:
                        env_response = boto3.client('datazone', region_name='us-west-2').list_environments(
                            domainIdentifier=domain['id'],
                            projectIdentifier=project['id']
                        )
                        if env_response.get('items'):
                            env = env_response['items'][0]
                            print(f"Environment ID: {env['id']}")
                    except:
                        pass
            except:
                pass

#!/usr/bin/env python3

import boto3
import json

def check_access():
    """Check what DataZone resources we can access"""
    
    client = boto3.client('datazone', region_name='us-west-2')
    
    print("Checking DataZone access...")
    print("=" * 50)
    
    # Check current identity
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"AWS Identity: {identity.get('Arn', 'Unknown')}")
        print(f"Account: {identity.get('Account', 'Unknown')}")
    except Exception as e:
        print(f"❌ Cannot get identity: {e}")
    
    # Try to list domains
    try:
        response = client.list_domains()
        print(f"✅ List domains: SUCCESS - Found {len(response.get('items', []))} domains")
        
        for domain in response.get('items', [])[:3]:
            print(f"   - {domain['name']} ({domain['id']})")
            
    except Exception as e:
        print(f"❌ List domains: FAILED - {str(e)}")
    
    # Try specific domain from conversation
    domain_id = "dzd_6je2k8b63qse07"
    try:
        response = client.get_domain(identifier=domain_id)
        print(f"✅ Get domain {domain_id}: SUCCESS - {response['name']}")
        
    except Exception as e:
        print(f"❌ Get domain {domain_id}: FAILED - {str(e)}")
    
    # Try to list projects in domain
    try:
        response = client.list_projects(domainIdentifier=domain_id)
        print(f"✅ List projects: SUCCESS - Found {len(response.get('items', []))} projects")
        
        for project in response.get('items', [])[:3]:
            print(f"   - {project['name']} ({project['id']})")
            
    except Exception as e:
        print(f"❌ List projects: FAILED - {str(e)}")

if __name__ == "__main__":
    check_access()

#!/usr/bin/env python3
"""Test Admin role group search in DataZone."""

import boto3
import sys

# Configuration
DOMAIN_ID = "dzd-614fzsz5nulxm1"
REGION = "us-east-2"
ADMIN_ROLE_ARN = "arn:aws:iam::198737698272:role/Admin"

def test_group_search():
    """Test searching for Admin role in DataZone group profiles."""
    datazone = boto3.client("datazone", region_name=REGION)
    
    print(f"🔍 Searching for Admin role: {ADMIN_ROLE_ARN}")
    print(f"📍 Domain: {DOMAIN_ID}, Region: {REGION}\n")
    
    next_token = None
    page_num = 0
    total_groups = 0
    found = False
    
    while True:
        page_num += 1
        params = {
            "domainIdentifier": DOMAIN_ID,
            "groupType": "IAM_ROLE_SESSION_GROUP",
        }
        if next_token:
            params["nextToken"] = next_token
        
        response = datazone.search_group_profiles(**params)
        items = response.get("items", [])
        total_groups += len(items)
        
        print(f"📄 Page {page_num}: {len(items)} groups")
        
        for group in items:
            group_id = group.get("id")
            group_name = group.get("groupName")
            role_principal = group.get("rolePrincipalArn")
            
            print(f"  - ID: {group_id}")
            print(f"    groupName: {group_name}")
            print(f"    rolePrincipalArn: {role_principal}")
            
            # Check both fields
            if group_name == ADMIN_ROLE_ARN or role_principal == ADMIN_ROLE_ARN:
                print(f"\n✅ FOUND! Group ID: {group_id}")
                found = True
                break
            print()
        
        if found:
            break
            
        next_token = response.get("nextToken")
        if not next_token:
            break
    
    print(f"\n📊 Summary: Searched {total_groups} groups across {page_num} pages")
    
    if not found:
        print(f"❌ Admin role NOT found")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(test_group_search())

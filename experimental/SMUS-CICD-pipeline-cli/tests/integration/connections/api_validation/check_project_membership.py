#!/usr/bin/env python3

import boto3

def check_project_membership():
    """Check if current user is a member of the DataZone project"""
    
    client = boto3.client('datazone', region_name='us-west-2')
    domain_id = "dzd_6je2k8b63qse07"
    project_id = "5mrkpk3iwpwx0n"
    
    # Get current identity
    sts = boto3.client('sts')
    identity = sts.get_caller_identity()
    current_user_arn = identity['Arn']
    
    print(f"Current user: {current_user_arn}")
    print(f"Checking membership in project: {project_id}")
    print("=" * 60)
    
    try:
        # Get project details
        project_response = client.get_project(
            domainIdentifier=domain_id,
            identifier=project_id
        )
        print(f"✅ Project found: {project_response['name']}")
        
        # List project memberships
        memberships_response = client.list_project_memberships(
            domainIdentifier=domain_id,
            projectIdentifier=project_id
        )
        
        members = memberships_response.get('members', [])
        print(f"✅ Found {len(members)} project members:")
        
        current_user_is_member = False
        
        for member in members:
            member_type = member.get('designation', 'UNKNOWN')
            
            if 'userIdentifier' in member:
                user_id = member['userIdentifier']
                print(f"   - User: {user_id} ({member_type})")
                
                # Check if this matches current user
                if user_id in current_user_arn or current_user_arn.endswith(user_id):
                    current_user_is_member = True
                    print(f"     ✅ MATCH: Current user is a {member_type}")
            
            elif 'groupIdentifier' in member:
                group_id = member['groupIdentifier']
                print(f"   - Group: {group_id} ({member_type})")
        
        if current_user_is_member:
            print(f"\n🎉 Current user IS a member of the project")
            return True
        else:
            print(f"\n❌ Current user is NOT a member of the project")
            print(f"   Need to add {current_user_arn} as a project member")
            return False
            
    except Exception as e:
        print(f"❌ Error checking project membership: {str(e)}")
        return False

if __name__ == "__main__":
    is_member = check_project_membership()
    
    if not is_member:
        print("\n💡 To fix this:")
        print("   1. Go to DataZone console")
        print("   2. Navigate to the project")
        print("   3. Add current user as a project member with appropriate permissions")

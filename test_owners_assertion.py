#!/usr/bin/env python3
"""Test project owners assertion logic."""

import boto3
import yaml
import os

# Read manifest
pipeline_file = "experimental/SMUS-CICD-pipeline-cli/tests/integration/basic_app/manifest.yaml"
with open(pipeline_file, 'r') as f:
    manifest = yaml.safe_load(f)

region = os.environ.get('DEV_DOMAIN_REGION', 'us-east-2')
datazone = boto3.client('datazone', region_name=region)

# Get domain ID - use the first/only domain
domains = datazone.list_domains()
assert domains['items'], "No domains found"
domain_id = domains['items'][0]['id']
print(f"✅ Using domain: {domains['items'][0]['name']} (ID: {domain_id})")

dev_project_name = manifest['stages']['dev']['project']['name']

# Get expected owners from manifest
expected_owners = manifest['stages']['dev']['project'].get('owners', [])
print(f"Expected owners from manifest: {expected_owners}")

if expected_owners:
    # Get project ID
    projects = datazone.list_projects(domainIdentifier=domain_id)
    project_id = next(
        (p['id'] for p in projects['items'] if p['name'] == dev_project_name),
        None
    )
    
    assert project_id, f"Project {dev_project_name} not found"
    print(f"✅ Found project: {dev_project_name} (ID: {project_id})")
    
    # Get actual owners
    members = datazone.list_project_memberships(
        domainIdentifier=domain_id,
        projectIdentifier=project_id
    )
    
    # Extract group IDs for owners
    owner_group_ids = [
        m['memberDetails']['group']['groupId']
        for m in members.get('members', [])
        if m.get('designation') == 'PROJECT_OWNER' and 'group' in m.get('memberDetails', {})
    ]
    
    print(f"Owner group IDs: {owner_group_ids}")
    
    # Map group IDs to ARNs/usernames
    actual_owners = []
    for group_id in owner_group_ids:
        try:
            profile = datazone.get_group_profile(
                domainIdentifier=domain_id,
                groupIdentifier=group_id
            )
            # Get role ARN if it's a role-based group, otherwise use group name
            owner_id = profile.get('rolePrincipalArn') or profile.get('groupName') or profile.get('id')
            actual_owners.append(owner_id)
            print(f"  Group {group_id}: {owner_id}")
        except Exception as e:
            print(f"  Could not get profile for {group_id}: {e}")
            actual_owners.append(group_id)
    
    print(f"Actual owners in project: {actual_owners}")
    
    # Expand ${AWS_ACCOUNT_ID} in expected owners
    import boto3
    sts = boto3.client('sts')
    account_id = sts.get_caller_identity()['Account']
    
    expanded_expected_owners = []
    for owner in expected_owners:
        expanded = owner.replace('${AWS_ACCOUNT_ID}', account_id)
        expanded_expected_owners.append(expanded)
    
    print(f"Expected owners (expanded): {expanded_expected_owners}")
    
    # Verify each expected owner is present (skip non-ARN owners like "Eng1")
    for owner in expanded_expected_owners:
        if owner.startswith('arn:'):
            assert owner in actual_owners, f"Owner {owner} not found in project"
            print(f"✅ Verified owner: {owner}")
        else:
            print(f"⏭️  Skipping non-ARN owner: {owner}")
    
    print(f"\n✅ All ARN-based owners verified successfully")
else:
    print("No owners specified in manifest")

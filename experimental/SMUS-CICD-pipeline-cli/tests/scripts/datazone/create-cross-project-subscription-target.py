#!/usr/bin/env python3
"""
Standalone script to create cross-project subscription targets and grants.

This script implements the logic for:
1. Finding subscription targets in both dev and target projects
2. Creating new subscription target in dev project with target's config
3. Creating subscription grants for all dev project subscriptions
"""

import boto3
import json

def get_subscription_targets(domain_id, project_id, region):
    """Get all subscription targets for a project across all environments."""
    datazone = boto3.client('datazone', region_name=region)
    
    # First get all environments for the project
    envs_response = datazone.list_environments(
        domainIdentifier=domain_id,
        projectIdentifier=project_id
    )
    
    all_targets = []
    
    for env in envs_response.get('items', []):
        env_id = env.get('id')
        env_name = env.get('name')
        
        try:
            targets_response = datazone.list_subscription_targets(
                domainIdentifier=domain_id,
                environmentIdentifier=env_id
            )
            
            targets = targets_response.get('items', [])
            for target in targets:
                target['environmentName'] = env_name
                all_targets.append(target)
                
        except Exception as e:
            print(f"⚠️ Error getting targets for env {env_name}: {e}")
    
    return all_targets

def find_glue_targets(targets):
    """Find subscription targets that support GlueTableAssetType."""
    glue_targets = []
    
    for target in targets:
        applicable_types = target.get('applicableAssetTypes', [])
        if 'GlueTableAssetType' in applicable_types:
            glue_targets.append(target)
    
    return glue_targets

def create_subscription_target(domain_id, dev_env_id, target_config, dev_manage_role, target_manage_role, region):
    """Create new subscription target in dev environment."""
    datazone = boto3.client('datazone', region_name=region)
    
    try:
        # Note: Using dev_manage_role for both due to DataZone limitation
        # Target role cannot be reused across projects
        response = datazone.create_subscription_target(
            domainIdentifier=domain_id,
            environmentIdentifier=dev_env_id,
            name=f"cross-project-glue-target",
            type='GlueSubscriptionTargetType',
            applicableAssetTypes=['GlueTableAssetType', 'GlueViewAssetType'],
            authorizedPrincipals=[dev_manage_role],  # Using dev role due to DataZone constraint
            manageAccessRole=dev_manage_role,  # Use dev project's role
            provider='Amazon SageMaker',
            subscriptionTargetConfig=target_config
        )
        
        return response.get('id')
        
    except Exception as e:
        print(f"❌ Error creating subscription target: {e}")
        return None

def get_project_subscriptions(domain_id, project_id, region):
    """Get all approved subscriptions for a project."""
    datazone = boto3.client('datazone', region_name=region)
    
    try:
        response = datazone.list_subscriptions(
            domainIdentifier=domain_id,
            owningProjectId=project_id,  # Correct parameter name
            status='APPROVED'
        )
        
        return response.get('items', [])
        
    except Exception as e:
        print(f"❌ Error getting subscriptions: {e}")
        return []

def create_subscription_grant(domain_id, subscription, target_id, dev_env_id, region):
    """Create subscription grant for a subscription using new target."""
    datazone = boto3.client('datazone', region_name=region)
    
    try:
        # Extract listing information from subscription
        subscribed_listing = subscription.get('subscribedListing', {})
        listing_id = subscribed_listing.get('id')
        listing_revision = subscribed_listing.get('revision', '1')
        
        response = datazone.create_subscription_grant(
            domainIdentifier=domain_id,
            environmentIdentifier=dev_env_id,
            grantedEntity={
                'listing': {
                    'identifier': listing_id,
                    'revision': listing_revision
                }
            },
            subscriptionTargetIdentifier=target_id
        )
        
        return response.get('id')
        
    except Exception as e:
        print(f"❌ Error creating subscription grant: {e}")
        return None

def main():
    # Configuration
    domain_id = "<DOMAIN_ID>"
    dev_project_id = "aodxxgjzro6k2v"  # dev-marketing
    target_project_id = "5oq8m1d1qn1lev"  # integration-test-test
    region = "us-east-1"
    
    print(f"🔍 Starting cross-project subscription target creation...")
    print(f"Dev project: {dev_project_id}")
    print(f"Target project: {target_project_id}")
    
    # 1. Get subscription targets from both projects
    print(f"\n📋 Getting subscription targets...")
    
    dev_targets = get_subscription_targets(domain_id, dev_project_id, region)
    target_targets = get_subscription_targets(domain_id, target_project_id, region)
    
    print(f"Dev project targets: {len(dev_targets)}")
    print(f"Target project targets: {len(target_targets)}")
    
    # 2. Find Glue targets in both projects
    dev_glue_targets = find_glue_targets(dev_targets)
    target_glue_targets = find_glue_targets(target_targets)
    
    print(f"\nDev Glue targets: {len(dev_glue_targets)}")
    for target in dev_glue_targets:
        print(f"  - {target['name']} (env: {target['environmentName']})")
    
    print(f"\nTarget Glue targets: {len(target_glue_targets)}")
    for target in target_glue_targets:
        print(f"  - {target['name']} (env: {target['environmentName']})")
    
    if not dev_glue_targets:
        print("❌ No Glue targets found in dev project")
        return
    
    if not target_glue_targets:
        print("❌ No Glue targets found in target project")
        return
    
    # 3. Use first dev Glue target environment and first target Glue target config
    dev_target = dev_glue_targets[0]
    target_target = target_glue_targets[0]
    
    dev_env_id = dev_target['environmentId']
    dev_manage_role = dev_target.get('manageAccessRole')  # Use dev project's role for manageAccessRole
    target_manage_role = target_target.get('manageAccessRole')  # Use target project's role for authorizedPrincipals
    target_config = target_target.get('subscriptionTargetConfig', [])
    
    print(f"\n🔧 Creating new subscription target...")
    print(f"Dev environment: {dev_env_id}")
    print(f"Dev manage role (for manageAccessRole): {dev_manage_role}")
    print(f"Target manage role (for authorizedPrincipals): {target_manage_role}")
    print(f"Target config: {json.dumps(target_config, indent=2)}")
    
    # 4. Create new subscription target in dev environment
    new_target_id = create_subscription_target(
        domain_id, 
        dev_env_id, 
        target_config, 
        dev_manage_role,  # manageAccessRole
        target_manage_role,  # authorizedPrincipals
        region
    )
    
    if not new_target_id:
        print("❌ Failed to create subscription target")
        return
    
    print(f"✅ Created subscription target: {new_target_id}")
    
    # 5. Get all dev project subscriptions
    print(f"\n📋 Getting dev project subscriptions...")
    subscriptions = get_project_subscriptions(domain_id, dev_project_id, region)
    
    print(f"Found {len(subscriptions)} approved subscriptions")
    for sub in subscriptions:
        listing_name = sub.get('subscribedListing', {}).get('name', 'Unknown')
        print(f"  - {listing_name} (ID: {sub['id']})")
    
    # 6. Create subscription grants for all subscriptions
    if subscriptions:
        print(f"\n🎯 Creating subscription grants...")
        
        grant_count = 0
        for subscription in subscriptions:
            sub_id = subscription['id']
            listing_name = subscription.get('subscribedListing', {}).get('name', 'Unknown')
            
            grant_id = create_subscription_grant(domain_id, subscription, new_target_id, dev_env_id, region)
            
            if grant_id:
                print(f"  ✅ Created grant for {listing_name}: {grant_id}")
                grant_count += 1
            else:
                print(f"  ❌ Failed to create grant for {listing_name}")
        
        print(f"\n🎉 Successfully created {grant_count} subscription grants")
    else:
        print(f"\n📋 No subscriptions found - no grants to create")
    
    print(f"\n✅ Cross-project subscription target creation complete!")

if __name__ == "__main__":
    main()

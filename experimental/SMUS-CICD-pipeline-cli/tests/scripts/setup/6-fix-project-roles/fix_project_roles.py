#!/usr/bin/env python3
"""
Fix IAM roles for all DataZone projects in a domain.

This script:
1. Lists all projects in a DataZone domain
2. Gets the IAM role for each project
3. Updates trust policies to include:
   - airflow-serverless.amazonaws.com
   - airflow-serverless-gamma.amazonaws.com
   - athena.aws.internal
   - athena.amazonaws.com

Usage:
    python fix_project_roles.py --domain-id <domain-id> --region <region>
"""

import argparse
import boto3
import json
import sys
import os


def get_all_projects(domain_id, region):
    """Get all projects in a domain."""
    endpoint_url = os.environ.get('AWS_ENDPOINT_URL_DATAZONE')
    datazone = boto3.client('datazone', region_name=region, endpoint_url=endpoint_url)
    projects = []
    
    try:
        paginator = datazone.get_paginator('list_projects')
        for page in paginator.paginate(domainIdentifier=domain_id):
            projects.extend(page.get('items', []))
        
        print(f"✅ Found {len(projects)} projects in domain {domain_id}")
        return projects
    except Exception as e:
        print(f"❌ Error listing projects: {e}")
        return []


def get_project_role_arn(project_id, domain_id, region):
    """Get the IAM role ARN for a project."""
    endpoint_url = os.environ.get('AWS_ENDPOINT_URL_DATAZONE')
    datazone = boto3.client('datazone', region_name=region, endpoint_url=endpoint_url)
    
    try:
        # List environments for the project
        env_response = datazone.list_environments(
            domainIdentifier=domain_id,
            projectIdentifier=project_id
        )
        
        # Look for userRoleArn in provisioned resources
        for env in env_response.get('items', []):
            for resource in env.get('provisionedResources', []):
                if resource.get('name') == 'userRoleArn':
                    return resource.get('value')
        
        return None
    except Exception as e:
        print(f"  ⚠️  Could not get role for project {project_id}: {e}")
        return None


def fix_role_trust_policy(role_arn, region):
    """Fix IAM role trust policy to include required service principals."""
    if not role_arn:
        return False
    
    iam = boto3.client('iam', region_name=region)
    role_name = role_arn.split('/')[-1]
    
    try:
        # Get current trust policy
        response = iam.get_role(RoleName=role_name)
        current_policy = response['Role']['AssumeRolePolicyDocument']
        
        # Required service principals
        required_principals = [
            'airflow-serverless.amazonaws.com',
            'airflow-serverless-gamma.amazonaws.com',
            'athena.aws.internal',
            'athena.amazonaws.com'
        ]
        
        # Check if all principals are present
        has_all = False
        for statement in current_policy.get('Statement', []):
            principal = statement.get('Principal', {})
            if isinstance(principal, dict) and 'Service' in principal:
                services = principal['Service']
                if isinstance(services, str):
                    services = [services]
                if all(svc in services for svc in required_principals):
                    has_all = True
                    break
        
        if has_all:
            print(f"  ✓ Role {role_name} already has all required principals")
            return True
        
        # Add missing principals
        updated = False
        for statement in current_policy.get('Statement', []):
            principal = statement.get('Principal', {})
            if isinstance(principal, dict) and 'Service' in principal:
                services = principal['Service']
                if isinstance(services, str):
                    services = [services]
                
                for req_principal in required_principals:
                    if req_principal not in services:
                        services.append(req_principal)
                        updated = True
                
                statement['Principal']['Service'] = services
        
        if not updated:
            print(f"  ⚠️  Could not update role {role_name}")
            return False
        
        # Update trust policy
        iam.update_assume_role_policy(
            RoleName=role_name,
            PolicyDocument=json.dumps(current_policy)
        )
        
        print(f"  ✅ Updated trust policy for {role_name}")
        return True
        
    except Exception as e:
        print(f"  ❌ Error updating role {role_name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Fix IAM roles for DataZone projects')
    parser.add_argument('--domain-id', required=True, help='DataZone domain ID')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    print(f"\n🔧 Fixing project roles in domain {args.domain_id}")
    print(f"   Region: {args.region}")
    if args.dry_run:
        print("   Mode: DRY RUN (no changes will be made)")
    print()
    
    # Get all projects
    projects = get_all_projects(args.domain_id, args.region)
    if not projects:
        print("❌ No projects found")
        return 1
    
    # Fix each project's role
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for project in projects:
        project_id = project.get('id')
        project_name = project.get('name', 'Unknown')
        
        print(f"\n📋 Project: {project_name} ({project_id})")
        
        # Get role ARN
        role_arn = get_project_role_arn(project_id, args.domain_id, args.region)
        if not role_arn:
            print(f"  ⚠️  No role found, skipping")
            skip_count += 1
            continue
        
        print(f"  Role: {role_arn}")
        
        if args.dry_run:
            print(f"  [DRY RUN] Would update trust policy")
            success_count += 1
            continue
        
        # Fix trust policy
        if fix_role_trust_policy(role_arn, args.region):
            success_count += 1
        else:
            fail_count += 1
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Total projects: {len(projects)}")
    print(f"  ✅ Successfully updated: {success_count}")
    print(f"  ⚠️  Skipped: {skip_count}")
    print(f"  ❌ Failed: {fail_count}")
    print(f"{'='*60}\n")
    
    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

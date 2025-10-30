#!/usr/bin/env python3
"""Add Overdrive/Airflow Serverless permissions to CICD test roles."""

import argparse
import boto3
import json
import sys


def add_overdrive_policy(role_name, region):
    """Add inline policy with Overdrive permissions."""
    iam = boto3.client('iam', region_name=region)
    
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "airflow:*",
                    "overdrive:*"
                ],
                "Resource": "*"
            }
        ]
    }
    
    policy_name = "OverdriveAccess"
    
    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        print(f"✅ Added {policy_name} policy to {role_name}")
    except Exception as e:
        print(f"❌ Error adding policy: {e}")
        return False
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Add Overdrive permissions to CICD roles')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    
    args = parser.parse_args()
    
    print(f"\n🔧 Adding Overdrive permissions to CICD roles")
    print(f"   Region: {args.region}\n")
    
    roles = ['SMUSCICDTestRole', 'SMUSCICDProdRole']
    
    for role_name in roles:
        if add_overdrive_policy(role_name, args.region):
            print(f"✓ {role_name} updated\n")
        else:
            print(f"✗ Failed to update {role_name}\n")
            return 1
    
    print("✅ All roles updated successfully")
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""
Create IAM roles for test and prod stages.

This script creates IAM roles with the necessary trust policies and permissions
for SageMaker Unified Studio projects.
"""

import argparse
import boto3
import json
import sys


def create_role(role_name, account_id, region):
    """Create IAM role with trust policy and attach managed policy."""
    iam = boto3.client('iam', region_name=region)
    
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": [
                        "loadtest.llaps.looseleaf.im.aws.internal",
                        "devo.workflows.looseleaf.im.aws.internal",
                        "datazone.amazonaws.com",
                        "auth.datazone.amazonaws.com",
                        "glue-gamma.amazonaws.com",
                        "airflow-serverless.amazonaws.com",
                        "glue.gamma.amazonaws.com",
                        "airflow-serverless-gamma.amazonaws.com",
                        "devo.llaps.looseleaf.im.aws.internal",
                        "sagemaker.amazonaws.com",
                        "scheduler.amazonaws.com",
                        "athena.aws.internal",
                        "athena.amazonaws.com",
                        "bedrock.amazonaws.com",
                        "datazone.aws.internal",
                        "lakeformation.amazonaws.com",
                        "loadtest.workflows.looseleaf.im.aws.internal",
                        "glue.amazonaws.com",
                        "emr-serverless.amazonaws.com",
                        "lambda.amazonaws.com",
                        "quicksight.amazonaws.com",
                        "redshift.amazonaws.com",
                        "redshift-serverless.amazonaws.com",
                        "access-grants.s3.amazonaws.com"
                    ]
                },
                "Action": [
                    "sts:AssumeRole",
                    "sts:TagSession",
                    "sts:SetContext",
                    "sts:SetSourceIdentity"
                ],
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": account_id
                    }
                }
            }
        ]
    }
    
    try:
        # Try to create the role
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description=f'IAM role for SageMaker Unified Studio CICD testing',
            Tags=[
                {'Key': 'Purpose', 'Value': 'smus-cicd-testing'},
                {'Key': 'ManagedBy', 'Value': 'smus-cicd-cli'}
            ]
        )
        print(f"✅ Created role: {role_name}")
        role_arn = response['Role']['Arn']
    except iam.exceptions.EntityAlreadyExistsException:
        print(f"✓ Role {role_name} already exists")
        response = iam.get_role(RoleName=role_name)
        role_arn = response['Role']['Arn']
        
        # Update trust policy
        iam.update_assume_role_policy(
            RoleName=role_name,
            PolicyDocument=json.dumps(trust_policy)
        )
        print(f"✅ Updated trust policy for {role_name}")
    
    # Attach managed policies
    policies = [
        'arn:aws:iam::aws:policy/AdministratorAccess',
        'arn:aws:iam::aws:policy/SageMakerStudioUserIAMPermissiveExecutionPolicy'
    ]
    
    for policy_arn in policies:
        try:
            iam.attach_role_policy(
                RoleName=role_name,
                PolicyArn=policy_arn
            )
            print(f"✅ Attached {policy_arn.split('/')[-1]} to {role_name}")
        except iam.exceptions.NoSuchEntityException:
            print(f"⚠️  Policy {policy_arn} not found")
        except Exception as e:
            if 'already attached' in str(e).lower():
                print(f"✓ {policy_arn.split('/')[-1]} already attached to {role_name}")
            else:
                print(f"⚠️  Error attaching policy: {e}")
    
    # Add inline policy for Overdrive/Airflow Serverless permissions
    overdrive_policy = {
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
    
    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName='OverdriveAccess',
            PolicyDocument=json.dumps(overdrive_policy)
        )
        print(f"✅ Added OverdriveAccess inline policy to {role_name}")
    except Exception as e:
        print(f"⚠️  Error adding inline policy: {e}")
    
    return role_arn


def main():
    parser = argparse.ArgumentParser(description='Create IAM roles for CICD testing')
    parser.add_argument('--account-id', required=True, help='AWS account ID')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    
    args = parser.parse_args()
    
    print(f"\n🔧 Creating IAM roles for CICD testing")
    print(f"   Account: {args.account_id}")
    print(f"   Region: {args.region}\n")
    
    # Create roles for test and prod stages
    test_role_name = 'SMUSCICDTestRole'
    prod_role_name = 'SMUSCICDProdRole'
    
    test_role_arn = create_role(test_role_name, args.account_id, args.region)
    prod_role_arn = create_role(prod_role_name, args.account_id, args.region)
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Test Role ARN: {test_role_arn}")
    print(f"  Prod Role ARN: {prod_role_arn}")
    print(f"{'='*60}\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

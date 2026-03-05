"""
Trust Policy Updater Lambda Function

Runs in Org Admin account to update OrganizationAccountAccessRole trust policy
in newly created accounts to allow Domain account access.

This Lambda is invoked by Pool Manager after account creation.
"""

import json
import boto3
from botocore.exceptions import ClientError

sts = boto3.client('sts')


def lambda_handler(event, context):
    """
    Update trust policy for OrganizationAccountAccessRole in target account
    
    Event format:
    {
        "accountId": "123456789012",
        "domainAccountId": "987654321098"
    }
    """
    print(f"📥 Received event: {json.dumps(event, indent=2)}")
    
    account_id = event.get('accountId')
    domain_account_id = event.get('domainAccountId')
    
    if not account_id or not domain_account_id:
        return {
            'statusCode': 400,
            'body': 'Missing accountId or domainAccountId'
        }
    
    try:
        # Assume OrganizationAccountAccessRole in the new account
        role_arn = f"arn:aws:iam::{account_id}:role/OrganizationAccountAccessRole"
        
        print(f"🔐 Assuming role: {role_arn}")
        
        assumed_role = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName='TrustPolicyUpdater'
        )
        
        credentials = assumed_role['Credentials']
        
        # Create IAM client with assumed role credentials
        iam_client = boto3.client(
            'iam',
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )
        
        # Get current trust policy
        role_name = 'OrganizationAccountAccessRole'
        current_policy = iam_client.get_role(RoleName=role_name)['Role']['AssumeRolePolicyDocument']
        
        print(f"📋 Current trust policy: {json.dumps(current_policy, indent=2)}")
        
        # Build new trust policy that includes both Org Admin and Domain accounts
        new_policy = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Allow',
                    'Principal': {
                        'AWS': f"arn:aws:iam::{account_id}:root"
                    },
                    'Action': 'sts:AssumeRole'
                },
                {
                    'Effect': 'Allow',
                    'Principal': {
                        'AWS': f"arn:aws:iam::{domain_account_id}:root"
                    },
                    'Action': 'sts:AssumeRole'
                }
            ]
        }
        
        # Update trust policy
        iam_client.update_assume_role_policy(
            RoleName=role_name,
            PolicyDocument=json.dumps(new_policy)
        )
        
        print(f"✅ Trust policy updated for account {account_id}")
        print(f"   Added Domain account {domain_account_id} to trust policy")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Trust policy updated successfully',
                'accountId': account_id,
                'domainAccountId': domain_account_id
            })
        }
        
    except Exception as e:
        print(f"❌ Failed to update trust policy: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'accountId': account_id
            })
        }

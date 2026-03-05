#!/usr/bin/env python3
"""
Test script for ProvisionAccount Lambda

Tests the account provisioning flow with a single test account.
"""

import json
import boto3
import uuid
from datetime import datetime

# Initialize clients
lambda_client = boto3.client('lambda', region_name='us-east-2')

# Configuration
ORG_ADMIN_ACCOUNT_ID = '495869084367'
DOMAIN_ACCOUNT_ID = '994753223772'
DOMAIN_ID = 'dzd-5o0lje5xgpeuw9'
TARGET_OU_ID = 'ou-n5om-otvkrtx2'  # CustomerAnalytics OU
PROVISION_LAMBDA_ARN = f'arn:aws:lambda:us-east-2:{ORG_ADMIN_ACCOUNT_ID}:function:ProvisionAccount'

def test_provision_account():
    """Test account provisioning with a single account"""
    
    # Generate NEW unique account for end-to-end test
    unique_id = str(uuid.uuid4()).replace('-', '')[:12]
    account_name = f"smus-test-{unique_id}"
    account_email = f"amirbo+pool-test+{unique_id}@amazon.com"
    
    print("🧪 Testing with NEW account for end-to-end provisioning")
    
    print("=" * 80)
    print("Testing ProvisionAccount Lambda")
    print("=" * 80)
    print(f"Account Name: {account_name}")
    print(f"Account Email: {account_email}")
    print(f"Target OU: {TARGET_OU_ID}")
    print(f"Lambda ARN: {PROVISION_LAMBDA_ARN}")
    print("=" * 80)
    
    # Create payload
    payload = {
        'action': 'provision',
        'accountName': account_name,
        'accountEmail': account_email,
        'ouId': TARGET_OU_ID,
        'domainId': DOMAIN_ID,
        'domainAccountId': DOMAIN_ACCOUNT_ID,
        'orgAdminAccountId': ORG_ADMIN_ACCOUNT_ID
    }
    
    print("\nPayload:")
    print(json.dumps(payload, indent=2))
    print("\n" + "=" * 80)
    print("Invoking Lambda...")
    print("=" * 80)
    
    try:
        # Invoke Lambda
        response = lambda_client.invoke(
            FunctionName=PROVISION_LAMBDA_ARN,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        # Parse response
        response_payload = json.loads(response['Payload'].read())
        
        print("\nResponse:")
        print(json.dumps(response_payload, indent=2))
        print("\n" + "=" * 80)
        
        if response_payload.get('status') == 'SUCCESS':
            account_id = response_payload.get('accountId')
            print(f"✅ SUCCESS: Account provisioned: {account_id}")
            print(f"   Name: {account_name}")
            print(f"   Email: {account_email}")
            return account_id
        else:
            error_msg = response_payload.get('message', 'Unknown error')
            print(f"❌ FAILED: {error_msg}")
            return None
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    account_id = test_provision_account()
    
    if account_id:
        print("\n" + "=" * 80)
        print("Next Steps:")
        print("=" * 80)
        print(f"1. Verify account in AWS Console: https://console.aws.amazon.com/organizations/v2/home/accounts/{account_id}")
        print(f"2. Check StackSet instances: https://console.aws.amazon.com/cloudformation/home?region=us-east-2#/stacksets")
        print(f"3. Test role assumption:")
        print(f"   aws sts assume-role --role-arn arn:aws:iam::{account_id}:role/AccountPoolFactory-DomainAccess --role-session-name test --external-id {DOMAIN_ID}")

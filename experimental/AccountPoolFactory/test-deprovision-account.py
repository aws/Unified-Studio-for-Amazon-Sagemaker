#!/usr/bin/env python3
"""
Test script for DeprovisionAccount Lambda

Tests the account cleanup flow with a test account.
"""

import json
import boto3
import sys

# Initialize clients
lambda_client = boto3.client('lambda', region_name='us-east-2')

# Configuration
DOMAIN_ACCOUNT_ID = '994753223772'
DOMAIN_ID = 'dzd-5o0lje5xgpeuw9'
DEPROVISION_LAMBDA_ARN = f'arn:aws:lambda:us-east-2:{DOMAIN_ACCOUNT_ID}:function:DeprovisionAccount'

def test_deprovision_account(account_id: str):
    """Test account deprovisioning"""
    
    print("=" * 80)
    print("Testing DeprovisionAccount Lambda")
    print("=" * 80)
    print(f"Account ID: {account_id}")
    print(f"Domain ID: {DOMAIN_ID}")
    print(f"Lambda ARN: {DEPROVISION_LAMBDA_ARN}")
    print("=" * 80)
    
    # Create payload
    payload = {
        'accountId': account_id,
        'domainId': DOMAIN_ID,
        'requestId': f'test-{account_id}'
    }
    
    print("\nPayload:")
    print(json.dumps(payload, indent=2))
    print("\n" + "=" * 80)
    print("Invoking Lambda...")
    print("=" * 80)
    
    try:
        # Invoke Lambda
        response = lambda_client.invoke(
            FunctionName=DEPROVISION_LAMBDA_ARN,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        # Parse response
        response_payload = json.loads(response['Payload'].read())
        
        print("\nResponse:")
        print(json.dumps(response_payload, indent=2))
        print("\n" + "=" * 80)
        
        if response_payload.get('status') == 'SUCCESS':
            stacks_deleted = response_payload.get('stacksDeleted', 0)
            print(f"✅ SUCCESS: Account cleaned")
            print(f"   Account ID: {account_id}")
            print(f"   Stacks Deleted: {stacks_deleted}")
            return True
        elif response_payload.get('status') == 'FAILED':
            failed_stack = response_payload.get('failedStack', 'Unknown')
            error_msg = response_payload.get('errorMessage', 'Unknown error')
            print(f"❌ FAILED: Cleanup failed")
            print(f"   Failed Stack: {failed_stack}")
            print(f"   Error: {error_msg}")
            return False
        else:
            error_msg = response_payload.get('message', 'Unknown error')
            print(f"❌ ERROR: {error_msg}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 test-deprovision-account.py <account-id>")
        print("\nExample:")
        print("  python3 test-deprovision-account.py 977916685855")
        sys.exit(1)
    
    account_id = sys.argv[1]
    success = test_deprovision_account(account_id)
    
    if success:
        print("\n" + "=" * 80)
        print("Next Steps:")
        print("=" * 80)
        print(f"1. Verify account state in DynamoDB:")
        print(f"   aws dynamodb query --table-name AccountPoolFactory-Accounts \\")
        print(f"     --key-condition-expression 'accountId = :id' \\")
        print(f"     --expression-attribute-values '{{\":id\":{{\"S\":\"{account_id}\"}}}}'")
        print(f"\n2. Verify no project stacks remain:")
        print(f"   aws cloudformation list-stacks --profile <project-account-profile>")
        print(f"\n3. Verify approved stacks still exist:")
        print(f"   aws cloudformation describe-stacks \\")
        print(f"     --stack-name AccountPoolFactory-StackSetExecutionRole \\")
        print(f"     --profile <project-account-profile>")
        
        sys.exit(0)
    else:
        sys.exit(1)

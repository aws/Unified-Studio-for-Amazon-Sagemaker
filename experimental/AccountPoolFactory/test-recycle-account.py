#!/usr/bin/env python3
"""
Test script for account recycling (REUSE strategy)

Tests the complete account recycling flow:
1. Find an ASSIGNED account in the pool
2. Simulate project deletion (mark as ready for reclaim)
3. Trigger PoolManager to reclaim the account
4. Verify DeprovisionAccount is invoked
5. Monitor cleanup progress
6. Verify account returns to AVAILABLE state

Usage:
    python3 test-recycle-account.py [account_id]
    
    If account_id is not provided, will find an ASSIGNED account automatically
"""

import boto3
import json
import time
import sys
from datetime import datetime

# Configuration
REGION = 'us-east-2'
DOMAIN_ACCOUNT_ID = '994753223772'
DOMAIN_ID = 'dzd_6aqvvvvvvvvvv'
TABLE_NAME = 'AccountPoolFactory-AccountState'

# Initialize clients
dynamodb = boto3.client('dynamodb', region_name=REGION)
lambda_client = boto3.client('lambda', region_name=REGION)
sts = boto3.client('sts', region_name=REGION)


def print_section(title):
    """Print section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def find_assigned_account():
    """Find an ASSIGNED account in the pool"""
    print("🔍 Searching for ASSIGNED account...")
    
    response = dynamodb.query(
        TableName=TABLE_NAME,
        IndexName='StateIndex',
        KeyConditionExpression='#state = :state',
        ExpressionAttributeNames={'#state': 'state'},
        ExpressionAttributeValues={':state': {'S': 'ASSIGNED'}},
        Limit=1
    )
    
    if not response.get('Items'):
        print("❌ No ASSIGNED accounts found in pool")
        return None
    
    item = response['Items'][0]
    account_id = item['accountId']['S']
    account_name = item.get('accountName', {}).get('S', 'Unknown')
    assigned_date = item.get('assignedDate', {}).get('S', 'Unknown')
    project_stack = item.get('projectStackName', {}).get('S', 'Unknown')
    
    print(f"✅ Found ASSIGNED account:")
    print(f"   Account ID: {account_id}")
    print(f"   Account Name: {account_name}")
    print(f"   Assigned Date: {assigned_date}")
    print(f"   Project Stack: {project_stack}")
    
    return account_id


def get_account_state(account_id):
    """Get current account state from DynamoDB"""
    response = dynamodb.query(
        TableName=TABLE_NAME,
        KeyConditionExpression='accountId = :accountId',
        ExpressionAttributeValues={':accountId': {'S': account_id}},
        ScanIndexForward=False,
        Limit=1
    )
    
    if not response.get('Items'):
        return None
    
    item = response['Items'][0]
    return {
        'accountId': item['accountId']['S'],
        'state': item.get('state', {}).get('S', 'Unknown'),
        'timestamp': item['timestamp']['N'],
        'accountName': item.get('accountName', {}).get('S', 'Unknown'),
        'assignedDate': item.get('assignedDate', {}).get('S'),
        'cleanupStartDate': item.get('cleanupStartDate', {}).get('S'),
        'cleanupCompletedDate': item.get('cleanupCompletedDate', {}).get('S'),
        'failedStep': item.get('failedStep', {}).get('S'),
        'failedStack': item.get('failedStack', {}).get('S'),
        'errorMessage': item.get('errorMessage', {}).get('S'),
    }


def list_stacks_in_account(account_id):
    """List CloudFormation stacks in the account"""
    print(f"📋 Listing stacks in account {account_id}...")
    
    try:
        # Assume role in project account
        role_arn = f"arn:aws:iam::{account_id}:role/AccountPoolFactory-DomainAccess"
        
        assumed_role = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName='TestRecycleAccount',
            ExternalId=DOMAIN_ID
        )
        
        credentials = assumed_role['Credentials']
        cf_client = boto3.client(
            'cloudformation',
            region_name=REGION,
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )
        
        # List stacks
        response = cf_client.list_stacks(
            StackStatusFilter=[
                'CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE',
                'CREATE_IN_PROGRESS', 'UPDATE_IN_PROGRESS'
            ]
        )
        
        stacks = response.get('StackSummaries', [])
        
        if not stacks:
            print("   No stacks found")
            return []
        
        print(f"   Found {len(stacks)} stacks:")
        for stack in stacks:
            stack_name = stack['StackName']
            status = stack['StackStatus']
            created = stack['CreationTime'].strftime('%Y-%m-%d %H:%M:%S')
            
            # Categorize
            if stack_name.startswith('AccountPoolFactory-') or stack_name.startswith('StackSet-'):
                category = "APPROVED"
            else:
                category = "PROJECT"
            
            print(f"   - [{category}] {stack_name} ({status}) - Created: {created}")
        
        return stacks
        
    except Exception as e:
        print(f"   ⚠️  Error listing stacks: {e}")
        return []


def update_reclaim_strategy(strategy='REUSE'):
    """Update ReclaimStrategy SSM parameter"""
    print(f"⚙️  Setting ReclaimStrategy to {strategy}...")
    
    ssm = boto3.client('ssm', region_name=REGION)
    
    try:
        ssm.put_parameter(
            Name='/AccountPoolFactory/PoolManager/ReclaimStrategy',
            Value=strategy,
            Type='String',
            Overwrite=True
        )
        print(f"✅ ReclaimStrategy set to {strategy}")
    except Exception as e:
        print(f"❌ Error setting ReclaimStrategy: {e}")


def trigger_pool_manager_reclaim(account_id):
    """Trigger PoolManager to reclaim the account"""
    print(f"🚀 Triggering PoolManager to reclaim account {account_id}...")
    
    # Simulate deletion event
    event = {
        'source': 'aws.cloudformation',
        'account': account_id,
        'detail': {
            'stack-name': 'DataZone-TestProject',
            'status-details': {
                'status': 'DELETE_COMPLETE'
            }
        }
    }
    
    print(f"   Event payload:")
    print(f"   {json.dumps(event, indent=2)}")
    
    response = lambda_client.invoke(
        FunctionName='PoolManager',
        InvocationType='RequestResponse',
        Payload=json.dumps(event)
    )
    
    result = json.loads(response['Payload'].read())
    print(f"   Response: {json.dumps(result, indent=2)}")
    
    return result


def monitor_cleanup_progress(account_id, timeout=900):
    """Monitor cleanup progress until completion or timeout"""
    print(f"👀 Monitoring cleanup progress (timeout: {timeout}s)...")
    
    start_time = time.time()
    last_state = None
    
    while time.time() - start_time < timeout:
        state_info = get_account_state(account_id)
        
        if not state_info:
            print(f"   ❌ Account not found in DynamoDB")
            return False
        
        current_state = state_info['state']
        
        # Print state change
        if current_state != last_state:
            elapsed = time.time() - start_time
            print(f"   [{elapsed:.1f}s] State: {current_state}")
            
            if current_state == 'CLEANING':
                print(f"      Cleanup started: {state_info.get('cleanupStartDate', 'Unknown')}")
            elif current_state == 'AVAILABLE':
                print(f"      Cleanup completed: {state_info.get('cleanupCompletedDate', 'Unknown')}")
                print(f"   ✅ Account successfully recycled!")
                return True
            elif current_state == 'FAILED':
                print(f"      Failed step: {state_info.get('failedStep', 'Unknown')}")
                print(f"      Failed stack: {state_info.get('failedStack', 'Unknown')}")
                print(f"      Error: {state_info.get('errorMessage', 'Unknown')}")
                print(f"   ❌ Cleanup failed!")
                return False
            
            last_state = current_state
        
        time.sleep(10)
    
    print(f"   ⏱️  Timeout reached after {timeout}s")
    print(f"   Final state: {current_state}")
    return False


def main():
    """Main test flow"""
    print_section("Account Recycling Test")
    
    # Get account ID from command line or find one
    if len(sys.argv) > 1:
        account_id = sys.argv[1]
        print(f"Using provided account ID: {account_id}")
    else:
        account_id = find_assigned_account()
        if not account_id:
            print("\n❌ No ASSIGNED accounts available for testing")
            print("   Create a project first or provide an account ID manually")
            sys.exit(1)
    
    # Get initial state
    print_section("Initial State")
    initial_state = get_account_state(account_id)
    if not initial_state:
        print(f"❌ Account {account_id} not found in pool")
        sys.exit(1)
    
    print(f"Account ID: {initial_state['accountId']}")
    print(f"Account Name: {initial_state['accountName']}")
    print(f"Current State: {initial_state['state']}")
    print(f"Assigned Date: {initial_state.get('assignedDate', 'N/A')}")
    
    # List stacks before cleanup
    print_section("Stacks Before Cleanup")
    stacks_before = list_stacks_in_account(account_id)
    
    # Update ReclaimStrategy to REUSE
    print_section("Configure Reclaim Strategy")
    update_reclaim_strategy('REUSE')
    
    # Trigger reclaim
    print_section("Trigger Account Reclaim")
    result = trigger_pool_manager_reclaim(account_id)
    
    if result.get('statusCode') != 200:
        print(f"❌ Failed to trigger reclaim: {result}")
        sys.exit(1)
    
    # Monitor progress
    print_section("Monitor Cleanup Progress")
    success = monitor_cleanup_progress(account_id, timeout=900)
    
    # Get final state
    print_section("Final State")
    final_state = get_account_state(account_id)
    
    print(f"Account ID: {final_state['accountId']}")
    print(f"Account Name: {final_state['accountName']}")
    print(f"Final State: {final_state['state']}")
    print(f"Cleanup Start: {final_state.get('cleanupStartDate', 'N/A')}")
    print(f"Cleanup Complete: {final_state.get('cleanupCompletedDate', 'N/A')}")
    
    if final_state['state'] == 'FAILED':
        print(f"Failed Step: {final_state.get('failedStep', 'N/A')}")
        print(f"Failed Stack: {final_state.get('failedStack', 'N/A')}")
        print(f"Error: {final_state.get('errorMessage', 'N/A')}")
    
    # List stacks after cleanup
    if success:
        print_section("Stacks After Cleanup")
        stacks_after = list_stacks_in_account(account_id)
        
        print(f"\nStack count: {len(stacks_before)} → {len(stacks_after)}")
    
    # Summary
    print_section("Test Summary")
    if success:
        print("✅ Account recycling test PASSED")
        print(f"   Account {account_id} successfully cleaned and returned to pool")
    else:
        print("❌ Account recycling test FAILED")
        print(f"   Account {account_id} is in state: {final_state['state']}")
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

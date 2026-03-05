"""
Pool Manager Lambda Function

Orchestrates pool-level operations including:
- Account assignment detection from CloudFormation events
- Pool size monitoring and replenishment triggering
- Parallel account creation via Organizations API
- Account deletion detection and reclamation (DELETE/REUSE strategies)
- Failed account tracking and replenishment blocking
- CloudWatch metrics and SNS notifications
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import boto3
from botocore.exceptions import ClientError

# Initialize AWS clients
dynamodb = boto3.client('dynamodb')
lambda_client = boto3.client('lambda')
sns = boto3.client('sns')
cloudwatch = boto3.client('cloudwatch')
ssm = boto3.client('ssm')
sts = boto3.client('sts')

# Environment variables
DYNAMODB_TABLE_NAME = os.environ['DYNAMODB_TABLE_NAME']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
SETUP_ORCHESTRATOR_FUNCTION_NAME = os.environ['SETUP_ORCHESTRATOR_FUNCTION_NAME']
DOMAIN_ACCOUNT_ID = os.environ['DOMAIN_ACCOUNT_ID']

# Configuration cache (cleared on each invocation)
_config_cache = None


def load_config() -> Dict[str, Any]:
    """Load configuration from SSM Parameter Store on every invocation"""
    try:
        config = {}
        next_token = None
        total_params = 0
        
        # Handle pagination to fetch all parameters
        while True:
            params = {
                'Path': '/AccountPoolFactory/PoolManager/',
                'Recursive': True,
                'WithDecryption': False,
                'MaxResults': 10  # Explicit max results per page
            }
            
            if next_token:
                params['NextToken'] = next_token
            
            response = ssm.get_parameters_by_path(**params)
            
            # Process parameters from this page
            for param in response['Parameters']:
                key = param['Name'].split('/')[-1]
                config[key] = param['Value']
                total_params += 1
            
            # Check if there are more pages
            next_token = response.get('NextToken')
            if not next_token:
                break
        
        print(f"📋 Loaded {total_params} parameters from SSM (with pagination)")
        print(f"   Parameter names: {sorted(config.keys())}")
        
        # Apply defaults for missing parameters
        config.setdefault('PoolName', 'AccountPoolFactory')
        config.setdefault('TargetOUId', 'root')
        config.setdefault('MinimumPoolSize', '5')
        config.setdefault('TargetPoolSize', '10')
        config.setdefault('MaxConcurrentSetups', '3')
        config.setdefault('ReclaimStrategy', 'DELETE')
        config.setdefault('EmailPrefix', 'accountpool')
        config.setdefault('EmailDomain', 'example.com')
        config.setdefault('NamePrefix', 'DataZone-Pool')
        
        print(f"✅ Configuration loaded successfully")
        return config
        
    except Exception as e:
        print(f"⚠️ Failed to load SSM parameters: {e}")
        print("Using default configuration")
        return {
            'PoolName': 'AccountPoolFactory',
            'TargetOUId': 'root',
            'MinimumPoolSize': '5',
            'TargetPoolSize': '10',
            'MaxConcurrentSetups': '3',
            'ReclaimStrategy': 'DELETE',
            'EmailPrefix': 'accountpool',
            'EmailDomain': 'example.com',
            'NamePrefix': 'DataZone-Pool'
        }


def get_config() -> Dict[str, Any]:
    """Get config with single-execution caching"""
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache


def lambda_handler(event, context):
    """
    Main Lambda handler for Pool Manager
    
    Handles:
    - CloudFormation stack events (CREATE_IN_PROGRESS, DELETE_COMPLETE)
    - Manual replenishment triggers
    - Failed account deletion requests
    """
    global _config_cache
    _config_cache = None  # Clear cache at start of invocation
    
    print(f"📥 Received event: {json.dumps(event, indent=2)}")
    
    config = get_config()
    
    # Handle manual actions
    if 'action' in event:
        action = event['action']
        if action == 'force_replenishment':
            return handle_force_replenishment(config)
        elif action == 'delete_failed_account':
            return handle_delete_failed_account(event['accountId'], config)
        else:
            return {'statusCode': 400, 'body': f'Unknown action: {action}'}
    
    # Handle CloudFormation events
    if 'source' in event and event['source'] == 'aws.cloudformation':
        detail = event.get('detail', {})
        status = detail.get('status-details', {}).get('status')
        stack_name = detail.get('stack-name', '')
        account_id = event.get('account')
        
        if not stack_name.startswith('DataZone-'):
            print(f"⏭️ Ignoring non-DataZone stack: {stack_name}")
            return {'statusCode': 200, 'body': 'Ignored'}
        
        if status == 'CREATE_IN_PROGRESS':
            return handle_assignment_event(account_id, stack_name, config)
        elif status == 'DELETE_COMPLETE':
            return handle_deletion_event(account_id, stack_name, config)
    
    print("⚠️ Unhandled event type")
    return {'statusCode': 200, 'body': 'No action taken'}


def handle_assignment_event(account_id: str, stack_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Handle account assignment when project is created"""
    print(f"🎯 Processing assignment event for account {account_id}, stack {stack_name}")
    
    # Query DynamoDB to verify account exists with state AVAILABLE
    try:
        response = dynamodb.query(
            TableName=DYNAMODB_TABLE_NAME,
            KeyConditionExpression='accountId = :accountId',
            ExpressionAttributeValues={':accountId': {'S': account_id}},
            ScanIndexForward=False,
            Limit=1
        )
        
        if not response.get('Items'):
            print(f"⚠️ Account {account_id} not found in pool, ignoring")
            return {'statusCode': 200, 'body': 'Account not in pool'}
        
        item = response['Items'][0]
        current_state = item.get('state', {}).get('S')
        
        if current_state != 'AVAILABLE':
            print(f"⚠️ Account {account_id} is in state {current_state}, not AVAILABLE")
            return {'statusCode': 200, 'body': f'Account in state {current_state}'}
        
        # Update account state to ASSIGNED
        timestamp = int(time.time())
        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp']
            },
            UpdateExpression='SET #state = :state, assignedDate = :date, projectStackName = :stack',
            ExpressionAttributeNames={'#state': 'state'},
            ExpressionAttributeValues={
                ':state': {'S': 'ASSIGNED'},
                ':date': {'S': datetime.now(timezone.utc).isoformat()},
                ':stack': {'S': stack_name}
            }
        )
        
        print(f"✅ Account {account_id} marked as ASSIGNED")
        
        # Publish metric
        publish_metric('AccountAssigned', 1, [{'Name': 'AccountId', 'Value': account_id}])
        
        # Check pool size and trigger replenishment if needed
        check_pool_size_and_replenish(config)
        
        return {'statusCode': 200, 'body': 'Assignment processed'}
        
    except Exception as e:
        print(f"❌ Error processing assignment: {e}")
        return {'statusCode': 500, 'body': str(e)}


def check_pool_size_and_replenish(config: Dict[str, Any]):
    """Check available account count and trigger replenishment if below minimum"""
    print("📊 Checking pool size...")
    
    # Query available accounts
    available_count = count_accounts_by_state('AVAILABLE')
    setting_up_count = count_accounts_by_state('SETTING_UP')
    failed_count = count_accounts_by_state('FAILED')
    
    print(f"📈 Pool status: {available_count} available, {setting_up_count} setting up, {failed_count} failed")
    
    # Publish metrics
    publish_metric('AvailableAccountCount', available_count)
    publish_metric('SettingUpAccountCount', setting_up_count)
    publish_metric('FailedAccountCount', failed_count)
    
    minimum_pool_size = int(config['MinimumPoolSize'])
    
    if available_count >= minimum_pool_size:
        print(f"✅ Pool size ({available_count}) is above minimum ({minimum_pool_size})")
        return
    
    # Check for failed accounts - block replenishment if any exist
    if failed_count > 0:
        print(f"🚫 Replenishment BLOCKED: {failed_count} failed accounts exist")
        publish_metric('ReplenishmentBlocked', 1, [{'Name': 'FailedAccountCount', 'Value': str(failed_count)}])
        
        # Send SNS notification
        send_replenishment_blocked_notification(failed_count)
        return
    
    # Calculate replenishment quantity
    target_pool_size = int(config['TargetPoolSize'])
    max_concurrent_setups = int(config['MaxConcurrentSetups'])
    
    replenishment_quantity = target_pool_size - available_count
    max_new_accounts = max_concurrent_setups - setting_up_count
    
    if max_new_accounts <= 0:
        print(f"⏸️ Max concurrent setups ({max_concurrent_setups}) reached, waiting...")
        return
    
    accounts_to_create = min(replenishment_quantity, max_new_accounts)
    
    print(f"🚀 Triggering replenishment: creating {accounts_to_create} accounts")
    publish_metric('ReplenishmentTriggered', 1, [
        {'Name': 'AvailableCount', 'Value': str(available_count)},
        {'Name': 'RequestedCount', 'Value': str(accounts_to_create)}
    ])
    
    # Create accounts in parallel
    create_accounts_parallel(accounts_to_create, config)


def count_accounts_by_state(state: str) -> int:
    """Count accounts in a specific state using GSI"""
    try:
        response = dynamodb.query(
            TableName=DYNAMODB_TABLE_NAME,
            IndexName='StateIndex',
            KeyConditionExpression='#state = :state',
            ExpressionAttributeNames={'#state': 'state'},
            ExpressionAttributeValues={':state': {'S': state}},
            Select='COUNT'
        )
        return response.get('Count', 0)
    except Exception as e:
        print(f"❌ Error counting accounts in state {state}: {e}")
        return 0


def create_accounts_parallel(count: int, config: Dict[str, Any]):
    """Create multiple accounts sequentially with delays to avoid concurrent modification errors
    
    AWS Organizations has rate limits and doesn't support true parallel account creation.
    We create accounts one at a time with delays between each to avoid ConcurrentModificationException.
    """
    import uuid
    
    # Get ProvisionAccount Lambda ARN from environment or config
    org_admin_account_id = config.get('OrgAdminAccountId', os.environ.get('ORG_ADMIN_ACCOUNT_ID'))
    region = os.environ.get('AWS_REGION', 'us-east-2')
    provision_account_arn = f"arn:aws:lambda:{region}:{org_admin_account_id}:function:ProvisionAccount"
    
    print(f"📞 Using ProvisionAccount Lambda: {provision_account_arn}")
    print(f"⚠️  Creating accounts sequentially to avoid AWS Organizations rate limits")
    
    timestamp = int(time.time())
    successful_accounts = []
    
    # Get pool name for account naming (sanitize for AWS account name requirements)
    pool_name = config.get('PoolName', 'AccountPoolFactory')
    # Remove spaces, convert to lowercase, keep only alphanumeric and hyphens
    pool_name_clean = ''.join(c if c.isalnum() or c == '-' else '-' for c in pool_name.lower())
    pool_name_clean = pool_name_clean.strip('-')[:20]  # Max 20 chars for pool name part
    
    for i in range(count):
        try:
            # Generate unique email and name using UUID to avoid conflicts
            # Format: smus-{pool-name}-{12-char-uuid}
            # Using 12 chars instead of 8 to reduce collision probability with 200+ test accounts
            unique_id = str(uuid.uuid4()).replace('-', '')[:12]  # 12 hex chars from UUID
            
            # Account name format: smus-{pool-name}-{unique-id}
            # Example: smus-test-a3f8b2c1
            name = f"smus-{pool_name_clean}-{unique_id}"
            
            # Email format: {prefix}+{unique-id}@{domain}
            # Example: accountpool+a3f8b2c1@example.com
            email = f"{config['EmailPrefix']}+{unique_id}@{config['EmailDomain']}"
            
            print(f"📧 Creating account {i+1}/{count}: {name} ({email})")
            
            # Invoke ProvisionAccount Lambda in Org Admin account
            payload = {
                'action': 'provision',
                'accountName': name,
                'accountEmail': email,
                'ouId': config.get('TargetOUId', 'root'),
                'domainId': os.environ.get('DOMAIN_ID'),
                'domainAccountId': DOMAIN_ACCOUNT_ID,
                'orgAdminAccountId': org_admin_account_id
            }
            
            print(f"   Invoking ProvisionAccount with payload: {json.dumps(payload, indent=2)}")
            
            response = lambda_client.invoke(
                FunctionName=provision_account_arn,
                InvocationType='RequestResponse',  # Synchronous - wait for account to be ready
                Payload=json.dumps(payload)
            )
            
            # Parse response
            response_payload = json.loads(response['Payload'].read())
            print(f"   ProvisionAccount response: {json.dumps(response_payload, indent=2)}")
            
            if response_payload.get('status') == 'SUCCESS':
                account_id = response_payload['accountId']
                print(f"✅ Account provisioned and ready: {account_id}")
                
                # Create DynamoDB record
                create_account_record(account_id, f"provision-{timestamp}-{i}", name, email)
                
                # Invoke Setup Orchestrator asynchronously
                invoke_setup_orchestrator(account_id, f"provision-{timestamp}-{i}")
                
                publish_metric('AccountCreationStarted', 1, [{'Name': 'AccountId', 'Value': account_id}])
                successful_accounts.append(account_id)
                
                # Add delay between account creations to avoid concurrent modification errors
                # AWS Organizations needs time to process each account creation
                if i < count - 1:  # Don't delay after last account
                    delay = 15  # 15 seconds between accounts
                    print(f"   ⏳ Waiting {delay}s before creating next account...")
                    time.sleep(delay)
            else:
                error_msg = response_payload.get('message', 'Unknown error')
                print(f"❌ Account provisioning failed: {error_msg}")
                
                # Handle specific error cases
                if 'EMAIL_ALREADY_EXISTS' in error_msg:
                    # This should be handled by ProvisionAccount Lambda now
                    # If we still get this error, it means the account exists but couldn't be found
                    print(f"   ⚠️  Email collision detected, skipping to next account")
                    publish_metric('EmailCollision', 1)
                elif 'ConcurrentModificationException' in error_msg:
                    print(f"   ⏳ Waiting 30s due to concurrent modification...")
                    time.sleep(30)
                
                # Continue to next account
                continue
            
        except Exception as e:
            print(f"❌ Error creating account {i+1}: {e}")
            # Wait before retrying next account
            time.sleep(15)
            continue
    
    print(f"✅ Successfully created {len(successful_accounts)}/{count} accounts")
    if successful_accounts:
        print(f"   Account IDs: {', '.join(successful_accounts)}")


def create_account_record(account_id: str, request_id: str, name: str, email: str):
    """Create DynamoDB record for new account"""
    timestamp = int(time.time())
    
    try:
        dynamodb.put_item(
            TableName=DYNAMODB_TABLE_NAME,
            Item={
                'accountId': {'S': account_id},
                'timestamp': {'N': str(timestamp)},
                'state': {'S': 'SETTING_UP'},
                'createdDate': {'S': datetime.now(timezone.utc).isoformat()},
                'accountName': {'S': name},
                'accountEmail': {'S': email},
                'createRequestId': {'S': request_id},
                'setupStartDate': {'S': datetime.now(timezone.utc).isoformat()},
                'completedSteps': {'L': []},
                'retryCount': {'N': '0'}
            }
        )
        print(f"✅ Created DynamoDB record for account {account_id}")
    except Exception as e:
        print(f"❌ Error creating DynamoDB record: {e}")


def invoke_setup_orchestrator(account_id: str, request_id: str):
    """Invoke Setup Orchestrator Lambda asynchronously"""
    try:
        payload = {
            'accountId': account_id,
            'requestId': request_id,
            'mode': 'setup'
        }
        
        lambda_client.invoke(
            FunctionName=SETUP_ORCHESTRATOR_FUNCTION_NAME,
            InvocationType='Event',  # Asynchronous
            Payload=json.dumps(payload)
        )
        
        print(f"✅ Invoked Setup Orchestrator for account {account_id}")
    except Exception as e:
        print(f"❌ Error invoking Setup Orchestrator: {e}")


def handle_deletion_event(account_id: str, stack_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Handle account deletion when project is removed"""
    print(f"🗑️ Processing deletion event for account {account_id}, stack {stack_name}")
    
    # Query DynamoDB to get account record
    try:
        response = dynamodb.query(
            TableName=DYNAMODB_TABLE_NAME,
            KeyConditionExpression='accountId = :accountId',
            ExpressionAttributeValues={':accountId': {'S': account_id}},
            ScanIndexForward=False,
            Limit=1
        )
        
        if not response.get('Items'):
            print(f"⚠️ Account {account_id} not found in pool")
            return {'statusCode': 200, 'body': 'Account not in pool'}
        
        item = response['Items'][0]
        current_state = item.get('state', {}).get('S')
        
        if current_state != 'ASSIGNED':
            print(f"⚠️ Account {account_id} is in state {current_state}, not ASSIGNED")
            return {'statusCode': 200, 'body': f'Account in state {current_state}'}
        
        # Check if any DataZone stacks remain in the account
        if has_remaining_datazone_stacks(account_id):
            print(f"⏳ Account {account_id} still has DataZone stacks, waiting...")
            return {'statusCode': 200, 'body': 'Waiting for all stacks to delete'}
        
        # Reclaim account based on strategy
        reclaim_strategy = config.get('ReclaimStrategy', 'DELETE')
        
        if reclaim_strategy == 'DELETE':
            return reclaim_account_delete(account_id, item, config)
        elif reclaim_strategy == 'REUSE':
            return reclaim_account_reuse(account_id, item)
        else:
            print(f"⚠️ Unknown reclaim strategy: {reclaim_strategy}")
            return {'statusCode': 400, 'body': f'Unknown strategy: {reclaim_strategy}'}
        
    except Exception as e:
        print(f"❌ Error processing deletion: {e}")
        return {'statusCode': 500, 'body': str(e)}


def has_remaining_datazone_stacks(account_id: str) -> bool:
    """Check if account has any remaining DataZone stacks"""
    try:
        # Assume role in project account
        role_arn = f"arn:aws:iam::{account_id}:role/OrganizationAccountAccessRole"
        assumed_role = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName='PoolManager-StackCheck'
        )
        
        credentials = assumed_role['Credentials']
        cf_client = boto3.client(
            'cloudformation',
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )
        
        # List stacks with DataZone prefix
        response = cf_client.list_stacks(
            StackStatusFilter=['CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE']
        )
        
        datazone_stacks = [
            stack for stack in response.get('StackSummaries', [])
            if stack['StackName'].startswith('DataZone-')
        ]
        
        return len(datazone_stacks) > 0
        
    except Exception as e:
        print(f"⚠️ Error checking stacks in account {account_id}: {e}")
        return True  # Assume stacks exist if we can't check


def reclaim_account_delete(account_id: str, item: Dict, config: Dict[str, Any]) -> Dict[str, Any]:
    """Reclaim account using DELETE strategy - just removes from pool"""
    print(f"🗑️ Reclaiming account {account_id} using DELETE strategy")
    
    try:
        # Update state to DELETING
        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp']
            },
            UpdateExpression='SET #state = :state, deletionStartDate = :date',
            ExpressionAttributeNames={'#state': 'state'},
            ExpressionAttributeValues={
                ':state': {'S': 'DELETING'},
                ':date': {'S': datetime.now(timezone.utc).isoformat()}
            }
        )
        
        print(f"✅ Account {account_id} marked for deletion")
        print(f"⚠️  Note: Account deletion via Organizations API requires Org Admin permissions")
        print(f"⚠️  Account will be removed from pool but still exists in AWS Organizations")
        
        # Delete DynamoDB record
        dynamodb.delete_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp']
            }
        )
        
        publish_metric('AccountDeleted', 1, [{'Name': 'AccountId', 'Value': account_id}])
        
        return {'statusCode': 200, 'body': 'Account removed from pool'}
        
    except Exception as e:
        print(f"❌ Error removing account {account_id}: {e}")
        
        # Mark as FAILED
        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp']
            },
            UpdateExpression='SET #state = :state, errorMessage = :error',
            ExpressionAttributeNames={'#state': 'state'},
            ExpressionAttributeValues={
                ':state': {'S': 'FAILED'},
                ':error': {'S': str(e)}
            }
        )
        
        send_failure_notification(account_id, 'account_deletion', str(e))
        
        return {'statusCode': 500, 'body': str(e)}


def reclaim_account_reuse(account_id: str, item: Dict) -> Dict[str, Any]:
    """Reclaim account using REUSE strategy"""
    print(f"♻️ Reclaiming account {account_id} using REUSE strategy")
    
    try:
        # Update state to CLEANING
        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp']
            },
            UpdateExpression='SET #state = :state, cleanupStartDate = :date',
            ExpressionAttributeNames={'#state': 'state'},
            ExpressionAttributeValues={
                ':state': {'S': 'CLEANING'},
                ':date': {'S': datetime.now(timezone.utc).isoformat()}
            }
        )
        
        # Invoke Setup Orchestrator in cleanup mode
        payload = {
            'accountId': account_id,
            'mode': 'cleanup'
        }
        
        lambda_client.invoke(
            FunctionName=SETUP_ORCHESTRATOR_FUNCTION_NAME,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
        
        print(f"✅ Cleanup initiated for account {account_id}")
        
        return {'statusCode': 200, 'body': 'Cleanup initiated'}
        
    except Exception as e:
        print(f"❌ Error initiating cleanup for account {account_id}: {e}")
        
        # Mark as FAILED
        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp']
            },
            UpdateExpression='SET #state = :state, errorMessage = :error',
            ExpressionAttributeNames={'#state': 'state'},
            ExpressionAttributeValues={
                ':state': {'S': 'FAILED'},
                ':error': {'S': str(e)}
            }
        )
        
        send_failure_notification(account_id, 'account_cleanup', str(e))
        
        return {'statusCode': 500, 'body': str(e)}


def handle_force_replenishment(config: Dict[str, Any]) -> Dict[str, Any]:
    """Handle manual replenishment trigger"""
    print("🔄 Force replenishment triggered")
    check_pool_size_and_replenish(config)
    return {'statusCode': 200, 'body': 'Replenishment triggered'}


def handle_delete_failed_account(account_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Handle manual deletion of failed account - just removes from DynamoDB"""
    print(f"🗑️ Removing failed account {account_id} from pool")
    
    try:
        # Query DynamoDB to get account record
        response = dynamodb.query(
            TableName=DYNAMODB_TABLE_NAME,
            KeyConditionExpression='accountId = :accountId',
            ExpressionAttributeValues={':accountId': {'S': account_id}},
            ScanIndexForward=False,
            Limit=1
        )
        
        if not response.get('Items'):
            return {'statusCode': 404, 'body': 'Account not found'}
        
        item = response['Items'][0]
        
        # Delete DynamoDB record (account deletion must be done manually via Organizations console)
        dynamodb.delete_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp']
            }
        )
        
        publish_metric('FailedAccountDeleted', 1, [{'Name': 'AccountId', 'Value': account_id}])
        
        print(f"✅ Failed account {account_id} removed from pool")
        print(f"⚠️  Note: Account still exists in AWS Organizations - delete manually if needed")
        
        return {'statusCode': 200, 'body': 'Failed account removed from pool'}
        
    except Exception as e:
        print(f"❌ Error removing failed account: {e}")
        return {'statusCode': 500, 'body': str(e)}


def publish_metric(metric_name: str, value: float, dimensions: List[Dict[str, str]] = None):
    """Publish CloudWatch metric"""
    try:
        metric_data = {
            'MetricName': metric_name,
            'Value': value,
            'Unit': 'Count',
            'Timestamp': datetime.now(timezone.utc)
        }
        
        if dimensions:
            metric_data['Dimensions'] = dimensions
        
        cloudwatch.put_metric_data(
            Namespace='AccountPoolFactory/PoolManager',
            MetricData=[metric_data]
        )
    except Exception as e:
        print(f"⚠️ Error publishing metric {metric_name}: {e}")


def send_replenishment_blocked_notification(failed_count: int):
    """Send SNS notification when replenishment is blocked"""
    try:
        # Get failed account details
        response = dynamodb.query(
            TableName=DYNAMODB_TABLE_NAME,
            IndexName='StateIndex',
            KeyConditionExpression='#state = :state',
            ExpressionAttributeNames={'#state': 'state'},
            ExpressionAttributeValues={':state': {'S': 'FAILED'}}
        )
        
        failed_accounts = []
        for item in response.get('Items', []):
            failed_accounts.append({
                'accountId': item.get('accountId', {}).get('S'),
                'failedStep': item.get('failedStep', {}).get('S', 'Unknown'),
                'errorMessage': item.get('errorMessage', {}).get('S', 'No error message')
            })
        
        message = {
            'alertType': 'REPLENISHMENT_BLOCKED',
            'severity': 'HIGH',
            'failedAccountCount': failed_count,
            'failedAccounts': failed_accounts,
            'message': f'Pool replenishment is blocked due to {failed_count} failed accounts',
            'action': 'Delete failed accounts using: aws lambda invoke --function-name PoolManager --payload \'{"action":"delete_failed_account","accountId":"ACCOUNT_ID"}\' response.json',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject='Pool Replenishment Blocked - Failed Accounts Require Attention',
            Message=json.dumps(message, indent=2)
        )
        
        print(f"📧 Sent replenishment blocked notification")
        
    except Exception as e:
        print(f"⚠️ Error sending notification: {e}")


def send_failure_notification(account_id: str, operation: str, error_message: str):
    """Send SNS notification for operation failure"""
    try:
        message = {
            'alertType': 'OPERATION_FAILED',
            'severity': 'HIGH',
            'accountId': account_id,
            'operation': operation,
            'errorMessage': error_message,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f'Account Operation Failed: {account_id}',
            Message=json.dumps(message, indent=2)
        )
        
        print(f"📧 Sent failure notification for {operation}")
        
    except Exception as e:
        print(f"⚠️ Error sending notification: {e}")

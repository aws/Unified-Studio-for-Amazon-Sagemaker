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
    """Load configuration from SSM Parameter Store on every invocation.

    Returns a config dict with:
    - Legacy single-pool keys (PoolName, MinimumPoolSize, etc.) for backward compat
    - 'pools': dict of pool_name -> {MinimumPoolSize, TargetPoolSize, ReclaimStrategy,
                                      ProjectProfileName, EmailPrefix, EmailDomain}
    """
    try:
        config = {}
        pools: Dict[str, Any] = {}

        # Load legacy /PoolManager/ params
        next_token = None
        total_params = 0
        while True:
            params = {
                'Path': '/AccountPoolFactory/PoolManager/',
                'Recursive': True,
                'WithDecryption': False,
                'MaxResults': 10
            }
            if next_token:
                params['NextToken'] = next_token
            response = ssm.get_parameters_by_path(**params)
            for param in response['Parameters']:
                key = param['Name'].split('/')[-1]
                config[key] = param['Value']
                total_params += 1
            next_token = response.get('NextToken')
            if not next_token:
                break

        # Load per-pool params from /AccountPoolFactory/Pools/{name}/
        try:
            pool_params_resp = ssm.get_parameters_by_path(
                Path='/AccountPoolFactory/Pools/',
                Recursive=True,
                WithDecryption=False
            )
            for param in pool_params_resp['Parameters']:
                # /AccountPoolFactory/Pools/{pool_name}/{key}
                parts = param['Name'].split('/')
                # parts: ['', 'AccountPoolFactory', 'Pools', pool_name, key]
                if len(parts) >= 5:
                    pool_name = parts[3]
                    key = parts[4]
                    if pool_name and key:
                        pools.setdefault(pool_name, {})[key] = param['Value']
        except Exception as e:
            print(f'⚠️ Could not load per-pool SSM params: {e}')

        config['pools'] = pools
        print(f'📋 Loaded {total_params} PoolManager params, {len(pools)} pools: {list(pools.keys())}')

        # Apply defaults for legacy single-pool keys
        config.setdefault('PoolName', list(pools.keys())[0] if pools else 'default')
        config.setdefault('MinimumPoolSize', '2')
        config.setdefault('TargetPoolSize', '5')
        config.setdefault('MaxConcurrentSetups', '3')
        config.setdefault('ReclaimStrategy', 'REUSE')
        config.setdefault('EmailPrefix', 'accountpool')
        config.setdefault('EmailDomain', 'example.com')
        config.setdefault('NamePrefix', 'DataZone-Pool')

        return config

    except Exception as e:
        print(f'⚠️ Failed to load SSM parameters: {e}')
        return {
            'PoolName': 'default',
            'MinimumPoolSize': '2',
            'TargetPoolSize': '5',
            'MaxConcurrentSetups': '3',
            'ReclaimStrategy': 'REUSE',
            'EmailPrefix': 'accountpool',
            'EmailDomain': 'example.com',
            'NamePrefix': 'DataZone-Pool',
            'pools': {},
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
            # Pass optional poolName from event into config so handler can filter
            if 'poolName' in event:
                config['poolName'] = event['poolName']
            return handle_force_replenishment(config)
        elif action == 'delete_failed_account':
            return handle_delete_failed_account(event['accountId'], config)
        else:
            return {'statusCode': 400, 'body': f'Unknown action: {action}'}

    # Handle DataZone events (source: aws.datazone)
    # These fire on the domain account default bus for project/environment lifecycle changes.
    if event.get('source') == 'aws.datazone':
        detail_type = event.get('detail-type', '')
        detail = event.get('detail', {})
        data = detail.get('data', {})
        project_id = data.get('projectId')
        # Deployment events include environmentAccount; deletion events do not — look it up
        account_id = data.get('environmentAccount')
        environment_id = data.get('environmentId')
        domain_id = os.environ.get('DOMAIN_ID', '')

        if not project_id:
            print(f"⏭️ DataZone event missing projectId, skipping")
            return {'statusCode': 200, 'body': 'Ignored'}

        # For deletion events, look up the account from DynamoDB by projectId
        if not account_id and project_id:
            try:
                resp = dynamodb.query(
                    TableName=DYNAMODB_TABLE_NAME,
                    IndexName='ProjectIndex',
                    KeyConditionExpression='projectId = :p',
                    ExpressionAttributeValues={':p': {'S': project_id}},
                    Limit=1
                )
                items = resp.get('Items', [])
                if items:
                    account_id = items[0].get('accountId', {}).get('S')
            except Exception as e:
                print(f"⚠️ Could not look up account for project {project_id}: {e}")

        # Fallback: try environment lookup (may fail if already deleted)
        if not account_id and environment_id:
            try:
                dz_client = boto3.client('datazone', region_name=os.environ.get('AWS_REGION', 'us-east-2'))
                env = dz_client.get_environment(domainIdentifier=domain_id, identifier=environment_id)
                account_id = env.get('awsAccountId')
            except Exception as e:
                print(f"⚠️ Could not look up environment {environment_id}: {e}")

        if not account_id:
            print(f"⏭️ DataZone event missing environmentAccount and could not look up, skipping")
            return {'statusCode': 200, 'body': 'Ignored'}

        if detail_type == 'Environment Deployment Completed':
            return handle_datazone_assignment(account_id, project_id, config)

        elif detail_type in ('Environment Deletion Completed', 'Environment Deletion Failed'):
            return handle_datazone_deletion(account_id, project_id, domain_id, config)

        print(f"⏭️ Unhandled DataZone event: {detail_type}")
        return {'statusCode': 200, 'body': 'Ignored'}

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


def check_pool_size_and_replenish(config: Dict[str, Any], target_pool: str = None):
    """Check available account count per pool and trigger replenishment if below minimum.

    If target_pool is given, only replenishes that pool. Otherwise iterates all pools.
    Falls back to single-pool legacy behavior if no pools are configured.
    """
    pools = config.get('pools', {})

    # Determine which pools to process
    if target_pool:
        pool_names = [target_pool] if target_pool in pools else []
        if not pool_names:
            # Fall back to legacy single-pool
            pool_names = [None]
    elif pools:
        pool_names = list(pools.keys())
    else:
        pool_names = [None]  # legacy single-pool mode

    max_concurrent = int(config.get('MaxConcurrentSetups', '3'))

    for pool_name in pool_names:
        pool_cfg = pools.get(pool_name, {}) if pool_name else {}
        min_size = int(pool_cfg.get('MinimumPoolSize', config.get('MinimumPoolSize', '2')))
        target_size = int(pool_cfg.get('TargetPoolSize', config.get('TargetPoolSize', '5')))

        available = count_accounts_by_state('AVAILABLE', pool_name)
        setting_up = count_accounts_by_state('SETTING_UP', pool_name)
        failed = count_accounts_by_state('FAILED', pool_name)

        label = f'pool={pool_name}' if pool_name else 'all'
        print(f'📊 [{label}] available={available} setting_up={setting_up} failed={failed} min={min_size}')

        publish_metric('AvailableAccountCount', available,
                       [{'Name': 'Pool', 'Value': pool_name or 'default'}])
        publish_metric('SettingUpAccountCount', setting_up,
                       [{'Name': 'Pool', 'Value': pool_name or 'default'}])

        if available >= min_size:
            print(f'✅ [{label}] Pool size OK ({available} >= {min_size})')
            continue

        if failed > 0:
            print(f'🚫 [{label}] Replenishment BLOCKED: {failed} failed accounts')
            publish_metric('ReplenishmentBlocked', 1,
                           [{'Name': 'Pool', 'Value': pool_name or 'default'}])
            send_replenishment_blocked_notification(failed)
            continue

        replenishment_qty = target_size - available
        max_new = max_concurrent - setting_up
        if max_new <= 0:
            print(f'⏸️ [{label}] Max concurrent setups reached, waiting...')
            continue

        to_create = min(replenishment_qty, max_new)
        print(f'🚀 [{label}] Creating {to_create} accounts')
        publish_metric('ReplenishmentTriggered', to_create,
                       [{'Name': 'Pool', 'Value': pool_name or 'default'}])

        # Build per-pool config for create_accounts_parallel
        pool_create_config = dict(config)
        if pool_name:
            pool_create_config['PoolName'] = pool_name
            pool_create_config['EmailPrefix'] = pool_cfg.get('EmailPrefix', config.get('EmailPrefix', 'accountpool'))
            pool_create_config['EmailDomain'] = pool_cfg.get('EmailDomain', config.get('EmailDomain', 'example.com'))

        create_accounts_parallel(to_create, pool_create_config)


def count_accounts_by_state(state: str, pool_name: str = None) -> int:
    """Count accounts in a specific state, optionally filtered by pool.

    Uses PoolIndex GSI when pool_name is provided, StateIndex otherwise.
    """
    try:
        if pool_name:
            response = dynamodb.query(
                TableName=DYNAMODB_TABLE_NAME,
                IndexName='PoolIndex',
                KeyConditionExpression='poolName = :pool AND #state = :state',
                ExpressionAttributeNames={'#state': 'state'},
                ExpressionAttributeValues={
                    ':pool': {'S': pool_name},
                    ':state': {'S': state},
                },
                Select='COUNT'
            )
        else:
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
        print(f'❌ Error counting accounts in state {state} (pool={pool_name}): {e}')
        return 0


def create_accounts_parallel(count: int, config: Dict[str, Any]):
    """Create multiple accounts sequentially with delays to avoid concurrent modification errors
    
    AWS Organizations has rate limits and doesn't support true parallel account creation.
    We create accounts one at a time with delays between each to avoid ConcurrentModificationException.
    """
    import uuid
    
    # Invoke ProvisionAccount Lambda locally (same account)
    region = os.environ.get('AWS_REGION', 'us-east-2')
    provision_account_arn = f"arn:aws:lambda:{region}:{DOMAIN_ACCOUNT_ID}:function:ProvisionAccount"

    print(f"📞 Using ProvisionAccount Lambda (local): {provision_account_arn}")
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
                'domainId': os.environ.get('DOMAIN_ID'),
                'domainAccountId': DOMAIN_ACCOUNT_ID,
                'poolName': config.get('PoolName', 'default'),
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
                returned_pool = response_payload.get('poolName', config.get('PoolName', 'default'))
                deployed_stacksets = response_payload.get('deployedStackSets', [])
                print(f"✅ Account provisioned and ready: {account_id}")
                
                # Create DynamoDB record with poolName and deployedStackSets
                create_account_record(account_id, f"provision-{timestamp}-{i}", name, email,
                                      pool_name=returned_pool, deployed_stacksets=deployed_stacksets)
                
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


def create_account_record(account_id: str, request_id: str, name: str, email: str,
                          pool_name: str = 'default', deployed_stacksets: list = None):
    """Create DynamoDB record for new account"""
    timestamp = int(time.time())
    item = {
        'accountId': {'S': account_id},
        'timestamp': {'N': str(timestamp)},
        'state': {'S': 'SETTING_UP'},
        'createdDate': {'S': datetime.now(timezone.utc).isoformat()},
        'accountName': {'S': name},
        'accountEmail': {'S': email},
        'createRequestId': {'S': request_id},
        'setupStartDate': {'S': datetime.now(timezone.utc).isoformat()},
        'completedSteps': {'L': []},
        'retryCount': {'N': '0'},
        'poolName': {'S': pool_name},
    }
    if deployed_stacksets:
        item['deployedStackSets'] = {'L': [{'S': s} for s in deployed_stacksets]}

    try:
        dynamodb.put_item(TableName=DYNAMODB_TABLE_NAME, Item=item)
        print(f"✅ Created DynamoDB record for account {account_id} (pool={pool_name})")
    except Exception as e:
        print(f"❌ Error creating DynamoDB record: {e}")


def invoke_setup_orchestrator(account_id: str, request_id: str):
    """Enqueue account for SetupOrchestrator via SQS (preferred) or async Lambda invoke (fallback)."""
    payload = {
        'accountId': account_id,
        'requestId': request_id,
        'mode': 'setup'
    }
    setup_queue_url = os.environ.get('SETUP_QUEUE_URL', '')
    try:
        if setup_queue_url:
            import boto3 as _boto3
            _boto3.client('sqs').send_message(
                QueueUrl=setup_queue_url,
                MessageBody=json.dumps(payload)
            )
            print(f"✅ Enqueued setup job for account {account_id} in SQS")
        else:
            lambda_client.invoke(
                FunctionName=SETUP_ORCHESTRATOR_FUNCTION_NAME,
                InvocationType='Event',
                Payload=json.dumps(payload)
            )
            print(f"✅ Invoked Setup Orchestrator async for account {account_id}")
    except Exception as e:
        print(f"❌ Error enqueuing setup for {account_id}: {e}")


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
        # Assume role in project account using SMUS-AccountPoolFactory-DomainAccess role
        role_arn = f"arn:aws:iam::{account_id}:role/SMUS-AccountPoolFactory-DomainAccess"
        domain_id = os.environ.get('DOMAIN_ID', '')
        
        assumed_role = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName='PoolManager-StackCheck',
            ExternalId=domain_id
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
        # If we can't check stacks, assume no stacks remain (proceed with cleanup)
        # This allows cleanup to proceed even if role assumption fails
        print(f"   Assuming no DataZone stacks remain, proceeding with cleanup")
        return False


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
    """Reclaim account using REUSE strategy - invokes DeprovisionAccount Lambda"""
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
        
        # Invoke DeprovisionAccount Lambda
        deprovision_function_name = os.environ.get('DEPROVISION_ACCOUNT_FUNCTION_NAME', 'DeprovisionAccount')
        domain_id = os.environ.get('DOMAIN_ID', '')
        
        payload = {
            'accountId': account_id,
            'requestId': f"reclaim-{int(time.time())}",
            'domainId': domain_id
        }
        
        print(f"📞 Invoking DeprovisionAccount Lambda: {deprovision_function_name}")
        
        lambda_client.invoke(
            FunctionName=deprovision_function_name,
            InvocationType='Event',  # Asynchronous
            Payload=json.dumps(payload)
        )
        
        print(f"✅ Deprovision initiated for account {account_id}")

        # Trigger recycler to process CLEANING state after deprovision completes
        try:
            lambda_client.invoke(
                FunctionName='AccountRecycler',
                InvocationType='Event',
                Payload=json.dumps({'accountId': account_id})
            )
            print(f"✅ AccountRecycler triggered for {account_id}")
        except Exception as e:
            print(f"⚠️ Could not trigger recycler: {e}")
        
        return {'statusCode': 200, 'body': 'Deprovision initiated'}
        
    except Exception as e:
        print(f"❌ Error initiating deprovision for account {account_id}: {e}")
        
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
        
        send_failure_notification(account_id, 'account_deprovision', str(e))
        
        return {'statusCode': 500, 'body': str(e)}


def handle_datazone_assignment(account_id: str, project_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Environment Deployment Completed — mark account ASSIGNED if not already."""
    print(f"🎯 DataZone environment deployed in account {account_id} for project {project_id}")
    try:
        response = dynamodb.query(
            TableName=DYNAMODB_TABLE_NAME,
            KeyConditionExpression='accountId = :a',
            ExpressionAttributeValues={':a': {'S': account_id}},
            ScanIndexForward=False, Limit=1
        )
        if not response.get('Items'):
            print(f"⏭️ Account {account_id} not in pool, ignoring")
            return {'statusCode': 200, 'body': 'Not in pool'}

        item = response['Items'][0]
        state = item.get('state', {}).get('S')

        if state == 'ASSIGNED':
            # Update projectId if not already set (may have been assigned via AccountProvider.validate)
            existing_project = item.get('projectId', {}).get('S', '')
            if not existing_project and project_id:
                try:
                    dynamodb.update_item(
                        TableName=DYNAMODB_TABLE_NAME,
                        Key={'accountId': {'S': account_id}, 'timestamp': item['timestamp']},
                        UpdateExpression='SET projectId = :p',
                        ExpressionAttributeValues={':p': {'S': project_id}}
                    )
                    print(f"✅ Updated projectId for already-ASSIGNED account {account_id}")
                except Exception as e:
                    print(f"⚠️ Could not update projectId: {e}")
            else:
                print(f"✅ Account {account_id} already ASSIGNED")
            return {'statusCode': 200, 'body': 'Already assigned'}

        if state != 'AVAILABLE':
            print(f"⏭️ Account {account_id} in state {state}, ignoring")
            return {'statusCode': 200, 'body': f'State {state}'}

        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={'accountId': {'S': account_id}, 'timestamp': item['timestamp']},
            UpdateExpression='SET #s = :s, assignedDate = :d, projectId = :p',
            ConditionExpression='#s = :avail',
            ExpressionAttributeNames={'#s': 'state'},
            ExpressionAttributeValues={
                ':s': {'S': 'ASSIGNED'},
                ':avail': {'S': 'AVAILABLE'},
                ':d': {'S': datetime.now(timezone.utc).isoformat()},
                ':p': {'S': project_id}
            }
        )
        print(f"✅ Account {account_id} marked ASSIGNED for project {project_id}")
        publish_metric('AccountAssigned', 1, [{'Name': 'AccountId', 'Value': account_id}])
        check_pool_size_and_replenish(config)
        return {'statusCode': 200, 'body': 'Assigned'}

    except dynamodb.exceptions.ConditionalCheckFailedException:
        print(f"ℹ️ Account {account_id} already assigned (concurrent)")
        return {'statusCode': 200, 'body': 'Already assigned'}
    except Exception as e:
        print(f"❌ Error handling assignment: {e}")
        return {'statusCode': 500, 'body': str(e)}


def handle_datazone_deletion(account_id: str, project_id: str, domain_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Environment Deletion Completed — reclaim account only when ALL environments
    in this project on this account are gone."""
    print(f"🗑️ DataZone environment deleted in account {account_id} for project {project_id}")
    try:
        # Check if any active environments remain for this project in this account
        # Use DataZone API — if project is deleted, all environments are gone
        dz = boto3.client('datazone', region_name=os.environ.get('AWS_REGION', 'us-east-2'))
        domain = os.environ.get('DOMAIN_ID', domain_id or '')

        remaining = []
        try:
            # Check if project still exists — if not, all environments are gone
            dz.get_project(domainIdentifier=domain, identifier=project_id)
            # Project exists — check environments
            try:
                resp = dz.list_environments(domainIdentifier=domain, projectIdentifier=project_id)
                for env in resp.get('items', []):
                    env_account = env.get('awsAccountId', '')
                    env_status = env.get('status', '')
                    if env_account == account_id and env_status not in ('DELETED', 'DELETE_FAILED'):
                        remaining.append(env.get('id'))
            except Exception as e:
                print(f"⚠️ Could not list environments: {e} — deferring reclaim to reconciler")
                return {'statusCode': 200, 'body': 'Deferred'}
        except dz.exceptions.ResourceNotFoundException:
            # Project deleted — all environments are gone, safe to reclaim
            print(f"  Project {project_id} deleted — all environments gone, reclaiming")
        except Exception as e:
            print(f"⚠️ Could not check project {project_id}: {e} — deferring reclaim to reconciler")
            return {'statusCode': 200, 'body': 'Deferred'}

        if remaining:
            print(f"⏳ {len(remaining)} environment(s) still active in {account_id}, not reclaiming yet")
            return {'statusCode': 200, 'body': f'{len(remaining)} envs remaining'}

        # All environments gone — reclaim the account
        print(f"♻️ All environments deleted from {account_id}, reclaiming...")
        response = dynamodb.query(
            TableName=DYNAMODB_TABLE_NAME,
            KeyConditionExpression='accountId = :a',
            ExpressionAttributeValues={':a': {'S': account_id}},
            ScanIndexForward=False, Limit=1
        )
        if not response.get('Items'):
            print(f"⏭️ Account {account_id} not in pool")
            return {'statusCode': 200, 'body': 'Not in pool'}

        item = response['Items'][0]
        # Read ReclaimStrategy from the account's pool config, fall back to global
        acct_pool = item.get('poolName', {}).get('S', '')
        pool_cfg = config.get('pools', {}).get(acct_pool, {})
        reclaim_strategy = pool_cfg.get('ReclaimStrategy') or config.get('ReclaimStrategy', 'REUSE')

        if reclaim_strategy == 'REUSE':
            return reclaim_account_reuse(account_id, item)
        else:
            return reclaim_account_delete(account_id, item, config)

    except Exception as e:
        print(f"❌ Error handling deletion: {e}")
        return {'statusCode': 500, 'body': str(e)}


def handle_force_replenishment(config: Dict[str, Any]) -> Dict[str, Any]:
    """Handle manual replenishment trigger. Accepts optional poolName in config."""
    pool_name = config.get('poolName')  # set by lambda_handler from event payload
    print(f"🔄 Force replenishment triggered (pool={pool_name or 'all'})")
    check_pool_size_and_replenish(config, target_pool=pool_name)
    return {'statusCode': 200, 'body': f'Replenishment triggered (pool={pool_name or "all"})'}


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

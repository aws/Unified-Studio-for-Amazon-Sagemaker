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
organizations = boto3.client('organizations')
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
        
        # Log critical cross-account parameters
        if 'OrgAdminRoleArn' in config:
            print(f"   ✅ OrgAdminRoleArn found: {config['OrgAdminRoleArn']}")
        else:
            print(f"   ⚠️ OrgAdminRoleArn NOT found")
            
        if 'ExternalId' in config:
            print(f"   ✅ ExternalId found: {config['ExternalId']}")
        else:
            print(f"   ⚠️ ExternalId NOT found")
        
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


def get_organizations_client(config: Dict[str, Any]):
    """Get Organizations client with cross-account role assumption if configured"""
    org_admin_role_arn = config.get('OrgAdminRoleArn')
    external_id = config.get('ExternalId')
    
    print(f"🔍 Cross-account role config check:")
    print(f"   OrgAdminRoleArn: {org_admin_role_arn}")
    print(f"   ExternalId: {external_id}")
    
    if org_admin_role_arn:
        print(f"🔐 Assuming cross-account role: {org_admin_role_arn}")
        try:
            # Assume role in Org Admin account
            assume_role_params = {
                'RoleArn': org_admin_role_arn,
                'RoleSessionName': 'AccountPoolFactory-PoolManager'
            }
            
            if external_id:
                assume_role_params['ExternalId'] = external_id
                print(f"   Using ExternalId: {external_id}")
            else:
                print(f"   ⚠️ No ExternalId provided!")
            
            print(f"   Calling sts.assume_role with params: {json.dumps({k: v for k, v in assume_role_params.items() if k != 'ExternalId'}, indent=2)}")
            
            response = sts.assume_role(**assume_role_params)
            
            credentials = response['Credentials']
            
            # Create Organizations client with assumed role credentials
            org_client = boto3.client(
                'organizations',
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken']
            )
            
            print(f"✅ Successfully assumed role in Org Admin account")
            print(f"   Session expires: {credentials['Expiration']}")
            return org_client
            
        except Exception as e:
            print(f"❌ Failed to assume cross-account role: {e}")
            print(f"   Error type: {type(e).__name__}")
            print("⚠️ Falling back to local Organizations client")
            return organizations
    else:
        print("ℹ️ No cross-account role configured, using local Organizations client")
        return organizations


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
    """Create multiple accounts in parallel"""
    timestamp = int(time.time())
    
    # Get Organizations client (with cross-account role if configured)
    org_client = get_organizations_client(config)
    
    for i in range(count):
        try:
            # Generate unique email and name
            email = f"{config['EmailPrefix']}+{timestamp}-{i}@{config['EmailDomain']}"
            name = f"{config['NamePrefix']}-{timestamp}-{i}"
            
            print(f"📧 Creating account {i+1}/{count}: {name} ({email})")
            
            # Create account via Organizations API
            response = org_client.create_account(
                Email=email,
                AccountName=name,
                RoleName='OrganizationAccountAccessRole',
                IamUserAccessToBilling='ALLOW'
            )
            
            request_id = response['CreateAccountStatus']['Id']
            print(f"✅ Account creation initiated: request_id={request_id}")
            
            # Wait for account creation to complete
            account_id = wait_for_account_creation(request_id, org_client)
            
            if account_id:
                # Move account to target OU if specified
                move_account_to_target_ou(account_id, config, org_client)
                
                # Create DynamoDB record
                create_account_record(account_id, request_id, name, email)
                
                # Wait for StackSet to deploy AccountPoolFactory-DomainAccess role
                wait_for_stackset_deployment(account_id, config)
                
                # Invoke Setup Orchestrator asynchronously
                invoke_setup_orchestrator(account_id, request_id)
                
                publish_metric('AccountCreationStarted', 1, [{'Name': 'AccountId', 'Value': account_id}])
            
        except Exception as e:
            print(f"❌ Error creating account {i+1}: {e}")
            continue


def wait_for_account_creation(request_id: str, org_client, timeout: int = 300) -> Optional[str]:
    """Wait for account creation to complete"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            response = org_client.describe_create_account_status(
                CreateAccountRequestId=request_id
            )
            
            status = response['CreateAccountStatus']
            state = status['State']
            
            if state == 'SUCCEEDED':
                account_id = status['AccountId']
                print(f"✅ Account created successfully: {account_id}")
                return account_id
            elif state == 'FAILED':
                reason = status.get('FailureReason', 'Unknown')
                print(f"❌ Account creation failed: {reason}")
                return None
            
            print(f"⏳ Account creation in progress... ({state})")
            time.sleep(5)
            
        except Exception as e:
            print(f"❌ Error checking account status: {e}")
            return None
    
    print(f"⏱️ Account creation timed out after {timeout} seconds")
    return None


def move_account_to_target_ou(account_id: str, config: Dict[str, Any], org_client):
    """Move account to target OU if specified"""
    target_ou_id = config.get('TargetOUId', 'root')
    
    if target_ou_id == 'root' or not target_ou_id:
        print(f"⏭️ Leaving account {account_id} in organization root")
        return
    
    try:
        # Get current parent
        response = org_client.list_parents(ChildId=account_id)
        if not response.get('Parents'):
            print(f"⚠️ No parent found for account {account_id}")
            return
        
        current_parent_id = response['Parents'][0]['Id']
        
        # Move account to target OU
        org_client.move_account(
            AccountId=account_id,
            SourceParentId=current_parent_id,
            DestinationParentId=target_ou_id
        )
        
        print(f"✅ Moved account {account_id} to OU {target_ou_id}")
        
    except Exception as e:
        print(f"⚠️ Failed to move account {account_id} to OU: {e}")


def update_account_trust_policy(account_id: str, config: Dict[str, Any], org_client):
    """Update OrganizationAccountAccessRole trust policy to allow Domain account access"""
    print(f"🔐 Updating trust policy for account {account_id}")
    
    domain_account_id = DOMAIN_ACCOUNT_ID
    
    try:
        # First assume the cross-account role in Org Admin account
        # This gives us Organizations permissions
        org_admin_role_arn = config.get('OrgAdminRoleArn')
        external_id = config.get('ExternalId')
        
        if not org_admin_role_arn:
            print(f"⚠️ No OrgAdminRoleArn configured, skipping trust policy update")
            return
        
        # Assume role in Org Admin account
        assume_role_params = {
            'RoleArn': org_admin_role_arn,
            'RoleSessionName': 'PoolManager-TrustUpdate'
        }
        if external_id:
            assume_role_params['ExternalId'] = external_id
        
        org_admin_creds = sts.assume_role(**assume_role_params)['Credentials']
        
        # Now use those credentials to assume OrganizationAccountAccessRole in the new account
        org_admin_sts = boto3.client(
            'sts',
            aws_access_key_id=org_admin_creds['AccessKeyId'],
            aws_secret_access_key=org_admin_creds['SecretAccessKey'],
            aws_session_token=org_admin_creds['SessionToken']
        )
        
        assumed_role = org_admin_sts.assume_role(
            RoleArn=f"arn:aws:iam::{account_id}:role/OrganizationAccountAccessRole",
            RoleSessionName='PoolManager-TrustUpdate'
        )
        
        credentials = assumed_role['Credentials']
        
        # Create IAM client with assumed role credentials
        iam_client = boto3.client(
            'iam',
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )
        
        # Build new trust policy that includes both Org Admin and Domain accounts
        role_name = 'OrganizationAccountAccessRole'
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
        
    except Exception as e:
        print(f"⚠️ Failed to update trust policy for account {account_id}: {e}")
        # Don't fail the entire account creation - Setup Orchestrator will handle this


def wait_for_stackset_deployment(account_id: str, config: Dict[str, Any], timeout: int = 300):
    """Wait for StackSet to deploy AccountPoolFactory-DomainAccess role to account"""
    print(f"⏳ Waiting for StackSet to deploy AccountPoolFactory-DomainAccess role to account {account_id}")
    
    # Get Organizations client with cross-account role
    org_client = get_organizations_client(config)
    
    stackset_name = "AccountPoolFactory-DomainAccessRole"
    start_time = time.time()
    check_interval = 10  # Check every 10 seconds
    
    while time.time() - start_time < timeout:
        try:
            # Check if stack instance exists and is in CURRENT state
            # We need to use the Org Admin account to check StackSet status
            org_admin_role_arn = config.get('OrgAdminRoleArn')
            external_id = config.get('ExternalId')
            
            if not org_admin_role_arn:
                print(f"⚠️ No OrgAdminRoleArn configured, skipping StackSet wait")
                return
            
            # Assume role in Org Admin account to check StackSet
            assume_role_params = {
                'RoleArn': org_admin_role_arn,
                'RoleSessionName': 'PoolManager-StackSetCheck'
            }
            if external_id:
                assume_role_params['ExternalId'] = external_id
            
            org_admin_creds = sts.assume_role(**assume_role_params)['Credentials']
            
            # Create CloudFormation client with Org Admin credentials
            cfn_client = boto3.client(
                'cloudformation',
                aws_access_key_id=org_admin_creds['AccessKeyId'],
                aws_secret_access_key=org_admin_creds['SecretAccessKey'],
                aws_session_token=org_admin_creds['SessionToken']
            )
            
            # Check stack instance status
            response = cfn_client.list_stack_instances(
                StackSetName=stackset_name,
                StackInstanceAccount=account_id,
                MaxResults=1
            )
            
            if response.get('Summaries'):
                instance = response['Summaries'][0]
                status = instance.get('Status')
                
                print(f"   StackSet instance status: {status}")
                
                if status == 'CURRENT':
                    elapsed = int(time.time() - start_time)
                    print(f"✅ StackSet deployed successfully to account {account_id} (took {elapsed}s)")
                    return
                elif status in ['FAILED', 'CANCELLED']:
                    print(f"❌ StackSet deployment failed with status: {status}")
                    print(f"   StatusReason: {instance.get('StatusReason', 'Unknown')}")
                    # Continue anyway - Setup Orchestrator will fail with better error
                    return
            else:
                print(f"   StackSet instance not found yet, waiting...")
            
            time.sleep(check_interval)
            
        except Exception as e:
            print(f"⚠️ Error checking StackSet status: {e}")
            time.sleep(check_interval)
    
    elapsed = int(time.time() - start_time)
    print(f"⏱️ StackSet deployment timed out after {elapsed}s")
    print(f"   Proceeding anyway - Setup Orchestrator will retry if needed")


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
    """Reclaim account using DELETE strategy"""
    print(f"🗑️ Reclaiming account {account_id} using DELETE strategy")
    
    # Get Organizations client (with cross-account role if configured)
    org_client = get_organizations_client(config)
    
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
        
        # Close account via Organizations API
        org_client.close_account(AccountId=account_id)
        
        print(f"✅ Account {account_id} closure initiated")
        
        # Delete DynamoDB record
        dynamodb.delete_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp']
            }
        )
        
        publish_metric('AccountDeleted', 1, [{'Name': 'AccountId', 'Value': account_id}])
        
        return {'statusCode': 200, 'body': 'Account deleted'}
        
    except Exception as e:
        print(f"❌ Error deleting account {account_id}: {e}")
        
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
    """Handle manual deletion of failed account"""
    print(f"🗑️ Deleting failed account {account_id}")
    
    # Get Organizations client (with cross-account role if configured)
    org_client = get_organizations_client(config)
    
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
        
        # Close account
        org_client.close_account(AccountId=account_id)
        
        # Delete DynamoDB record
        dynamodb.delete_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp']
            }
        )
        
        publish_metric('FailedAccountDeleted', 1, [{'Name': 'AccountId', 'Value': account_id}])
        
        print(f"✅ Failed account {account_id} deleted")
        
        return {'statusCode': 200, 'body': 'Failed account deleted'}
        
    except Exception as e:
        print(f"❌ Error deleting failed account: {e}")
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

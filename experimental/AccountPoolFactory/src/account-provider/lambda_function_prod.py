"""
Account Provider Lambda - Production Version
Queries DynamoDB for available accounts and returns them to DataZone.
Pool-aware: maps project profile name → pool name via SSM, then filters by pool.
"""

import json
import logging
import os
import boto3
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.client('dynamodb')
ssm = boto3.client('ssm')
cloudwatch = boto3.client('cloudwatch')
sns = boto3.client('sns')

TABLE_NAME = os.environ.get('TABLE_NAME', 'AccountPoolFactory-AccountState')
REGION = os.environ.get('AWS_REGION', 'us-east-2')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

# Cache: profile_name → pool_name (populated on first call)
_profile_to_pool_cache = None


def _load_profile_pool_mapping():
    """Build a mapping of project_profile_name → pool_name from SSM.
    Reads /AccountPoolFactory/Pools/{name}/ProjectProfileName for each pool.
    """
    global _profile_to_pool_cache
    if _profile_to_pool_cache is not None:
        return _profile_to_pool_cache

    mapping = {}
    try:
        resp = ssm.get_parameters_by_path(
            Path='/AccountPoolFactory/Pools/',
            Recursive=True,
            WithDecryption=False
        )
        for param in resp.get('Parameters', []):
            parts = param['Name'].split('/')
            # /AccountPoolFactory/Pools/{pool_name}/ProjectProfileName
            if len(parts) >= 5 and parts[4] == 'ProjectProfileName':
                pool_name = parts[3]
                profile_name = param['Value']
                mapping[profile_name] = pool_name
                logger.info(f"  Profile '{profile_name}' → pool '{pool_name}'")
    except Exception as e:
        logger.warning(f"Could not load profile→pool mapping from SSM: {e}")

    _profile_to_pool_cache = mapping
    logger.info(f"Profile→pool mapping: {mapping}")
    return mapping


def _extract_pool_name_from_event(event):
    """Extract pool name from the DataZone event context.

    DataZone passes context in the listAuthorizedAccountsRequest that may include
    projectProfileId or projectProfileName. We map that to a pool name via SSM.
    Returns pool_name or None (fall back to all pools).
    """
    op = event.get('operationRequest', {})
    req = op.get('listAuthorizedAccountsRequest') or {}
    if not isinstance(req, dict):
        req = {}

    # DataZone may pass context with projectProfileId or projectProfileName
    context = req.get('context', {}) or {}
    profile_name = context.get('projectProfileName') or context.get('projectProfile')
    profile_id = context.get('projectProfileId')

    if not profile_name and not profile_id:
        # Also check top-level event fields
        profile_name = event.get('projectProfileName')
        profile_id = event.get('projectProfileId')

    if not profile_name and not profile_id:
        return None

    mapping = _load_profile_pool_mapping()

    if profile_name and profile_name in mapping:
        return mapping[profile_name]

    # If we have a profile ID but not name, try to resolve via DataZone API
    if profile_id:
        try:
            dz = boto3.client('datazone', region_name=REGION)
            domain_id = os.environ.get('DOMAIN_ID', '')
            if domain_id:
                resp = dz.get_project_profile(
                    domainIdentifier=domain_id,
                    identifier=profile_id
                )
                resolved_name = resp.get('name', '')
                if resolved_name in mapping:
                    return mapping[resolved_name]
        except Exception as e:
            logger.warning(f"Could not resolve profile ID {profile_id}: {e}")

    return None  # Fall back to all pools

def lambda_handler(event, context):
    """
    Handle account pool requests from DataZone
    
    Expected event structure:
    {
        "operationRequest": {
            "listAuthorizedAccountsRequest": {} or
            "validateAccountAuthorizationRequest": {"awsAccountId": "...", "regionName": "..."}
        }
    }
    """
    
    logger.info("=" * 80)
    logger.info("🚀 Account Provider Lambda invoked")
    logger.info("=" * 80)
    logger.info(f"📥 Event: {json.dumps(event, indent=2)}")
    logger.info(f"📋 Context: request_id={context.aws_request_id}, function_name={context.function_name}")
    
    try:
        operation_request = event.get('operationRequest', {})
        
        if operation_request.get('validateAccountAuthorizationRequest'):
            logger.info("✅ ValidateAccountAuthorizationRequest received")
            response = validate_account_authorization(operation_request['validateAccountAuthorizationRequest'])
        elif operation_request.get('listAuthorizedAccountsRequest') is not None:
            logger.info("📋 ListAuthorizedAccountsRequest received")
            pool_name = _extract_pool_name_from_event(event)
            response = list_authorized_accounts(pool_name=pool_name)
        elif 'listAuthorizedAccountsRequest' in operation_request:
            logger.info("📋 ListAuthorizedAccountsRequest received (null payload)")
            pool_name = _extract_pool_name_from_event(event)
            response = list_authorized_accounts(pool_name=pool_name)
        else:
            error_msg = f"❌ Unsupported operation: {operation_request}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        logger.info("=" * 80)
        logger.info("✅ Returning response")
        logger.info("=" * 80)
        logger.info(f"📤 Response: {json.dumps(response, indent=2)}")
        
        return response
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error("❌ ERROR occurred in Account Provider Lambda")
        logger.error("=" * 80)
        logger.error(f"Error: {str(e)}", exc_info=True)
        
        # Send SNS alert
        if SNS_TOPIC_ARN:
            try:
                sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Subject="Account Provider Lambda Error",
                    Message=f"Error in Account Provider Lambda:\n\n{str(e)}\n\nEvent: {json.dumps(event, indent=2)}"
                )
            except Exception as sns_error:
                logger.error(f"Failed to send SNS alert: {sns_error}")
        
        raise

def list_authorized_accounts(pool_name=None):
    """Query DynamoDB for available accounts, optionally filtered by pool.

    If pool_name is given, uses PoolIndex GSI for efficient per-pool query.
    Falls back to StateIndex (all pools) if no pool_name or PoolIndex unavailable.
    """
    logger.info(f"🔍 Querying DynamoDB for AVAILABLE accounts (pool={pool_name or 'all'})...")

    try:
        if pool_name:
            # Use PoolIndex GSI: poolName PK, state SK
            try:
                response = dynamodb.query(
                    TableName=TABLE_NAME,
                    IndexName='PoolIndex',
                    KeyConditionExpression='poolName = :pool AND #state = :state',
                    ExpressionAttributeNames={'#state': 'state'},
                    ExpressionAttributeValues={
                        ':pool': {'S': pool_name},
                        ':state': {'S': 'AVAILABLE'},
                    },
                    Limit=100
                )
                logger.info(f"  Used PoolIndex GSI for pool={pool_name}")
            except Exception as e:
                logger.warning(f"PoolIndex query failed ({e}), falling back to StateIndex")
                pool_name = None  # fall through to StateIndex below

        if not pool_name:
            response = dynamodb.query(
                TableName=TABLE_NAME,
                IndexName='StateIndex',
                KeyConditionExpression='#state = :state',
                ExpressionAttributeNames={'#state': 'state'},
                ExpressionAttributeValues={':state': {'S': 'AVAILABLE'}},
                Limit=100
            )
        
        items = response.get('Items', [])
        logger.info(f"📊 Found {len(items)} AVAILABLE accounts")
        
        if len(items) == 0:
            logger.warning("⚠️  No available accounts in pool!")
            
            # Send SNS alert for pool depletion
            if SNS_TOPIC_ARN:
                try:
                    sns.publish(
                        TopicArn=SNS_TOPIC_ARN,
                        Subject="Account Pool Depleted",
                        Message="No available accounts in pool. Account Provider Lambda cannot return accounts to DataZone."
                    )
                except Exception as sns_error:
                    logger.error(f"Failed to send SNS alert: {sns_error}")
            
            # Publish CloudWatch metric
            try:
                cloudwatch.put_metric_data(
                    Namespace='AccountPoolFactory/AccountProvider',
                    MetricData=[
                        {
                            'MetricName': 'PoolDepleted',
                            'Value': 1,
                            'Unit': 'Count',
                            'Timestamp': datetime.utcnow()
                        }
                    ]
                )
            except Exception as cw_error:
                logger.error(f"Failed to publish CloudWatch metric: {cw_error}")
        
        # Convert DynamoDB items to account list
        accounts = []
        for item in items:
            account_id = item.get('accountId', {}).get('S')
            if account_id:
                accounts.append({
                    'awsAccountId': account_id,
                    'awsAccountName': f'DataZone-Pool-{account_id}',
                    'supportedRegions': [REGION]
                })
                logger.info(f"  ✅ Account: {account_id}")
        
        # Publish CloudWatch metric
        try:
            cloudwatch.put_metric_data(
                Namespace='AccountPoolFactory/AccountProvider',
                MetricData=[
                    {
                        'MetricName': 'AccountsReturned',
                        'Value': len(accounts),
                        'Unit': 'Count',
                        'Timestamp': datetime.utcnow()
                    }
                ]
            )
        except Exception as cw_error:
            logger.error(f"Failed to publish CloudWatch metric: {cw_error}")
        
        return {
            'operationResponse': {
                'listAuthorizedAccountsResponse': {
                    'items': accounts
                }
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error querying DynamoDB: {e}")
        raise

def _mark_assigned(account_id: str, item: dict):
    """Mark account as ASSIGNED in DynamoDB and trigger pool replenishment check."""
    import time
    from datetime import timezone
    try:
        dynamodb.update_item(
            TableName=TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp']
            },
            UpdateExpression='SET #state = :state, assignedDate = :date',
            ConditionExpression='#state = :available',  # idempotent — only update if still AVAILABLE
            ExpressionAttributeNames={'#state': 'state'},
            ExpressionAttributeValues={
                ':state': {'S': 'ASSIGNED'},
                ':available': {'S': 'AVAILABLE'},
                ':date': {'S': datetime.now(timezone.utc).isoformat()}
            }
        )
        logger.info(f"✅ Account {account_id} marked as ASSIGNED")

        # Trigger PoolManager to check pool size and replenish if needed
        try:
            lambda_client = boto3.client('lambda', region_name=REGION)
            lambda_client.invoke(
                FunctionName='PoolManager',
                InvocationType='Event',
                Payload=json.dumps({'action': 'force_replenishment'}).encode()
            )
            logger.info("✅ PoolManager replenishment triggered")
        except Exception as e:
            logger.warning(f"⚠️  Could not trigger PoolManager: {e}")

    except dynamodb.exceptions.ConditionalCheckFailedException:
        logger.info(f"ℹ️  Account {account_id} already assigned (concurrent request)")
    except Exception as e:
        logger.error(f"❌ Failed to mark account {account_id} as ASSIGNED: {e}")


def validate_account_authorization(request):
    """Validate if account/region pair is authorized.

    Also verifies the account's poolName matches the requesting project profile's pool.
    """
    account_id = request.get('awsAccountId')
    region = request.get('regionName')
    context = request.get('context', {}) or {}

    logger.info(f"🔍 Validating account: {account_id}, region: {region}")

    # Determine expected pool from context (if provided)
    expected_pool = None
    profile_name = context.get('projectProfileName') or context.get('projectProfile')
    if profile_name:
        mapping = _load_profile_pool_mapping()
        expected_pool = mapping.get(profile_name)
        logger.info(f"  Expected pool for profile '{profile_name}': {expected_pool}")

    try:
        response = dynamodb.query(
            TableName=TABLE_NAME,
            KeyConditionExpression='accountId = :accountId',
            ExpressionAttributeValues={':accountId': {'S': account_id}},
            ScanIndexForward=False,
            Limit=1
        )

        items = response.get('Items', [])

        if not items:
            logger.warning(f"⚠️  Account {account_id} not found in pool")
            auth_result = 'DENY'
        else:
            item = items[0]
            state = item.get('state', {}).get('S')
            acct_pool = item.get('poolName', {}).get('S', '')

            # Pool check: if we know the expected pool, verify it matches
            pool_ok = True
            if expected_pool and acct_pool and acct_pool != expected_pool:
                logger.warning(f"  Pool mismatch: account pool={acct_pool}, expected={expected_pool}")
                pool_ok = False

            if state in ('AVAILABLE', 'ASSIGNED') and region == REGION and pool_ok:
                auth_result = 'GRANT'
                logger.info(f"✅ Authorization GRANTED for {account_id} in {region} (state={state}, pool={acct_pool})")
                if state == 'AVAILABLE':
                    _mark_assigned(account_id, item)
            else:
                auth_result = 'DENY'
                logger.info(f"❌ Authorization DENIED for {account_id} in {region} (state={state}, pool={acct_pool}, pool_ok={pool_ok})")

        return {
            'operationResponse': {
                'validateAccountAuthorizationResponse': {
                    'authResult': auth_result
                }
            }
        }

    except Exception as e:
        logger.error(f"❌ Error validating account: {e}")
        return {
            'operationResponse': {
                'validateAccountAuthorizationResponse': {
                    'authResult': 'DENY'
                }
            }
        }

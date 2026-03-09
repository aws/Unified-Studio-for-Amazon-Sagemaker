"""
Account Provider Lambda - Production Version
Queries DynamoDB for available accounts and returns them to DataZone
"""

import json
import logging
import os
import boto3
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.client('dynamodb')
cloudwatch = boto3.client('cloudwatch')
sns = boto3.client('sns')

# Configuration from environment variables
TABLE_NAME = os.environ.get('TABLE_NAME', 'AccountPoolFactory-AccountState')
REGION = os.environ.get('AWS_REGION', 'us-east-2')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

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
            response = list_authorized_accounts()
        elif 'listAuthorizedAccountsRequest' in operation_request:
            # listAuthorizedAccountsRequest is null but key exists — treat as list request
            logger.info("📋 ListAuthorizedAccountsRequest received (null payload)")
            response = list_authorized_accounts()
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

def list_authorized_accounts():
    """Query DynamoDB for available accounts and return them"""
    logger.info("🔍 Querying DynamoDB for AVAILABLE accounts...")
    
    try:
        # Query StateIndex GSI for AVAILABLE accounts
        response = dynamodb.query(
            TableName=TABLE_NAME,
            IndexName='StateIndex',
            KeyConditionExpression='#state = :state',
            ExpressionAttributeNames={
                '#state': 'state'
            },
            ExpressionAttributeValues={
                ':state': {'S': 'AVAILABLE'}
            },
            Limit=100  # Return up to 100 available accounts
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
    """Validate if account/region pair is authorized"""
    account_id = request.get('awsAccountId')
    region = request.get('regionName')
    
    logger.info(f"🔍 Validating account: {account_id}, region: {region}")
    
    try:
        # Query DynamoDB for this specific account
        response = dynamodb.query(
            TableName=TABLE_NAME,
            KeyConditionExpression='accountId = :accountId',
            ExpressionAttributeValues={
                ':accountId': {'S': account_id}
            },
            ScanIndexForward=False,  # Get most recent record
            Limit=1
        )
        
        items = response.get('Items', [])
        
        if len(items) == 0:
            logger.warning(f"⚠️  Account {account_id} not found in pool")
            auth_result = 'DENY'
        else:
            item = items[0]
            state = item.get('state', {}).get('S')
            
            # Account must be AVAILABLE or ASSIGNED (already being assigned to this project)
            if state in ('AVAILABLE', 'ASSIGNED') and region == REGION:
                auth_result = 'GRANT'
                logger.info(f"✅ Authorization GRANTED for {account_id} in {region} (state: {state})")
                # Mark ASSIGNED on first AVAILABLE grant
                if state == 'AVAILABLE':
                    _mark_assigned(account_id, item)
            else:
                auth_result = 'DENY'
                logger.info(f"❌ Authorization DENIED for {account_id} in {region} (state: {state})")
        
        return {
            'operationResponse': {
                'validateAccountAuthorizationResponse': {
                    'authResult': auth_result
                }
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error validating account: {e}")
        # Default to DENY on error
        return {
            'operationResponse': {
                'validateAccountAuthorizationResponse': {
                    'authResult': 'DENY'
                }
            }
        }

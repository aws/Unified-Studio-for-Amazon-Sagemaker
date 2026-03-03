import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Hardcoded test account
TEST_ACCOUNT = {
    "awsAccountId": "004878717744",
    "awsAccountName": "TestAccount-100",
    "supportedRegions": ["us-east-2", "us-east-1"]
}

def lambda_handler(event, context):
    """
    Handle account pool requests from DataZone
    
    Expected event structure:
    {
        "operationRequest": {
            "listAuthorizedAccountsRequest": {} or
            "validateAccountAuthorizationRequest": {"awsAccountId": "...", "awsRegion": "..."}
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
        
        if 'listAuthorizedAccountsRequest' in operation_request and operation_request['listAuthorizedAccountsRequest'] is not None:
            logger.info("📋 ListAuthorizedAccountsRequest received")
            response = list_authorized_accounts()
        elif 'validateAccountAuthorizationRequest' in operation_request and operation_request['validateAccountAuthorizationRequest'] is not None:
            logger.info("✅ ValidateAccountAuthorizationRequest received")
            response = validate_account_authorization(operation_request['validateAccountAuthorizationRequest'])
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
        raise

def list_authorized_accounts():
    """Return list of authorized accounts"""
    return {
        'operationResponse': {
            'listAuthorizedAccountsResponse': {
                'items': [TEST_ACCOUNT]
            }
        }
    }

def validate_account_authorization(request):
    """Validate if account/region pair is authorized"""
    account_id = request.get('awsAccountId')
    region = request.get('regionName')  # Fixed: use 'regionName' not 'awsRegion'
    
    logger.info(f"🔍 Validating account: {account_id}, region: {region}")
    
    # Check if requested account matches our test account
    if account_id == TEST_ACCOUNT['awsAccountId'] and region in TEST_ACCOUNT['supportedRegions']:
        auth_result = 'GRANT'
        logger.info(f"✅ Authorization GRANTED for {account_id} in {region}")
    else:
        auth_result = 'DENY'
        logger.info(f"❌ Authorization DENIED for {account_id} in {region}")
    
    return {
        'operationResponse': {
            'validateAccountAuthorizationResponse': {
                'authResult': auth_result
            }
        }
    }

"""
ProvisionAccount Lambda Function

Runs in Domain Account (994753223772) — moved from Org Admin account.
On entry, assumes the AccountCreation cross-account role in the Org Admin account,
then uses those temporary credentials for all Organizations and StackSet API calls.

Responsibilities:
1. Assume AccountCreation role in Org Admin account (via STS)
2. Create account via Organizations API (using assumed role)
3. Move account to target OU
4. Deploy StackSet execution role to new account (via OrganizationAccountAccessRole)
5. Deploy TrustPolicy StackSet (creates SMUS-AccountPoolFactory-DomainAccess role)
6. Wait for StackSet completion
7. Return ready-to-use account ID

Security:
- AccountCreation role is protected by ExternalId
- OrganizationAccountAccessRole assumption is done from the assumed AccountCreation session
- No Organizations/StackSet API calls are made with the Lambda's own credentials
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError

# STS client — uses Lambda's own role, only for the initial assume_role call
sts = boto3.client('sts')

# Constants
REGION = os.environ.get('AWS_REGION_NAME', 'us-east-2')
DOMAIN_ACCESS_STACKSET_NAME = 'SMUS-AccountPoolFactory-DomainAccess'

# Environment variables (set by CloudFormation)
ACCOUNT_CREATION_ROLE_ARN = os.environ.get('ACCOUNT_CREATION_ROLE_ARN', '')
EXTERNAL_ID = os.environ.get('EXTERNAL_ID', '')


def _get_org_clients():
    """Assume the AccountCreation role in Org Admin and return (organizations, cloudformation, sts) clients.

    Called at the start of every handler path that needs to touch Organizations or StackSets.
    Returns fresh temporary credentials each invocation to avoid expiry issues.
    """
    if not ACCOUNT_CREATION_ROLE_ARN or not EXTERNAL_ID:
        raise Exception(
            'ACCOUNT_CREATION_ROLE_ARN and EXTERNAL_ID environment variables must be set'
        )

    assumed = sts.assume_role(
        RoleArn=ACCOUNT_CREATION_ROLE_ARN,
        RoleSessionName='ProvisionAccount',
        ExternalId=EXTERNAL_ID,
        DurationSeconds=3600
    )
    creds = assumed['Credentials']
    kwargs = dict(
        aws_access_key_id=creds['AccessKeyId'],
        aws_secret_access_key=creds['SecretAccessKey'],
        aws_session_token=creds['SessionToken']
    )
    org_client = boto3.client('organizations', **kwargs)
    cf_client = boto3.client('cloudformation', region_name=REGION, **kwargs)
    sts_client = boto3.client('sts', **kwargs)
    return org_client, cf_client, sts_client


def lambda_handler(event, context):
    """Main Lambda handler for ProvisionAccount"""
    print(f"📥 Received event: {json.dumps(event, indent=2)}")

    action = event.get('action')

    # Assume AccountCreation role once per invocation — all downstream functions use these clients
    try:
        organizations, cloudformation, assumed_sts = _get_org_clients()
    except Exception as e:
        return {'status': 'ERROR', 'message': f'Failed to assume AccountCreation role: {e}'}

    if action == 'provision':
        return provision_account(event, organizations, cloudformation, assumed_sts)
    elif action == 'fixStackSet':
        return fix_stackset(event, organizations, cloudformation, assumed_sts)
    elif action == 'fixStackSetBatch':
        return fix_stackset_batch(event, organizations, cloudformation, assumed_sts)
    else:
        return {
            'status': 'ERROR',
            'message': f'Unknown action: {action}'
        }

def fix_stackset_batch(event: Dict[str, Any], organizations, cloudformation, assumed_sts) -> Dict[str, Any]:
    """Deploy DomainAccess StackSet instances for multiple accounts in one operation.

    Uses a single create_stack_instances call with all account IDs to avoid
    OperationInProgressException from concurrent single-account calls.

    Steps:
    1. Deploy StackSetExecution role to each account sequentially (required before StackSet)
    2. Single create_stack_instances call with all accounts
    3. Wait for the operation to complete
    """
    account_ids = event.get('accountIds', [])
    domain_id = event.get('domainId')
    domain_account_id = event.get('domainAccountId')

    if not account_ids or not domain_id or not domain_account_id:
        return {'status': 'ERROR', 'message': 'Missing required: accountIds, domainId, domainAccountId'}

    print(f"🔧 Batch StackSet fix for {len(account_ids)} accounts")
    org_admin_account_id = assumed_sts.get_caller_identity()['Account']

    # Step 1: Deploy StackSetExecution role to each account (sequential — uses OrganizationAccountAccessRole)
    failed_execution_role = []
    for account_id in account_ids:
        try:
            print(f"   Step 1: StackSetExecution role → {account_id}")
            deploy_stackset_execution_role(account_id, org_admin_account_id, assumed_sts, cloudformation)
        except Exception as e:
            print(f"   ⚠️  StackSetExecution role failed for {account_id}: {e}")
            failed_execution_role.append(account_id)

    # Only proceed with accounts that got the execution role
    ready_accounts = [a for a in account_ids if a not in failed_execution_role]
    if not ready_accounts:
        return {'status': 'ERROR', 'message': 'All accounts failed StackSetExecution role deployment'}

    # Step 2: Wait for any in-progress StackSet operation, then batch create
    print(f"   Step 2: Waiting for any in-progress StackSet operation...")
    _wait_for_any_stackset_operation(DOMAIN_ACCESS_STACKSET_NAME, cloudformation, timeout=300)

    print(f"   Step 2: create_stack_instances for {len(ready_accounts)} accounts...")
    try:
        response = cloudformation.create_stack_instances(
            StackSetName=DOMAIN_ACCESS_STACKSET_NAME,
            Accounts=ready_accounts,
            Regions=[REGION],
            OperationPreferences={
                'FailureToleranceCount': len(ready_accounts),  # tolerate partial failures
                'MaxConcurrentCount': 5
            }
        )
        operation_id = response['OperationId']
        print(f"   Operation ID: {operation_id}")

        # Step 3: Wait for the batch operation to complete
        # Use a longer timeout — batch of N accounts takes N * ~30s
        timeout = min(300 + len(ready_accounts) * 30, 840)
        wait_for_stackset_operation(DOMAIN_ACCESS_STACKSET_NAME, operation_id,
                                    ready_accounts[0], cloudformation, timeout=timeout)
        print(f"✅ Batch StackSet operation complete for {len(ready_accounts)} accounts")

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'OperationInProgressException':
            # Still busy — caller will retry on next recycler wave
            return {'status': 'ERROR', 'message': f'StackSet still busy: {e}'}
        raise

    return {
        'status': 'SUCCESS',
        'accountIds': ready_accounts,
        'failedExecutionRole': failed_execution_role,
        'message': f'StackSet deployed to {len(ready_accounts)} accounts'
    }


def fix_stackset(event: Dict[str, Any], organizations, cloudformation, assumed_sts) -> Dict[str, Any]:
    """Deploy DomainAccess StackSet instance for an existing account.

    Called by the Reconciler when it finds a pool account missing the
    SMUS-AccountPoolFactory-DomainAccess role. This handles accounts
    that were created before the StackSet was set up, or where the
    StackSet instance was never deployed.

    Two-step process:
    1. Deploy StackSetExecution role via OrganizationAccountAccessRole
       (needed for SELF_MANAGED StackSets to operate in the target account)
    2. Deploy DomainAccess StackSet instance
    """
    account_id = event.get('accountId')
    domain_id = event.get('domainId')
    domain_account_id = event.get('domainAccountId')

    if not all([account_id, domain_id, domain_account_id]):
        return {
            'status': 'ERROR',
            'message': 'Missing required parameters: accountId, domainId, domainAccountId'
        }

    print(f"🔧 Fixing StackSet for account {account_id}")

    try:
        # Get the Org Admin account ID from the assumed role session
        org_admin_account_id = assumed_sts.get_caller_identity()['Account']

        # Step 1: Ensure StackSetExecution role exists in target account
        print(f"   Step 1: Deploying StackSetExecution role...")
        deploy_stackset_execution_role(account_id, org_admin_account_id, assumed_sts, cloudformation)

        # Step 2: Deploy DomainAccess StackSet instance
        print(f"   Step 2: Deploying DomainAccess StackSet instance...")
        deploy_domain_access_role_stackset(account_id, domain_id, domain_account_id, cloudformation)

        print(f"✅ StackSet instance deployed for {account_id}")
        return {
            'status': 'SUCCESS',
            'accountId': account_id,
            'message': 'StackSet instance deployed'
        }
    except Exception as e:
        print(f"❌ StackSet fix failed for {account_id}: {e}")
        return {
            'status': 'ERROR',
            'accountId': account_id,
            'message': str(e)
        }



def provision_account(event: Dict[str, Any], organizations, cloudformation, assumed_sts) -> Dict[str, Any]:
    """Provision a new account with proper role setup"""
    
    # Extract parameters
    account_name = event.get('accountName')
    account_email = event.get('accountEmail')
    ou_id = event.get('ouId')
    domain_id = event.get('domainId')
    domain_account_id = event.get('domainAccountId')

    # org_admin_account_id comes from the assumed AccountCreation role session
    org_admin_account_id = assumed_sts.get_caller_identity()['Account']

    # Validate required parameters
    if not all([account_name, account_email, ou_id, domain_id, domain_account_id]):
        return {
            'status': 'ERROR',
            'message': 'Missing required parameters'
        }
    
    print(f"🚀 Provisioning account: {account_name}")
    print(f"   Email: {account_email}")
    print(f"   Target OU: {ou_id}")
    print(f"   Domain ID: {domain_id}")
    print(f"   Domain Account: {domain_account_id}")
    
    try:
        # Step 1: Create account
        print("Step 1: Creating account via Organizations API...")
        account_id = create_account(account_name, account_email, organizations)
        print(f"   Account created: {account_id}")

        # Step 1b: Tag account for reconciliation tracking
        pool_name = event.get('poolName', 'AccountPoolFactory')
        try:
            organizations.tag_resource(
                ResourceId=account_id,
                Tags=[
                    {'Key': 'ManagedBy', 'Value': 'AccountPoolFactory'},
                    {'Key': 'PoolName', 'Value': pool_name}
                ]
            )
            print(f"   Tagged account {account_id} with ManagedBy=AccountPoolFactory, PoolName={pool_name}")
        except Exception as tag_error:
            print(f"   Warning: Failed to tag account {account_id}: {tag_error}")

        # Step 2: Move account to target OU
        print(f"📦 Step 2: Moving account to target OU...")
        move_account_to_ou(account_id, ou_id, organizations)
        print(f"   ✅ Account moved to OU: {ou_id}")

        # Step 3: Deploy StackSet execution role
        print(f"🔧 Step 3: Deploying StackSet execution role...")
        deploy_stackset_execution_role(account_id, org_admin_account_id, assumed_sts, cloudformation)
        print(f"   ✅ StackSet execution role deployed")

        # Step 4: Deploy SMUS-AccountPoolFactory-DomainAccess role via StackSet
        print(f"🔐 Step 4: Deploying SMUS-AccountPoolFactory-DomainAccess role...")
        deploy_domain_access_role_stackset(account_id, domain_id, domain_account_id, cloudformation)
        print(f"   ✅ SMUS-AccountPoolFactory-DomainAccess role deployed")
        
        # Step 5: Wait for IAM role propagation
        print(f"⏳ Step 5: Waiting for IAM role propagation...")
        time.sleep(10)
        print(f"   ✅ IAM roles ready")
        
        print(f"✅ Account provisioning complete: {account_id}")
        
        return {
            'status': 'SUCCESS',
            'accountId': account_id,
            'message': 'Account provisioned and ready for configuration'
        }
        
    except Exception as e:
        print(f"❌ Account provisioning failed: {e}")
        return {
            'status': 'ERROR',
            'message': str(e),
            'accountId': account_id if 'account_id' in locals() else None
        }


def create_account(account_name: str, account_email: str, organizations) -> str:
    """Create account via Organizations API and wait for completion
    
    Handles EMAIL_ALREADY_EXISTS by finding the existing account with that email.
    This can happen when:
    - Previous creation attempt failed partway through
    - Retry with same email after partial failure
    - Account exists but wasn't tracked properly
    """
    
    try:
        # Try to create account
        response = organizations.create_account(
            AccountName=account_name,
            Email=account_email,
            RoleName='OrganizationAccountAccessRole',
            IamUserAccessToBilling='ALLOW'
        )
        
        request_id = response['CreateAccountStatus']['Id']
        print(f"   Account creation request ID: {request_id}")
        
        # Wait for account creation to complete
        max_wait = 300  # 5 minutes
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status_response = organizations.describe_create_account_status(
                CreateAccountRequestId=request_id
            )
            
            status = status_response['CreateAccountStatus']['State']
            print(f"   Account creation status: {status}")
            
            if status == 'SUCCEEDED':
                account_id = status_response['CreateAccountStatus']['AccountId']
                return account_id
            elif status == 'FAILED':
                failure_reason = status_response['CreateAccountStatus'].get('FailureReason', 'Unknown')
                
                # Handle EMAIL_ALREADY_EXISTS by finding the existing account
                if 'EMAIL_ALREADY_EXISTS' in failure_reason:
                    print(f"   ⚠️  Email {account_email} already exists, searching for existing account...")
                    
                    try:
                        # List all accounts and find the one with matching email
                        paginator = organizations.get_paginator('list_accounts')
                        for page in paginator.paginate():
                            for account in page['Accounts']:
                                if account['Email'] == account_email:
                                    account_id = account['Id']
                                    account_status = account['Status']
                                    
                                    if account_status == 'ACTIVE':
                                        print(f"   ✅ Found existing ACTIVE account: {account_id}")
                                        return account_id
                                    else:
                                        raise Exception(f"Found account {account_id} but status is {account_status}, not ACTIVE")
                        
                        # If we get here, email exists but we couldn't find the account
                        raise Exception(f"Email {account_email} exists but account not found in organization")
                        
                    except Exception as search_error:
                        raise Exception(f"EMAIL_ALREADY_EXISTS but failed to find account: {search_error}")
                
                raise Exception(f"Account creation failed: {failure_reason}")
            
            time.sleep(10)
        
        raise Exception(f"Account creation timed out after {max_wait} seconds")
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_message = e.response.get('Error', {}).get('Message', '')
        
        if error_code == 'EmailAlreadyExistsException' or 'EMAIL_ALREADY_EXISTS' in error_message:
            # Email already exists - find the account with this email
            print(f"   ⚠️  Email {account_email} already exists, searching for existing account...")
            
            try:
                # List all accounts and find the one with matching email
                paginator = organizations.get_paginator('list_accounts')
                for page in paginator.paginate():
                    for account in page['Accounts']:
                        if account['Email'] == account_email:
                            account_id = account['Id']
                            account_status = account['Status']
                            
                            if account_status == 'ACTIVE':
                                print(f"   ✅ Found existing ACTIVE account: {account_id}")
                                return account_id
                            else:
                                raise Exception(f"Found account {account_id} but status is {account_status}, not ACTIVE")
                
                # If we get here, email exists but we couldn't find the account
                raise Exception(f"Email {account_email} exists but account not found in organization")
                
            except Exception as search_error:
                raise Exception(f"EMAIL_ALREADY_EXISTS but failed to find account: {search_error}")
        else:
            # Other error, re-raise
            raise


def move_account_to_ou(account_id: str, target_ou_id: str, organizations):
    """Move account from root to target OU (idempotent)"""
    
    # Get current parent
    parents = organizations.list_parents(ChildId=account_id)
    
    if not parents['Parents']:
        raise Exception(f"Account {account_id} has no parent")
    
    source_parent_id = parents['Parents'][0]['Id']
    
    # Check if already in target OU
    if source_parent_id == target_ou_id:
        print(f"   ✅ Account already in target OU: {target_ou_id}")
        return
    
    # Move account to target OU
    try:
        organizations.move_account(
            AccountId=account_id,
            SourceParentId=source_parent_id,
            DestinationParentId=target_ou_id
        )
        print(f"   Moved account from {source_parent_id} to {target_ou_id}")
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'DuplicateAccountException':
            # Account already in target OU (race condition)
            print(f"   ✅ Account already in target OU: {target_ou_id}")
        else:
            raise


def wait_for_role_availability(account_id: str, assumed_sts, max_wait: int = 120):
    """Wait for OrganizationAccountAccessRole to become available in new account
    
    New AWS accounts need 30-60 seconds after creation before IAM roles can be assumed.
    This function polls until the role is available or timeout is reached.
    """
    role_arn = f"arn:aws:iam::{account_id}:role/OrganizationAccountAccessRole"
    
    print(f"   ⏳ Waiting for OrganizationAccountAccessRole to become available...")
    print(f"      Account: {account_id}")
    print(f"      Max wait: {max_wait} seconds")
    
    start_time = time.time()
    attempt = 0
    
    while time.time() - start_time < max_wait:
        attempt += 1
        elapsed = int(time.time() - start_time)
        
        try:
            # Try to assume the role using the AccountCreation session
            assumed_sts.assume_role(
                RoleArn=role_arn,
                RoleSessionName='ProvisionAccount-RoleCheck',
                DurationSeconds=900
            )
            
            elapsed_final = int(time.time() - start_time)
            print(f"   ✅ Role available after {elapsed_final} seconds ({attempt} attempts)")
            return
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            
            if error_code in ['InvalidClientTokenId', 'AccessDenied']:
                # Role not ready yet, keep waiting
                if attempt % 6 == 0:  # Log every 30 seconds (6 attempts * 5 sec)
                    print(f"      Attempt {attempt} ({elapsed}s): Role not ready yet, continuing...")
                time.sleep(5)
                continue
            else:
                # Unexpected error
                raise Exception(f"Unexpected error checking role availability: {e}")
    
    raise Exception(f"Role did not become available after {max_wait} seconds")


def deploy_stackset_execution_role(account_id: str, org_admin_account_id: str, assumed_sts, cloudformation):
    """Deploy StackSet execution role directly to new account using CloudFormation"""
    
    stack_name = 'SMUS-AccountPoolFactory-StackSetExecutionRole'
    
    # CloudFormation template for StackSet execution role
    template_body = f"""
AWSTemplateFormatVersion: '2010-09-09'
Description: 'StackSet Execution Role for Account Pool Factory'

Resources:
  StackSetExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: SMUS-AccountPoolFactory-StackSetExecution
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              AWS: arn:aws:iam::{org_admin_account_id}:role/SMUS-AccountPoolFactory-StackSetAdmin
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/AdministratorAccess

Outputs:
  ExecutionRoleArn:
    Description: ARN of the StackSet Execution Role
    Value: !GetAtt StackSetExecutionRole.Arn
"""
    
    # Wait for OrganizationAccountAccessRole to become available
    wait_for_role_availability(account_id, assumed_sts, max_wait=120)
    
    # Retry loop for CloudFormation stack creation
    # New accounts sometimes need extra time for CloudFormation service to recognize credentials
    max_retries = 5
    retry_delay = 30  # Start with 30 seconds
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"   🔐 Assuming OrganizationAccountAccessRole in account {account_id} (attempt {attempt}/{max_retries})")
            
            # Assume OrganizationAccountAccessRole in new account using the AccountCreation session
            role_arn = f"arn:aws:iam::{account_id}:role/OrganizationAccountAccessRole"
            
            assumed_role = assumed_sts.assume_role(
                RoleArn=role_arn,
                RoleSessionName='ProvisionAccount-StackSetRole'
            )
            
            credentials = assumed_role['Credentials']
            
            # Create CloudFormation client with assumed role credentials
            cf_client = boto3.client(
                'cloudformation',
                region_name=REGION,
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken']
            )
            
            # Check if stack already exists
            try:
                existing_stacks = cf_client.describe_stacks(StackName=stack_name)
                if existing_stacks['Stacks']:
                    stack_status = existing_stacks['Stacks'][0]['StackStatus']
                    if stack_status == 'CREATE_COMPLETE':
                        print(f"   ✅ Stack already exists: {stack_name}")
                        return  # Success!
                    else:
                        print(f"   ⚠️  Stack exists with status: {stack_status}")
            except ClientError as check_error:
                if 'does not exist' not in str(check_error):
                    raise
            
            # Create stack
            print(f"   📦 Creating CloudFormation stack: {stack_name}")
            
            cf_client.create_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Capabilities=['CAPABILITY_NAMED_IAM'],
                OnFailure='ROLLBACK',
                TimeoutInMinutes=10,
                Tags=[
                    {'Key': 'ManagedBy', 'Value': 'AccountPoolFactory'},
                    {'Key': 'AccountId', 'Value': account_id}
                ]
            )
            
            # Wait for stack creation to complete
            wait_for_stack_complete(cf_client, stack_name, timeout=300)
            
            print(f"   ✅ Stack created: {stack_name}")
            return  # Success!
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_msg = str(e)
            
            # Both OptInRequired and InvalidClientTokenId are timing issues with new accounts
            if error_code in ['OptInRequired', 'InvalidClientTokenId'] and attempt < max_retries:
                # CloudFormation service not ready yet, retry with backoff
                print(f"   ⏳ CloudFormation not ready yet ({error_code}, attempt {attempt}/{max_retries}), waiting {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 120)  # Exponential backoff, max 120s
                continue
            else:
                # Other error or max retries reached
                raise
    
    raise Exception(f"Failed to create stack after {max_retries} attempts")


def deploy_domain_access_role_stackset(account_id: str, domain_id: str, domain_account_id: str, cloudformation):
    """Deploy StackSet to create SMUS-AccountPoolFactory-DomainAccess role with ExternalId protection"""
    
    print(f"   📦 Checking StackSet instance for account {account_id}")
    
    # Check if StackSet instance already exists
    try:
        response = cloudformation.list_stack_instances(
            StackSetName=DOMAIN_ACCESS_STACKSET_NAME,
            StackInstanceAccount=account_id,
            StackInstanceRegion=REGION
        )
        
        if response.get('Summaries'):
            instance = response['Summaries'][0]
            status = instance.get('Status')
            
            if status == 'CURRENT':
                print(f"   ✅ StackSet instance already exists and is current")
                return
            elif status == 'OUTDATED':
                print(f"   🔄 StackSet instance exists but is outdated, updating...")
                # Update will happen via create_stack_instances with existing instance
            else:
                print(f"   ⚠️  StackSet instance exists with status: {status}")
                # Continue to create/update
    except ClientError as e:
        if 'StackInstanceNotFoundException' not in str(e):
            # Unexpected error
            raise
        # Instance doesn't exist, will create it
        print(f"   📦 Creating new StackSet instance")
    
    # Create or update stack instance in the target account
    try:
        response = cloudformation.create_stack_instances(
            StackSetName=DOMAIN_ACCESS_STACKSET_NAME,
            Accounts=[account_id],
            Regions=[REGION],
            OperationPreferences={
                'FailureToleranceCount': 0,
                'MaxConcurrentCount': 1
            }
        )
        
        operation_id = response['OperationId']
        print(f"   Operation ID: {operation_id}")
        
        # Wait for StackSet instance creation to complete
        wait_for_stackset_operation(DOMAIN_ACCESS_STACKSET_NAME, operation_id, account_id, cloudformation, timeout=180)
        
        print(f"   ✅ StackSet instance deployed successfully")
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')

        if error_code == 'OperationInProgressException':
            # Another StackSet operation is running (likely for a different account).
            # Wait for it to finish, then retry create_stack_instances for THIS account.
            print(f"   ⏳ StackSet operation in progress, waiting for it to finish...")
            _wait_for_any_stackset_operation(DOMAIN_ACCESS_STACKSET_NAME, cloudformation, timeout=180)

            # Retry once — the StackSet is now free
            print(f"   🔄 Retrying create_stack_instances for {account_id}...")
            try:
                response = cloudformation.create_stack_instances(
                    StackSetName=DOMAIN_ACCESS_STACKSET_NAME,
                    Accounts=[account_id],
                    Regions=[REGION],
                    OperationPreferences={
                        'FailureToleranceCount': 0,
                        'MaxConcurrentCount': 1
                    }
                )
                operation_id = response['OperationId']
                wait_for_stackset_operation(DOMAIN_ACCESS_STACKSET_NAME, operation_id, account_id, cloudformation, timeout=180)
                print(f"   ✅ StackSet instance deployed successfully (after retry)")
            except ClientError as e2:
                # If it already exists now (race condition resolved), that's fine
                if 'already exists' in str(e2).lower():
                    print(f"   ✅ StackSet instance already exists")
                else:
                    raise
        else:
            raise


def wait_for_stack_complete(cf_client, stack_name: str, timeout: int = 300):
    """Wait for CloudFormation stack to complete"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            response = cf_client.describe_stacks(StackName=stack_name)
            status = response['Stacks'][0]['StackStatus']
            
            if status == 'CREATE_COMPLETE':
                return
            elif status in ['CREATE_FAILED', 'ROLLBACK_COMPLETE', 'ROLLBACK_FAILED']:
                raise Exception(f"Stack creation failed with status: {status}")
            
            print(f"   ⏳ Stack status: {status}")
            time.sleep(10)
            
        except ClientError as e:
            if 'does not exist' in str(e):
                time.sleep(5)
            else:
                raise
    
    raise Exception(f"Stack creation timed out after {timeout} seconds")


def _wait_for_any_stackset_operation(stackset_name: str, cloudformation, timeout: int = 180):
    """Wait until no StackSet operation is in progress (any operation, any account).
    Used to serialize concurrent create_stack_instances calls."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = cloudformation.list_stack_set_operations(
                StackSetName=stackset_name,
                MaxResults=5
            )
            in_progress = [
                op for op in response.get('Summaries', [])
                if op.get('Status') in ('RUNNING', 'STOPPING')
            ]
            if not in_progress:
                return
            print(f"   ⏳ Waiting for StackSet operation to finish ({len(in_progress)} running)...")
        except ClientError:
            return  # If we can't check, proceed anyway
        time.sleep(15)
    print(f"   ⚠️  Timed out waiting for StackSet operation, proceeding anyway")


def wait_for_stackset_operation(stackset_name: str, operation_id: str, account_id: str, cloudformation, timeout: int = 180):
    """Wait for StackSet operation to complete"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            response = cloudformation.describe_stack_set_operation(
                StackSetName=stackset_name,
                OperationId=operation_id
            )
            
            status = response['StackSetOperation']['Status']
            print(f"   ⏳ StackSet operation status: {status}")
            
            if status == 'SUCCEEDED':
                return
            elif status in ['FAILED', 'STOPPED']:
                # Get failure details
                try:
                    instances = cloudformation.list_stack_instances(
                        StackSetName=stackset_name,
                        StackInstanceAccount=account_id,
                        StackInstanceRegion=REGION
                    )
                    
                    if instances.get('Summaries'):
                        status_reason = instances['Summaries'][0].get('StatusReason', 'Unknown')
                        
                        # If the failure is because the role already exists, that's OK - idempotent
                        if 'already exists' in status_reason.lower():
                            print(f"   ✅ StackSet instance already exists (idempotent)")
                            return
                        
                        raise Exception(f"StackSet operation failed: {status_reason}")
                except ClientError:
                    pass
                
                raise Exception(f"StackSet operation failed with status: {status}")
            
            time.sleep(10)
            
        except ClientError as e:
            if 'StackInstanceNotFoundException' in str(e):
                # Instance not created yet, keep waiting
                time.sleep(10)
                continue
            else:
                raise
    
    raise Exception(f"StackSet operation timed out after {timeout} seconds")

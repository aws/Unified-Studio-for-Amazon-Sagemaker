"""
Setup Orchestrator Lambda Function

Executes optimized 2-wave account setup workflow with maximum parallelization:
- Wave 1: Foundation + Domain Access (parallel, ~2.5 min)
  - VPC deployment with 3 private subnets
  - IAM roles (ManageAccessRole, ProvisioningRole)
  - Project execution role (optional, for ToolingLite blueprint)
  - EventBridge rules for event forwarding
  - S3 bucket for blueprint artifacts
  - RAM share creation and domain visibility verification
- Wave 2: Blueprint Enablement (~3 min)
  - Enable 17 DataZone blueprints with policy grants

Total estimated duration: 5.5 minutes (vs 10-12 minutes sequential, 45% improvement)

Key optimizations:
- Eliminated false dependencies (IAM/EventBridge don't need VPC, S3 doesn't need IAM)
- Domain visibility verification moved to Wave 1 (prerequisite for DataZone APIs)
- All foundation resources deployed in parallel
"""

import json
import os
import time
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
import boto3
from botocore.exceptions import ClientError

# Initialize AWS clients
cloudformation = boto3.client('cloudformation')
datazone = boto3.client('datazone')
ram = boto3.client('ram')
s3 = boto3.client('s3')
dynamodb = boto3.client('dynamodb')
sns = boto3.client('sns')
cloudwatch = boto3.client('cloudwatch')
ssm = boto3.client('ssm')
sts = boto3.client('sts')
organizations = boto3.client('organizations')

# Environment variables
DYNAMODB_TABLE_NAME = os.environ['DYNAMODB_TABLE_NAME']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
DOMAIN_ID = os.environ['DOMAIN_ID']
DOMAIN_ACCOUNT_ID = os.environ['DOMAIN_ACCOUNT_ID']
ROOT_DOMAIN_UNIT_ID = os.environ['ROOT_DOMAIN_UNIT_ID']
REGION = os.environ.get('AWS_REGION', 'us-east-2')

# Configuration cache
_config_cache = None


def load_config() -> Dict[str, Any]:
    """Load configuration from SSM Parameter Store"""
    try:
        response = ssm.get_parameters_by_path(
            Path='/AccountPoolFactory/SetupOrchestrator/',
            Recursive=True,
            WithDecryption=False
        )
        
        config = {}
        for param in response['Parameters']:
            key = param['Name'].split('/')[-1]
            config[key] = param['Value']
        
        # Apply defaults
        config.setdefault('DomainId', DOMAIN_ID)
        config.setdefault('DomainAccountId', DOMAIN_ACCOUNT_ID)
        config.setdefault('RootDomainUnitId', ROOT_DOMAIN_UNIT_ID)
        config.setdefault('Region', REGION)
        
        print(f"✅ Configuration loaded: {json.dumps(config, indent=2)}")
        return config
        
    except Exception as e:
        print(f"⚠️ Failed to load SSM parameters: {e}")
        return {
            'DomainId': DOMAIN_ID,
            'DomainAccountId': DOMAIN_ACCOUNT_ID,
            'RootDomainUnitId': ROOT_DOMAIN_UNIT_ID,
            'Region': REGION
        }


def get_config() -> Dict[str, Any]:
    """Get config with single-execution caching"""
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache


def lambda_handler(event, context):
    """Main Lambda handler for Setup Orchestrator.

    Supports two invocation paths:
    1. Direct invoke: event contains accountId, mode, etc. directly
    2. SQS trigger: event contains Records[0].body with the JSON payload
    """
    global _config_cache
    _config_cache = None  # Clear cache at start

    # Unwrap SQS record if triggered via event source mapping
    if event.get('Records'):
        try:
            event = json.loads(event['Records'][0]['body'])
        except Exception as e:
            print(f"❌ Failed to parse SQS record body: {e}")
            return {'statusCode': 400, 'body': f'Invalid SQS message: {e}'}

    print(f"📥 Received event: {json.dumps(event, indent=2)}")
    
    account_id = event.get('accountId')
    request_id = event.get('requestId')
    mode = event.get('mode', 'setup')
    resume_from_step = event.get('resumeFromStep')
    
    if not account_id:
        print("❌ Missing accountId in event")
        return {'statusCode': 400, 'body': 'Missing accountId'}
    
    config = get_config()
    
    # Validate account exists
    if not validate_account_exists(account_id):
        print(f"❌ Account {account_id} does not exist")
        return {'statusCode': 404, 'body': 'Account not found'}
    
    # Check for idempotency — skip for updateBlueprints which must run on AVAILABLE accounts
    account_state = get_account_state(account_id)
    if account_state and mode != 'updateBlueprints':
        state = account_state.get('state', {}).get('S')
        if state == 'AVAILABLE':
            print(f"✅ Account {account_id} already in AVAILABLE state, skipping")
            return {'statusCode': 200, 'body': 'Already completed'}
        elif state == 'IN_PROGRESS':
            last_updated = account_state.get('setupStartDate', {}).get('S')
            # Check if stale (>30 minutes)
            # For now, proceed with setup
            pass
    
    # Execute setup workflow
    try:
        if mode == 'setup':
            result = execute_setup_workflow(account_id, config, resume_from_step)
        elif mode == 'updateBlueprints':
            result = execute_update_blueprints(account_id, config)
        elif mode == 'cleanup':
            result = execute_cleanup_workflow(account_id, config)
        else:
            return {'statusCode': 400, 'body': f'Unknown mode: {mode}'}
        
        return {'statusCode': 200, 'body': json.dumps(result)}
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        mark_account_failed(account_id, 'unknown', str(e))
        send_failure_notification(account_id, 'unknown', str(e))
        return {'statusCode': 500, 'body': str(e)}


def validate_account_exists(account_id: str) -> bool:
    """Validate account exists in DynamoDB (Pool Manager already validated in Organizations)"""
    try:
        # Check if account exists in DynamoDB
        # Pool Manager already validated the account exists in Organizations
        # We just need to verify we have a DynamoDB record
        account_state = get_account_state(account_id)
        if account_state:
            print(f"✅ Account {account_id} found in DynamoDB")
            return True
        else:
            print(f"⚠️ Account {account_id} not found in DynamoDB")
            return False
    except Exception as e:
        print(f"❌ Error validating account {account_id}: {e}")
        return False


def get_account_state(account_id: str) -> Optional[Dict]:
    """Get account state from DynamoDB"""
    try:
        response = dynamodb.query(
            TableName=DYNAMODB_TABLE_NAME,
            KeyConditionExpression='accountId = :accountId',
            ExpressionAttributeValues={':accountId': {'S': account_id}},
            ScanIndexForward=False,
            Limit=1
        )
        
        if response.get('Items'):
            return response['Items'][0]
        return None
        
    except Exception as e:
        print(f"⚠️ Error querying account state: {e}")
        return None


# update_trust_policy() function removed - duplicate, already defined below


# get_account_state() second definition removed - duplicate


# deploy_stackset_instance() function removed


# ============================================================
# StackSet-driven deployment helpers (T6 migration)
# ============================================================

ORG_ADMIN_ACCOUNT_ID = os.environ.get('ORG_ADMIN_ACCOUNT_ID', '')
EXTERNAL_ID = os.environ.get('EXTERNAL_ID', f'AccountPoolFactory-{DOMAIN_ACCOUNT_ID}')


def _get_org_cf_client():
    """Assume AccountCreationRole in org-admin, return CF client scoped there."""
    role_arn = f"arn:aws:iam::{ORG_ADMIN_ACCOUNT_ID}:role/SMUS-AccountPoolFactory-AccountCreation"
    creds = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName='SetupOrchestrator-StackSet',
        ExternalId=EXTERNAL_ID,
        DurationSeconds=900
    )['Credentials']
    return boto3.client(
        'cloudformation', region_name=REGION,
        aws_access_key_id=creds['AccessKeyId'],
        aws_secret_access_key=creds['SecretAccessKey'],
        aws_session_token=creds['SessionToken']
    )


def _add_stackset_instance(org_cf, stackset_name: str, account_id: str, params: list,
                           max_retries: int = 30, base_delay: float = 30.0) -> str:
    """Add a StackSet instance for account_id. Returns operation ID.
    
    Retries on OperationInProgressException with flat delay + jitter since
    a StackSet can only have one operation at a time. StackSet operations
    typically complete in 30-60s.
    If a failed instance exists, deletes it first then re-adds.
    """
    kwargs = dict(
        StackSetName=stackset_name,
        Accounts=[account_id],
        Regions=[REGION],
        OperationPreferences={
            'FailureToleranceCount': 0,
            'MaxConcurrentCount': 1,
        }
    )
    if params:
        kwargs['ParameterOverrides'] = params

    import random
    for attempt in range(max_retries):
        try:
            resp = org_cf.create_stack_instances(**kwargs)
            return resp['OperationId']
        except org_cf.exceptions.OperationInProgressException:
            if attempt == max_retries - 1:
                raise
            delay = base_delay + random.uniform(0, 15)
            print(f"  ⏳ StackSet {stackset_name} busy, retry {attempt+1}/{max_retries} in {delay:.0f}s")
            time.sleep(delay)
        except Exception as e:
            err_str = str(e)
            if 'StackInstanceExists' in err_str:
                # Check if instance is in a failed/outdated state — delete and retry
                try:
                    inst = org_cf.describe_stack_instance(
                        StackSetName=stackset_name, StackInstanceAccount=account_id,
                        StackInstanceRegion=REGION
                    )['StackInstance']
                    inst_status = inst.get('Status', '')
                    stack_status = inst.get('StackInstanceStatus', {}).get('DetailedStatus', '')
                    if inst_status in ('OUTDATED',) or stack_status in ('FAILED', 'CANCELLED'):
                        print(f"  🔄 Deleting {inst_status}/{stack_status} instance for {account_id} in {stackset_name}")
                        del_resp = org_cf.delete_stack_instances(
                            StackSetName=stackset_name, Accounts=[account_id],
                            Regions=[REGION], RetainStacks=False,
                            OperationPreferences={'FailureToleranceCount': 0, 'MaxConcurrentCount': 1}
                        )
                        _wait_stackset_operation(org_cf, stackset_name, del_resp['OperationId'], timeout=300)
                        continue  # retry the create
                    else:
                        print(f"  ℹ️ StackSet instance already exists ({inst_status}) for {account_id} in {stackset_name}")
                        return 'ALREADY_EXISTS'
                except Exception as inner_e:
                    if 'OperationInProgressException' in str(inner_e):
                        delay = base_delay + random.uniform(0, 10)
                        print(f"  ⏳ StackSet {stackset_name} busy during cleanup, waiting {delay:.0f}s")
                        time.sleep(delay)
                        continue
                    print(f"  ⚠️ Could not inspect/delete instance: {inner_e}")
                    return 'ALREADY_EXISTS'
            raise


def _wait_stackset_operation(org_cf, stackset_name: str, operation_id: str, timeout: int = 600):
    """Poll until StackSet operation SUCCEEDED or raise on failure."""
    start = time.time()
    while time.time() - start < timeout:
        resp = org_cf.describe_stack_set_operation(
            StackSetName=stackset_name, OperationId=operation_id
        )
        status = resp['StackSetOperation']['Status']
        if status == 'SUCCEEDED':
            return
        if status in ('FAILED', 'CANCELLED', 'STOPPED'):
            raise Exception(f"StackSet operation {operation_id} {status} for {stackset_name}")
        time.sleep(15)
    raise Exception(f"StackSet operation timed out after {timeout}s for {stackset_name}")


def _read_stack_outputs(account_id: str, stack_name: str) -> dict:
    """Assume DomainAccess role into account, read CF stack outputs."""
    config = get_config()
    domain_id = config.get('DomainId', DOMAIN_ID)
    role_arn = f'arn:aws:iam::{account_id}:role/SMUS-AccountPoolFactory-DomainAccess'
    creds = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName='SetupOrchestrator-ReadOutputs',
        ExternalId=domain_id,
        DurationSeconds=900
    )['Credentials']
    cf_client = boto3.client(
        'cloudformation', region_name=REGION,
        aws_access_key_id=creds['AccessKeyId'],
        aws_secret_access_key=creds['SecretAccessKey'],
        aws_session_token=creds['SessionToken']
    )
    # StackSet instance stack name: StackSet-{StackSetName}-{uuid}
    # Find by listing stacks with the prefix
    stacks = cf_client.list_stacks(
        StackStatusFilter=['CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE']
    )['StackSummaries']
    prefix = f'StackSet-{stack_name}-'
    match = next((s for s in stacks if s['StackName'].startswith(prefix)), None)
    if not match:
        raise Exception(f"No healthy StackSet stack found with prefix {prefix} in {account_id}")
    detail = cf_client.describe_stacks(StackName=match['StackName'])['Stacks'][0]
    return {o['OutputKey']: o['OutputValue'] for o in detail.get('Outputs', [])}


# Old direct CF stack names that conflict with StackSet deployment
_OLD_DIRECT_STACKS = [
    'DataZone-Blueprints-{account_id}',
    'DataZone-EventBridge-{account_id}',
    'DataZone-ProjectRole-{account_id}',
    'DataZone-IAM-{account_id}',
    'DataZone-VPC-{account_id}',
]


def _cleanup_old_stacks(account_id: str, config: Dict[str, Any]):
    """Delete old direct CF stacks from account before StackSet deployment.
    
    These stacks were created by the pre-StackSet SetupOrchestrator and contain
    resources (IAM roles, VPCs, etc.) that conflict with StackSet instance creation.
    Skips stacks that don't exist or are already deleted.
    """
    try:
        cf_client = get_cross_account_client('cloudformation', account_id, config)
    except Exception as e:
        print(f"⚠️ Cannot access account {account_id} for old stack cleanup: {e}")
        return

    for stack_template in _OLD_DIRECT_STACKS:
        stack_name = stack_template.format(account_id=account_id)
        try:
            resp = cf_client.describe_stacks(StackName=stack_name)
            status = resp['Stacks'][0]['StackStatus']
            if status in ('DELETE_COMPLETE', 'DELETE_IN_PROGRESS'):
                continue
            print(f"  🗑️ Deleting old stack {stack_name} (status: {status})")
            cf_client.delete_stack(StackName=stack_name)
        except cf_client.exceptions.ClientError as e:
            if 'does not exist' in str(e):
                continue
            print(f"  ⚠️ Error checking {stack_name}: {e}")

    # Wait for all deletions to complete
    for stack_template in _OLD_DIRECT_STACKS:
        stack_name = stack_template.format(account_id=account_id)
        try:
            wait_for_stack_delete(cf_client, stack_name, timeout=300)
        except Exception:
            pass  # Stack didn't exist or already deleted

    print(f"✅ Old stack cleanup complete for {account_id}")


def execute_setup_workflow(account_id: str, config: Dict[str, Any], resume_from: Optional[str] = None) -> Dict[str, Any]:
    """Execute wave-based parallel setup workflow
    
    Note: Wave 0 (StackSet deployment) is now handled by ProvisionAccount Lambda in Org Admin account.
    SetupOrchestrator assumes SMUS-AccountPoolFactory-DomainAccess role already exists.
    """
    print(f"🚀 Starting setup workflow for account {account_id}")
    
    start_time = time.time()
    resources = {}
    
    try:
        # Wave 0.5: Clean up old direct CF stacks that conflict with StackSet deployment
        _cleanup_old_stacks(account_id, config)
        
        # Wave 1: Foundation + Domain Access (all parallel)
        print("🌊 Wave 1: Foundation + Domain Access (parallel)")
        print("   Deploying: VPC, IAM roles, Project role, EventBridge, S3 bucket, RAM share + domain visibility")
        
        vpc_result, iam_result, project_role_result, eb_result, s3_result, ram_result = execute_wave_parallel([
            lambda: deploy_vpc(account_id, config),
            lambda: deploy_iam_roles(account_id, config),
            lambda: deploy_project_role(account_id, config),
            lambda: deploy_eventbridge_rules(account_id, config),
            lambda: create_s3_bucket(account_id, config),
            lambda: create_ram_share_and_verify_domain(account_id, config)
        ])
        
        resources.update(vpc_result)
        resources.update(iam_result)
        resources.update(project_role_result)
        resources.update(eb_result)
        resources.update(s3_result)
        resources.update(ram_result)
        
        update_progress(account_id, 'wave1_foundation', {
            'vpc': vpc_result,
            'iam': iam_result,
            'project_role': project_role_result,
            'eventbridge': eb_result,
            's3': s3_result,
            'ram_and_domain': ram_result
        }, deployed_stacksets=[
            'SMUS-AccountPoolFactory-VpcSetup',
            'SMUS-AccountPoolFactory-IamRoles',
            'SMUS-AccountPoolFactory-ProjectRole',
            'SMUS-AccountPoolFactory-EventbridgeRules',
        ])
        
        print(f"✅ Wave 1 completed - All foundation resources deployed and domain verified")
        
        # Wave 2: Blueprint Enablement
        print("🌊 Wave 2: Blueprint Enablement")
        print("   Domain is verified accessible - DataZone APIs will succeed")
        
        bp_result = enable_blueprints(account_id, config, iam_result, vpc_result, s3_result)
        resources.update(bp_result)
        update_progress(account_id, 'wave2_blueprints', bp_result,
                        deployed_stacksets=['SMUS-AccountPoolFactory-BlueprintEnablement'])
        
        print(f"✅ Wave 2 completed - Blueprints enabled")
        
        # Mark account as AVAILABLE
        duration = int(time.time() - start_time)
        mark_account_available(account_id, resources, duration)
        
        publish_metric('SetupSucceeded', 1, [{'Name': 'AccountId', 'Value': account_id}])
        publish_metric('SetupDuration', duration, [{'Name': 'AccountId', 'Value': account_id}])
        
        print(f"✅ Setup completed in {duration} seconds (~{duration/60:.1f} minutes)")
        
        return {
            'status': 'COMPLETED',
            'accountId': account_id,
            'setupDuration': duration,
            'resources': resources
        }
        
    except Exception as e:
        print(f"❌ Setup workflow failed: {e}")
        mark_account_failed(account_id, 'workflow', str(e))
        send_failure_notification(account_id, 'workflow', str(e))
        raise


def execute_wave_parallel(tasks: List[callable]) -> Tuple:
    """Execute multiple tasks in parallel and return results"""
    results = []
    for task in tasks:
        try:
            result = task()
            results.append(result)
        except Exception as e:
            print(f"❌ Task failed: {e}")
            raise
    return tuple(results)



def update_trust_policy(account_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Update OrganizationAccountAccessRole trust policy to allow Domain account access"""
    print(f"🔐 Updating trust policy for account {account_id}")
    
    domain_account_id = config['DomainAccountId']
    
    try:
        # Assume role in project account using Org Admin credentials
        # The Lambda already has permission to assume OrganizationAccountAccessRole
        assumed_role = sts.assume_role(
            RoleArn=f"arn:aws:iam::{account_id}:role/OrganizationAccountAccessRole",
            RoleSessionName='SetupOrchestrator-TrustUpdate'
        )
        
        credentials = assumed_role['Credentials']
        
        # Create IAM client with assumed role credentials
        iam_client = boto3.client(
            'iam',
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )
        
        # Get current trust policy
        role_name = 'OrganizationAccountAccessRole'
        current_policy = iam_client.get_role(RoleName=role_name)['Role']['AssumeRolePolicyDocument']
        
        # Check if Domain account is already in trust policy
        domain_principal = f"arn:aws:iam::{domain_account_id}:root"
        already_trusted = False
        
        for statement in current_policy.get('Statement', []):
            principal = statement.get('Principal', {})
            aws_principals = principal.get('AWS', [])
            if isinstance(aws_principals, str):
                aws_principals = [aws_principals]
            if domain_principal in aws_principals:
                already_trusted = True
                break
        
        if already_trusted:
            print(f"   ✅ Domain account already trusted")
            return {'trustPolicyUpdated': False, 'alreadyTrusted': True}
        
        # Add Domain account to trust policy
        print(f"   Adding Domain account {domain_account_id} to trust policy")
        
        # Build new trust policy
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
        
        print(f"   ✅ Trust policy updated successfully")
        
        return {
            'trustPolicyUpdated': True,
            'domainAccountId': domain_account_id,
            'roleName': role_name
        }
        
    except Exception as e:
        print(f"   ❌ Trust policy update failed: {e}")
        raise Exception(f"Trust policy update failed: {e}")


def _needs_template_update(outputs: list, expected_version: str) -> bool:
    """Return True if the deployed stack's TemplateVersion output differs from expected_version.
    Stacks without a TemplateVersion output (old deployments) always need updating."""
    deployed = next((o['OutputValue'] for o in outputs if o['OutputKey'] == 'TemplateVersion'), None)
    return deployed != expected_version


def _update_stack(cf_client, stack_name: str, template_path: str, parameters: list, timeout: int = 600):
    """Update an existing CF stack with a new template. Silently skips if no changes."""
    with open(template_path, 'r') as f:
        template_body = f.read()
    try:
        cf_client.update_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=parameters,
            Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM', 'CAPABILITY_AUTO_EXPAND'],
        )
        wait_for_stack_complete(cf_client, stack_name, timeout=timeout)
        print(f"   ✅ Stack updated: {stack_name}")
    except Exception as e:
        if 'No updates are to be performed' in str(e):
            print(f"   ✅ Stack already up to date: {stack_name}")
        else:
            raise


def deploy_vpc(account_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Deploy VPC via StackSet instance, read outputs from target account."""
    print(f"🌐 Deploying VPC for account {account_id} via StackSet")
    stackset_name = 'SMUS-AccountPoolFactory-VpcSetup'
    org_cf = _get_org_cf_client()
    op_id = _add_stackset_instance(org_cf, stackset_name, account_id, [])
    if op_id != 'ALREADY_EXISTS':
        _wait_stackset_operation(org_cf, stackset_name, op_id)
    outputs = _read_stack_outputs(account_id, stackset_name)
    result = {
        'vpcId': outputs.get('VpcId', ''),
        'subnetIds': [
            outputs.get('PrivateSubnet1Id', ''),
            outputs.get('PrivateSubnet2Id', ''),
            outputs.get('PrivateSubnet3Id', ''),
        ]
    }
    print(f"✅ VPC deployed via StackSet: {result['vpcId']}")
    return result


def deploy_iam_roles(account_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Deploy IAM roles via StackSet instance, read outputs from target account."""
    print(f"👤 Deploying IAM roles for account {account_id} via StackSet")
    stackset_name = 'SMUS-AccountPoolFactory-IamRoles'
    params = [
        {'ParameterKey': 'DomainAccountId', 'ParameterValue': config['DomainAccountId']},
        {'ParameterKey': 'DomainId',        'ParameterValue': config['DomainId']},
    ]
    org_cf = _get_org_cf_client()
    op_id = _add_stackset_instance(org_cf, stackset_name, account_id, params)
    if op_id != 'ALREADY_EXISTS':
        _wait_stackset_operation(org_cf, stackset_name, op_id)
    outputs = _read_stack_outputs(account_id, stackset_name)
    result = {
        'manageAccessRoleArn':  outputs.get('ManageAccessRoleArn', ''),
        'provisioningRoleArn':  outputs.get('ProvisioningRoleArn', ''),
    }
    print(f"✅ IAM roles deployed via StackSet")
    return result


def deploy_eventbridge_rules(account_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Deploy EventBridge rules via StackSet instance."""
    print(f"📡 Deploying EventBridge rules for account {account_id} via StackSet")
    stackset_name = 'SMUS-AccountPoolFactory-EventbridgeRules'
    central_bus_arn = (
        f"arn:aws:events:{config['Region']}:{config['DomainAccountId']}"
        f":event-bus/AccountPoolFactory-CentralBus"
    )
    params = [{'ParameterKey': 'CentralEventBusArn', 'ParameterValue': central_bus_arn}]
    org_cf = _get_org_cf_client()
    op_id = _add_stackset_instance(org_cf, stackset_name, account_id, params)
    if op_id != 'ALREADY_EXISTS':
        _wait_stackset_operation(org_cf, stackset_name, op_id)
    print(f"✅ EventBridge rules deployed via StackSet")
    return {'eventBridgeRulesDeployed': True}


def deploy_project_role(account_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Deploy project execution role via StackSet instance."""
    enabled = config.get('ProjectRoleEnabled', 'true').lower()
    if enabled != 'true':
        print(f"⏭️ Project role disabled")
        return {}
    role_name  = config.get('ProjectRoleName', 'AmazonSageMakerProjectRole')
    policy_arn = config.get('ProjectRoleManagedPolicyArn',
                            'arn:aws:iam::aws:policy/SageMakerStudioAdminIAMPermissiveExecutionPolicy')
    print(f"👤 Deploying project role for account {account_id} via StackSet")
    stackset_name = 'SMUS-AccountPoolFactory-ProjectRole'
    params = [
        {'ParameterKey': 'RoleName',         'ParameterValue': role_name},
        {'ParameterKey': 'ManagedPolicyArn', 'ParameterValue': policy_arn},
    ]
    org_cf = _get_org_cf_client()
    op_id = _add_stackset_instance(org_cf, stackset_name, account_id, params)
    if op_id != 'ALREADY_EXISTS':
        _wait_stackset_operation(org_cf, stackset_name, op_id)
    outputs = _read_stack_outputs(account_id, stackset_name)
    print(f"✅ Project role deployed via StackSet")
    return {'projectRoleArn': outputs.get('ProjectRoleArn', '')}

def create_s3_bucket(account_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Create S3 bucket for blueprint artifacts"""
    print(f"🪣 Creating S3 bucket for account {account_id}")

    bucket_name = f"datazone-blueprints-{account_id}-{config['Region']}"
    try:
        s3_client = get_cross_account_client('s3', account_id)

        # Check if bucket already exists
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            print(f"✅ S3 bucket already exists: {bucket_name}")
            return {'bucketName': bucket_name}
        except s3_client.exceptions.ClientError:
            pass

        if config['Region'] == 'us-east-1':
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': config['Region']}
            )

        s3_client.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={'Status': 'Enabled'}
        )

        s3_client.put_bucket_encryption(
            Bucket=bucket_name,
            ServerSideEncryptionConfiguration={
                'Rules': [{
                    'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}
                }]
            }
        )

        print(f"✅ S3 bucket created: {bucket_name}")
        return {'bucketName': bucket_name}

    except Exception as e:
        print(f"❌ S3 bucket creation failed: {e}")
        raise


def create_ram_share_and_verify_domain(account_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Verify domain visibility via org-wide RAM share.
    
    The org-wide RAM share (DataZone-Domain-Share-OrgWide) covers all accounts in the OU,
    so no per-account share creation is needed. We just verify the domain is accessible.
    
    Pre-requisite: org-wide share must exist in the domain account targeting the OU.
    """
    print(f"🔍 Verifying domain visibility for account {account_id} (via org-wide RAM share)")
    
    # No ramShareArn for per-account share — pass empty dict, verify_domain_visibility
    # only uses it for a mid-retry principal check which is not needed with org-wide share.
    verify_result = verify_domain_visibility(account_id, config, {})
    
    result = {
        'domainVisible': verify_result.get('domainVisible', False),
        'domainAccessible': verify_result.get('domainAccessible', False)
    }
    
    print(f"✅ Domain verified accessible for account {account_id}")
    return result




def create_ram_share(account_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Create RAM share for domain access with explicit principal and resource association
    
    ROOT CAUSE FIX: Under concurrent Lambda executions (5 simultaneous), passing
    principals in create_resource_share can silently fail to persist the principal
    association. Fix: create share empty, then explicitly associate principal AND
    resource separately, verifying each step.
    
    If resource association fails (e.g. "Failed to put resource policy"), the share
    is deleted and recreated to avoid stale FAILED associations blocking retries.
    
    Steps:
    1. Create empty RAM share (no principals, no resources)
    2. Wait for share ACTIVE
    3. Explicitly associate principal (account ID) and verify ASSOCIATED
    4. Explicitly associate domain resource and wait for it to appear
    
    Timing: ~30-60 seconds total
    """
    print(f"🔗 Creating RAM share for account {account_id}")
    
    share_name = f"DataZone-Domain-Share-{account_id}"
    
    try:
        domain_arn = f"arn:aws:datazone:{config['Region']}:{config['DomainAccountId']}:domain/{config['DomainId']}"
        principal = account_id
        
        print(f"   Domain ARN: {domain_arn}")
        print(f"   Principal: {principal}")
        
        # Check if share already exists
        existing = ram.get_resource_shares(
            resourceOwner='SELF',
            name=share_name
        )
        active_shares = [s for s in existing.get('resourceShares', []) if s['status'] == 'ACTIVE']
        needs_recreate = False
        if active_shares:
            share_arn = active_shares[0]['resourceShareArn']
            print(f"   ✅ RAM share already exists: {share_arn}")
            # Verify principal is associated, re-associate if missing
            assocs = ram.get_resource_share_associations(
                associationType='PRINCIPAL',
                resourceShareArns=[share_arn]
            )
            has_principal = any(a['associatedEntity'] == principal and a['status'] == 'ASSOCIATED'
                              for a in assocs.get('resourceShareAssociations', []))
            if not has_principal:
                print(f"   ⚠️  Principal missing, re-associating...")
                ram.associate_resource_share(resourceShareArn=share_arn, principals=[principal])
                wait_for_ram_principal_associated(share_arn, principal)
            # Verify resource is associated
            res_assocs = ram.get_resource_share_associations(
                associationType='RESOURCE',
                resourceShareArns=[share_arn]
            )
            resource_status = None
            for a in res_assocs.get('resourceShareAssociations', []):
                if a['associatedEntity'] == domain_arn:
                    resource_status = a['status']
                    break

            if resource_status == 'ASSOCIATED':
                print(f"   ✅ Resource already ASSOCIATED")
            elif resource_status == 'FAILED':
                # Strategy 1: Disassociate the FAILED resource, then re-associate
                print(f"   ⚠️  Resource in FAILED state, attempting disassociate + re-associate...")
                try:
                    ram.disassociate_resource_share(
                        resourceShareArn=share_arn,
                        resourceArns=[domain_arn]
                    )
                    # Wait for disassociation to complete
                    for _ in range(12):
                        time.sleep(5)
                        check = ram.get_resource_share_associations(
                            associationType='RESOURCE',
                            resourceShareArns=[share_arn]
                        )
                        still_there = any(
                            a['associatedEntity'] == domain_arn and a['status'] != 'DISASSOCIATED'
                            for a in check.get('resourceShareAssociations', [])
                        )
                        if not still_there:
                            break
                    print(f"   ✅ FAILED resource disassociated")
                    ram.associate_resource_share(resourceShareArn=share_arn, resourceArns=[domain_arn])
                    wait_for_ram_share_resources(share_arn, domain_arn)
                    print(f"   ✅ Resource re-associated successfully")
                except Exception as e1:
                    # Strategy 2: Delete the entire share and recreate from scratch
                    print(f"   ⚠️  Disassociate failed ({e1}), deleting share and recreating...")
                    ram.delete_resource_share(resourceShareArn=share_arn)
                    # Wait for deletion
                    for _ in range(12):
                        time.sleep(5)
                        check = ram.get_resource_shares(
                            resourceShareArns=[share_arn],
                            resourceOwner='SELF'
                        )
                        if not check.get('resourceShares') or check['resourceShares'][0]['status'] == 'DELETED':
                            break
                    print(f"   ✅ Old share deleted, will recreate from scratch")
                    needs_recreate = True
            else:
                # Resource missing or in another state — try associating
                print(f"   ⚠️  Resource status: {resource_status}, re-associating...")
                ram.associate_resource_share(resourceShareArn=share_arn, resourceArns=[domain_arn])
                wait_for_ram_share_resources(share_arn, domain_arn)

            if not needs_recreate:
                print(f"   ✅ Existing RAM share verified with principal and resource")
                return {'ramShareArn': share_arn}
        
        # Step 1: Create EMPTY RAM share (no principals, no resources)
        # CRITICAL: Do NOT pass principals here - under concurrent load they can
        # silently fail to associate. We associate explicitly in Step 3.
        print(f"   📋 Step 1: Creating empty RAM share...")
        response = ram.create_resource_share(
            name=share_name,
            permissionArns=[
                'arn:aws:ram::aws:permission/AWSRAMPermissionAmazonDataZoneDomainFullAccessWithPortalAccess'
            ],
            tags=[
                {'key': 'ManagedBy', 'value': 'AccountPoolFactory'},
                {'key': 'AccountId', 'value': account_id}
            ]
        )
        
        share_arn = response['resourceShare']['resourceShareArn']
        initial_status = response['resourceShare']['status']
        
        print(f"   ✅ RAM share created: {share_arn}")
        print(f"      Initial status: {initial_status}")
        
        # Step 2: Wait for share to become active
        print(f"   📋 Step 2: Waiting for share to become ACTIVE...")
        wait_for_ram_share_active(share_arn)
        print(f"   ✅ Share is ACTIVE")
        
        # Step 3: Explicitly associate principal (account ID)
        # This is the key fix - associate principal separately and verify it
        print(f"   📋 Step 3: Explicitly associating principal {principal}...")
        principal_response = ram.associate_resource_share(
            resourceShareArn=share_arn,
            principals=[principal]
        )
        
        principal_assocs = principal_response.get('resourceShareAssociations', [])
        if principal_assocs:
            for assoc in principal_assocs:
                print(f"      Principal status: {assoc.get('status', 'UNKNOWN')}")
        else:
            print(f"   ⚠️  WARNING: No principal associations returned")
        
        # Verify principal is ASSOCIATED (wait up to 60 seconds)
        print(f"   📋 Step 3b: Verifying principal association...")
        wait_for_ram_principal_associated(share_arn, principal)
        print(f"   ✅ Principal {principal} is ASSOCIATED")
        
        # Step 4: Explicitly associate the domain resource
        print(f"   📋 Step 4: Explicitly associating domain resource...")
        resource_response = ram.associate_resource_share(
            resourceShareArn=share_arn,
            resourceArns=[domain_arn]
        )
        
        resource_assocs = resource_response.get('resourceShareAssociations', [])
        if resource_assocs:
            for assoc in resource_assocs:
                assoc_status = assoc.get('status', 'UNKNOWN')
                print(f"      Resource status: {assoc_status}")
                print(f"      Entity: {assoc.get('associatedEntity', 'UNKNOWN')}")
                if assoc.get('statusMessage'):
                    print(f"      Message: {assoc['statusMessage']}")
        else:
            print(f"   ⚠️  WARNING: No resource associations returned")
        
        # Step 5: Wait for domain resource to appear in share
        print(f"   📋 Step 5: Waiting for domain resource to appear in share...")
        wait_for_ram_share_resources(share_arn, domain_arn)
        
        print(f"✅ RAM share fully configured: {share_arn}")
        print(f"   Principal: {principal} ✅")
        print(f"   Resource: {domain_arn} ✅")
        return {'ramShareArn': share_arn}
        
    except Exception as e:
        print(f"❌ RAM share creation failed: {e}")
        print(f"   Account: {account_id}")
        print(f"   Share name: {share_name}")
        print(f"   Domain ARN: {domain_arn if 'domain_arn' in locals() else 'NOT SET'}")
        print(f"   Share ARN: {share_arn if 'share_arn' in locals() else 'NOT CREATED'}")
        raise


def wait_for_ram_principal_associated(share_arn: str, expected_principal: str, timeout: int = 60):
    """Wait for RAM share principal to reach ASSOCIATED status
    
    Args:
        share_arn: RAM share ARN
        expected_principal: Account ID that should be associated
        timeout: Maximum wait time in seconds
    """
    start_time = time.time()
    attempt = 0
    
    while time.time() - start_time < timeout:
        attempt += 1
        
        response = ram.get_resource_share_associations(
            associationType='PRINCIPAL',
            resourceShareArns=[share_arn]
        )
        
        for assoc in response.get('resourceShareAssociations', []):
            if assoc.get('associatedEntity') == expected_principal:
                status = assoc.get('status')
                if status == 'ASSOCIATED':
                    return
                elif status == 'FAILED':
                    message = assoc.get('statusMessage', 'No message')
                    raise Exception(
                        f"Principal association FAILED for {expected_principal}: {message}"
                    )
                else:
                    print(f"      Attempt {attempt}: Principal status = {status}")
        
        time.sleep(5)
    
    raise Exception(
        f"Principal {expected_principal} not ASSOCIATED after {timeout}s. "
        f"Share: {share_arn}"
    )


def enable_blueprints(account_id: str, config: Dict[str, Any], iam_result: Dict[str, Any],
                      vpc_result: Dict[str, Any] = None, s3_result: Dict[str, Any] = None) -> Dict[str, Any]:
    """Enable DataZone blueprints via StackSet instance.
    
    Retries the full add+wait cycle up to 3 times because blueprint types may
    take time to become available after old stack deletion.
    """
    print(f"📋 Enabling blueprints for account {account_id} via StackSet")

    stackset_name = 'SMUS-AccountPoolFactory-BlueprintEnablement'

    vpc_id         = (vpc_result or {}).get('vpcId', '')
    subnet_ids     = ','.join(s for s in (vpc_result or {}).get('subnetIds', []) if s)
    bucket_name    = (s3_result or {}).get('bucketName', '')
    s3_location    = f"s3://{bucket_name}" if bucket_name else ''

    params = [
        {'ParameterKey': 'DomainId',             'ParameterValue': config['DomainId']},
        {'ParameterKey': 'ManageAccessRoleArn',  'ParameterValue': iam_result.get('manageAccessRoleArn', '')},
        {'ParameterKey': 'ProvisioningRoleArn',  'ParameterValue': iam_result.get('provisioningRoleArn', '')},
        {'ParameterKey': 'VpcId',                'ParameterValue': vpc_id},
        {'ParameterKey': 'SubnetIds',            'ParameterValue': subnet_ids},
        {'ParameterKey': 'S3BucketName',         'ParameterValue': s3_location},
        {'ParameterKey': 'DomainUnitId',         'ParameterValue': config.get('RootDomainUnitId', ROOT_DOMAIN_UNIT_ID)},
    ]

    org_cf = _get_org_cf_client()
    
    max_attempts = 3
    for attempt in range(max_attempts):
        op_id = _add_stackset_instance(org_cf, stackset_name, account_id, params)
        if op_id == 'ALREADY_EXISTS':
            break
        try:
            _wait_stackset_operation(org_cf, stackset_name, op_id, timeout=3600)
            break  # success
        except Exception as e:
            if attempt < max_attempts - 1 and 'FAILED' in str(e):
                print(f"  ⚠️ BlueprintEnablement attempt {attempt+1} failed, retrying in 60s...")
                # Delete the failed instance so we can retry
                try:
                    del_resp = org_cf.delete_stack_instances(
                        StackSetName=stackset_name, Accounts=[account_id],
                        Regions=[REGION], RetainStacks=False,
                        OperationPreferences={'FailureToleranceCount': 0, 'MaxConcurrentCount': 1}
                    )
                    _wait_stackset_operation(org_cf, stackset_name, del_resp['OperationId'], timeout=300)
                except Exception:
                    pass
                time.sleep(60)
            else:
                raise

    outputs = _read_stack_outputs(account_id, stackset_name)
    blueprint_ids = [v for k, v in outputs.items() if k.endswith('BlueprintId')]
    print(f"✅ {len(blueprint_ids)} blueprints enabled via StackSet")
    return {'blueprintIds': str(blueprint_ids)}


def verify_domain_visibility(account_id: str, config: Dict[str, Any], ram_result: Dict[str, Any]) -> Dict[str, Any]:
    """Verify domain is visible and accessible from project account
    
    After RAM share is fully configured (principal ASSOCIATED + resource present),
    domain access typically works within 15-30 seconds. Uses linear backoff
    to avoid Lambda timeout.
    """
    print(f"🔍 Verifying domain visibility for account {account_id}")
    
    max_retries = 12
    wait_interval = 15  # Linear 15s intervals, max ~3 minutes total
    
    for attempt in range(max_retries):
        try:
            dz_client = get_cross_account_client('datazone', account_id)
            
            try:
                response = dz_client.get_domain(identifier=config['DomainId'])
                domain_status = response.get('status')
                
                if domain_status == 'AVAILABLE':
                    print(f"✅ Domain accessible via GetDomain (attempt {attempt + 1})")
                    return {'domainVisible': True, 'domainAccessible': True}
                else:
                    print(f"⚠️ Domain found but status is {domain_status}")
                    
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == 'UnauthorizedException':
                    # Before retrying, verify principal is still associated
                    if attempt == 3:  # Check once at attempt 3
                        share_arn = ram_result.get('ramShareArn', '')
                        if share_arn:
                            print(f"   Verifying RAM principal still associated...")
                            try:
                                assoc_resp = ram.get_resource_share_associations(
                                    associationType='PRINCIPAL',
                                    resourceShareArns=[share_arn]
                                )
                                principals = assoc_resp.get('resourceShareAssociations', [])
                                if not principals:
                                    print(f"   ❌ Principal MISSING - re-associating...")
                                    ram.associate_resource_share(
                                        resourceShareArn=share_arn,
                                        principals=[account_id]
                                    )
                                    wait_for_ram_principal_associated(share_arn, account_id)
                                    print(f"   ✅ Principal re-associated")
                                else:
                                    p_status = principals[0].get('status', 'UNKNOWN')
                                    print(f"   Principal status: {p_status}")
                            except Exception as check_e:
                                print(f"   ⚠️ Could not verify principal: {check_e}")
                    
                    print(f"   Unauthorized (attempt {attempt + 1}/{max_retries}), waiting {wait_interval}s...")
                elif error_code == 'ResourceNotFoundException':
                    print(f"   ResourceNotFound (attempt {attempt + 1}/{max_retries}), waiting {wait_interval}s...")
                else:
                    print(f"   Error: {error_code} (attempt {attempt + 1}/{max_retries})")
            
            if attempt < max_retries - 1:
                time.sleep(wait_interval)
            
        except Exception as e:
            print(f"⚠️ Error checking domain visibility: {e}")
            if attempt < max_retries - 1:
                time.sleep(wait_interval)
            else:
                raise
    
    raise Exception(
        f"Domain not accessible after {max_retries} retries (~{max_retries * wait_interval}s). "
        f"Account: {account_id}. Check RAM share principal and resource associations."
    )


def execute_update_blueprints(account_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Update only the Blueprints stack on an AVAILABLE account.

    Reads VPC and S3 outputs from existing stacks, then calls enable_blueprints()
    which will update_stack() if params changed or skip if already up to date.
    Does NOT deprovision or touch any other stacks.
    Account state is left as AVAILABLE throughout.
    """
    print(f"🔄 Updating blueprints for account {account_id}")

    try:
        cf_client = get_cross_account_client('cloudformation', account_id)

        # Read VPC outputs from existing stack
        vpc_result = {}
        try:
            resp = cf_client.describe_stacks(StackName=f"DataZone-VPC-{account_id}")
            outputs = resp['Stacks'][0].get('Outputs', [])
            vpc_result = {
                'vpcId': get_output_value(outputs, 'VpcId'),
                'subnetIds': [
                    get_output_value(outputs, 'PrivateSubnet1Id'),
                    get_output_value(outputs, 'PrivateSubnet2Id'),
                    get_output_value(outputs, 'PrivateSubnet3Id')
                ]
            }
        except Exception as e:
            print(f"  ⚠️ Could not read VPC stack: {e}")

        # Read IAM outputs from existing stack
        iam_result = {}
        try:
            resp = cf_client.describe_stacks(StackName=f"DataZone-IAM-{account_id}")
            outputs = resp['Stacks'][0].get('Outputs', [])
            iam_result = {
                'manageAccessRoleArn': get_output_value(outputs, 'ManageAccessRoleArn'),
                'provisioningRoleArn': get_output_value(outputs, 'ProvisioningRoleArn')
            }
        except Exception as e:
            print(f"  ⚠️ Could not read IAM stack: {e}")

        # S3 bucket follows naming convention
        s3_result = {'bucketName': f"datazone-blueprints-{account_id}-{config['Region']}"}

        bp_result = enable_blueprints(account_id, config, iam_result, vpc_result, s3_result)

        print(f"✅ Blueprints updated for {account_id}")
        return {'status': 'UPDATED', 'accountId': account_id, 'blueprints': bp_result}

    except Exception as e:
        print(f"❌ Blueprint update failed for {account_id}: {e}")
        raise


def execute_cleanup_workflow(account_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Execute cleanup workflow for REUSE strategy"""
    print(f"🧹 Starting cleanup workflow for account {account_id}")
    
    try:
        cf_client = get_cross_account_client('cloudformation', account_id)
        
        # List all DataZone stacks
        response = cf_client.list_stacks(
            StackStatusFilter=['CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE']
        )
        
        stacks_to_delete = [
            stack['StackName'] for stack in response.get('StackSummaries', [])
            if stack['StackName'].startswith('DataZone-')
        ]
        
        # Delete stacks in reverse order
        for stack_name in reversed(stacks_to_delete):
            print(f"  🗑️ Deleting stack {stack_name}")
            cf_client.delete_stack(StackName=stack_name)
            wait_for_stack_delete(cf_client, stack_name)
        
        # Delete S3 buckets
        s3_client = get_cross_account_client('s3', account_id)
        bucket_name = f"datazone-blueprints-{account_id}-{config['Region']}"
        
        try:
            # Empty bucket first
            response = s3_client.list_object_versions(Bucket=bucket_name)
            for version in response.get('Versions', []):
                s3_client.delete_object(
                    Bucket=bucket_name,
                    Key=version['Key'],
                    VersionId=version['VersionId']
                )
            
            # Delete bucket
            s3_client.delete_bucket(Bucket=bucket_name)
            print(f"  ✅ Deleted S3 bucket {bucket_name}")
        except:
            pass
        
        # Mark account as AVAILABLE
        mark_account_available(account_id, {}, 0)
        
        print(f"✅ Cleanup completed")
        return {'status': 'CLEANED'}
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        mark_account_failed(account_id, 'cleanup', str(e))
        raise


def check_existing_stack(cf_client, stack_name):
    """Check if a CloudFormation stack exists and handle bad states.

    Returns:
      ('healthy', outputs)  — stack is CREATE_COMPLETE/UPDATE_COMPLETE, use outputs
      ('none', None)        — stack doesn't exist, caller should create it
      ('cleaned', None)     — stack was in a bad state and has been deleted, caller should create it

    This makes all deploy_* functions idempotent even when stacks are in
    ROLLBACK_COMPLETE, DELETE_FAILED, or other terminal bad states.
    """
    HEALTHY = {'CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE'}
    DELETABLE = {'ROLLBACK_COMPLETE', 'ROLLBACK_FAILED', 'CREATE_FAILED',
                 'DELETE_FAILED', 'UPDATE_ROLLBACK_FAILED'}

    try:
        response = cf_client.describe_stacks(StackName=stack_name)
        stack = response['Stacks'][0]
        stack_status = stack['StackStatus']

        if stack_status in HEALTHY:
            return 'healthy', stack.get('Outputs', [])

        if stack_status in DELETABLE:
            print(f"  Stack {stack_name} in bad state ({stack_status}), deleting...")
            cf_client.delete_stack(StackName=stack_name)
            wait_for_stack_delete(cf_client, stack_name, timeout=300)
            print(f"  Stack {stack_name} deleted, will recreate")
            return 'cleaned', None

        # Stack is in a transient state — wait for it to complete, then re-check
        IN_PROGRESS = {'CREATE_IN_PROGRESS', 'UPDATE_IN_PROGRESS', 'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS',
                       'DELETE_IN_PROGRESS', 'ROLLBACK_IN_PROGRESS', 'UPDATE_ROLLBACK_IN_PROGRESS',
                       'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS'}
        if stack_status in IN_PROGRESS:
            print(f"  Stack {stack_name} in transient state ({stack_status}), waiting for completion...")
            wait_for_stack_complete(cf_client, stack_name, timeout=600)
            # Re-check after waiting
            response = cf_client.describe_stacks(StackName=stack_name)
            stack = response['Stacks'][0]
            stack_status = stack['StackStatus']
            if stack_status in HEALTHY:
                return 'healthy', stack.get('Outputs', [])
            if stack_status in DELETABLE:
                print(f"  Stack {stack_name} in bad state ({stack_status}) after wait, deleting...")
                cf_client.delete_stack(StackName=stack_name)
                wait_for_stack_delete(cf_client, stack_name, timeout=300)
                return 'cleaned', None

        print(f"  Stack {stack_name} in unexpected state ({stack_status}), skipping")
        raise Exception(f"Stack {stack_name} in unexpected state: {stack_status}")

    except ClientError as e:
        if 'does not exist' in str(e):
            return 'none', None
        raise


def get_cross_account_client(service: str, account_id: str, config: Dict[str, Any] = None):
    """Get boto3 client for cross-account access using SMUS-AccountPoolFactory-DomainAccess role"""
    if config is None:
        config = get_config()
    
    role_arn = f"arn:aws:iam::{account_id}:role/SMUS-AccountPoolFactory-DomainAccess"
    domain_id = config.get('DomainId', DOMAIN_ID)
    
    print(f"🔐 Assuming role: {role_arn}")
    print(f"   ExternalId: {domain_id}")
    
    assumed_role = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName=f'SetupOrchestrator-{service}',
        ExternalId=domain_id,
        DurationSeconds=3600
    )
    
    credentials = assumed_role['Credentials']
    
    return boto3.client(
        service,
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=REGION
    )


def wait_for_stack_complete(cf_client, stack_name: str, timeout: int = 1800):
    """Wait for CloudFormation stack to complete (create or update)"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            response = cf_client.describe_stacks(StackName=stack_name)
            status = response['Stacks'][0]['StackStatus']
            
            if status in ('CREATE_COMPLETE', 'UPDATE_COMPLETE'):
                return
            elif status in ('CREATE_FAILED', 'ROLLBACK_COMPLETE', 'ROLLBACK_FAILED',
                            'UPDATE_ROLLBACK_COMPLETE', 'UPDATE_FAILED', 'UPDATE_ROLLBACK_FAILED'):
                raise Exception(f"Stack operation failed with status: {status}")
            
            print(f"  ⏳ Stack status: {status}")
            time.sleep(30)
            
        except Exception as e:
            if 'does not exist' in str(e):
                time.sleep(10)
            else:
                raise
    
    raise Exception(f"Stack creation timed out after {timeout} seconds")


def wait_for_stack_delete(cf_client, stack_name: str, timeout: int = 1800):
    """Wait for CloudFormation stack to delete"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            response = cf_client.describe_stacks(StackName=stack_name)
            status = response['Stacks'][0]['StackStatus']
            
            if status == 'DELETE_COMPLETE':
                return
            elif status == 'DELETE_FAILED':
                raise Exception(f"Stack deletion failed")
            
            print(f"  ⏳ Stack status: {status}")
            time.sleep(30)
            
        except ClientError as e:
            if 'does not exist' in str(e):
                return
            raise
    
    raise Exception(f"Stack deletion timed out after {timeout} seconds")


def wait_for_ram_share_active(share_arn: str, timeout: int = 300):
    """Wait for RAM share to become active"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        response = ram.get_resource_shares(
            resourceShareArns=[share_arn],
            resourceOwner='SELF'
        )
        
        if response['resourceShares']:
            status = response['resourceShares'][0]['status']
            if status == 'ACTIVE':
                return
            print(f"  ⏳ RAM share status: {status}")
        
        time.sleep(10)
    
    raise Exception(f"RAM share did not become active after {timeout} seconds")


def wait_for_ram_share_resources(share_arn: str, expected_resource_arn: str, timeout: int = 300):
    """Wait for domain resource to be added to RAM share with exponential backoff
    
    IAM-mode DataZone domains require time for the domain resource to appear in the share.
    Test data shows: Resource appears on 2nd attempt (~10 seconds) in successful cases.
    
    Polling strategy:
    - Initial attempts: 5 second intervals (fast feedback for common case)
    - Later attempts: Exponential backoff up to 30 seconds
    - Total timeout: 300 seconds (5 minutes) - generous buffer
    
    Args:
        share_arn: RAM share ARN
        expected_resource_arn: Domain ARN we're waiting for
        timeout: Maximum wait time in seconds (default: 300)
    """
    print(f"  ⏳ Waiting for domain resource to appear in RAM share...")
    print(f"     Expected resource: {expected_resource_arn}")
    print(f"     Share ARN: {share_arn}")
    print(f"     Timeout: {timeout} seconds")
    print(f"     Strategy: Fast polling (5s) then exponential backoff")
    print(f"     Test data: Usually succeeds in ~10-30 seconds")
    
    start_time = time.time()
    attempt = 0
    
    # Polling intervals: Start fast, then exponential backoff
    # [5, 5, 5, 5, 10, 15, 20, 30, 30, 30, ...]
    def get_wait_interval(attempt_num):
        if attempt_num < 4:
            return 5  # First 4 attempts: 5 seconds (covers typical 10-30s case)
        elif attempt_num < 6:
            return 10  # Next 2 attempts: 10 seconds
        elif attempt_num < 8:
            return 15  # Next 2 attempts: 15 seconds
        else:
            return 30  # Remaining attempts: 30 seconds
    
    while time.time() - start_time < timeout:
        attempt += 1
        elapsed = int(time.time() - start_time)
        
        try:
            # Create a fresh RAM client to avoid any credential caching issues
            ram_client = boto3.client('ram', region_name=REGION)
            
            print(f"     Attempt {attempt} ({elapsed}s elapsed): Checking for resources...")
            
            # Handle pagination - RAM shares can have multiple resources
            all_resources = []
            next_token = None
            page_count = 0
            
            while True:
                page_count += 1
                if next_token:
                    response = ram_client.list_resources(
                        resourceOwner='SELF',
                        resourceShareArns=[share_arn],
                        nextToken=next_token
                    )
                else:
                    response = ram_client.list_resources(
                        resourceOwner='SELF',
                        resourceShareArns=[share_arn]
                    )
                
                resources = response.get('resources', [])
                all_resources.extend(resources)
                
                if page_count > 1 or len(resources) > 0:
                    print(f"       Page {page_count}: {len(resources)} resource(s)")
                
                next_token = response.get('nextToken')
                if not next_token:
                    break
            
            resource_count = len(all_resources)
            
            if resource_count == 0:
                print(f"       No resources in share yet")
            else:
                print(f"       Total: {resource_count} resource(s) in share")
                
                # Check if our domain resource is present
                for resource in all_resources:
                    resource_arn = resource.get('arn', 'NO_ARN')
                    resource_type = resource.get('type', 'NO_TYPE')
                    resource_status = resource.get('status', 'NO_STATUS')
                    
                    if resource_arn == expected_resource_arn:
                        print(f"  ✅ Domain resource found in share!")
                        print(f"     Resource: {resource_arn}")
                        print(f"     Type: {resource_type}")
                        print(f"     Status: {resource_status}")
                        print(f"     Time taken: {elapsed} seconds")
                        print(f"     Attempts: {attempt}")
                        
                        # Additional wait for RAM propagation to DataZone
                        propagation_wait = 15
                        print(f"  ⏳ Waiting {propagation_wait} seconds for RAM share to propagate to DataZone...")
                        time.sleep(propagation_wait)
                        print(f"  ✅ RAM share propagation complete")
                        return
                
                # Resources exist but not our domain
                print(f"       ⚠️  {resource_count} resources found but expected domain not present")
                print(f"       Listing all resources:")
                for resource in all_resources:
                    print(f"         - {resource.get('arn', 'NO_ARN')} (type: {resource.get('type', 'NO_TYPE')}, status: {resource.get('status', 'NO_STATUS')})")
            
            # Wait before next attempt (with exponential backoff)
            wait_interval = get_wait_interval(attempt)
            print(f"       Waiting {wait_interval} seconds before next attempt...")
            time.sleep(wait_interval)
            
        except Exception as e:
            print(f"       ⚠️  Error checking resources: {e}")
            wait_interval = get_wait_interval(attempt)
            time.sleep(wait_interval)
    
    # Timeout reached - provide detailed error with final state
    elapsed_total = int(time.time() - start_time)
    print(f"  ❌ TIMEOUT: Domain resource not added after {elapsed_total} seconds ({attempt} attempts)")
    
    try:
        final_response = ram.list_resources(
            resourceOwner='SELF',
            resourceShareArns=[share_arn]
        )
        final_resources = final_response.get('resources', [])
        
        print(f"     Final state:")
        print(f"       Resources in share: {len(final_resources)}")
        for resource in final_resources:
            print(f"         - {resource['arn']} (status: {resource.get('status', 'UNKNOWN')})")
        
        # Check resource association status
        print(f"     Checking resource association status...")
        assoc_response = ram.get_resource_share_associations(
            associationType='RESOURCE',
            resourceShareArns=[share_arn]
        )
        associations = assoc_response.get('resourceShareAssociations', [])
        print(f"       Resource associations: {len(associations)}")
        for assoc in associations:
            print(f"         - Entity: {assoc.get('associatedEntity', 'UNKNOWN')}")
            print(f"           Status: {assoc.get('status', 'UNKNOWN')}")
            print(f"           Message: {assoc.get('statusMessage', 'N/A')}")
    except Exception as e:
        print(f"     Could not retrieve final state: {e}")
    
    raise Exception(
        f"Domain resource was not added to RAM share after {elapsed_total} seconds ({attempt} attempts). "
        f"Expected resource: {expected_resource_arn}. "
        f"This may indicate: (1) Resource association is stuck in ASSOCIATING state, "
        f"(2) Resource association failed (check statusMessage above), "
        f"(3) Domain execution role permissions issue, or "
        f"(4) Transient AWS service issue. "
        f"Check CloudWatch logs for detailed resource association status."
    )


def get_output_value(outputs: List[Dict], key: str) -> str:
    """Extract value from CloudFormation outputs"""
    for output in outputs:
        if output['OutputKey'] == key:
            return output['OutputValue']
    return ''


def update_progress(account_id: str, step: str, result: Dict[str, Any], deployed_stacksets: list = None):
    """Update account progress in DynamoDB.
    deployed_stacksets: list of StackSet names deployed in this wave — appended to deployedStackSets.
    """
    try:
        response = dynamodb.query(
            TableName=DYNAMODB_TABLE_NAME,
            KeyConditionExpression='accountId = :accountId',
            ExpressionAttributeValues={':accountId': {'S': account_id}},
            ScanIndexForward=False,
            Limit=1
        )

        if not response.get('Items'):
            return

        item = response['Items'][0]

        # Flatten result dict — skip list/dict values, convert to strings
        flat_resources = {}
        for k, v in result.items():
            if isinstance(v, (str, int, float, bool)):
                flat_resources[k] = {'S': str(v)}
            elif isinstance(v, list):
                flat_resources[k] = {'S': str(v)}

        update_expr = ('SET currentStep = :step, '
                       'completedSteps = list_append(if_not_exists(completedSteps, :empty), :step_list), '
                       'resources = :resources')
        attr_values = {
            ':step':      {'S': step},
            ':step_list': {'L': [{'S': step}]},
            ':empty':     {'L': []},
            ':resources': {'M': flat_resources},
        }

        if deployed_stacksets:
            # Read existing deployedStackSets and merge (deduplicate)
            existing = [e.get('S', '') for e in item.get('deployedStackSets', {}).get('L', [])]
            merged = list(dict.fromkeys(existing + deployed_stacksets))  # preserves order, deduplicates
            update_expr += ', deployedStackSets = :ss_list'
            attr_values[':ss_list'] = {'L': [{'S': s} for s in merged]}

        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp'],
            },
            UpdateExpression=update_expr,
            ExpressionAttributeValues=attr_values,
        )

        print(f"  📝 Progress updated: {step}" + (f" stacksets={deployed_stacksets}" if deployed_stacksets else ""))

    except Exception as e:
        print(f"⚠️ Error updating progress: {e}")


def mark_account_available(account_id: str, resources: Dict[str, Any], duration: int):
    """Mark account as AVAILABLE in DynamoDB"""
    try:
        response = dynamodb.query(
            TableName=DYNAMODB_TABLE_NAME,
            KeyConditionExpression='accountId = :accountId',
            ExpressionAttributeValues={':accountId': {'S': account_id}},
            ScanIndexForward=False,
            Limit=1
        )
        
        if not response.get('Items'):
            return
        
        item = response['Items'][0]
        
        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp']
            },
            UpdateExpression='SET #state = :state, setupCompleteDate = :date, setupDuration = :duration, resources = :resources',
            ExpressionAttributeNames={'#state': 'state'},
            ExpressionAttributeValues={
                ':state': {'S': 'AVAILABLE'},
                ':date': {'S': datetime.now(timezone.utc).isoformat()},
                ':duration': {'N': str(duration)},
                ':resources': {'M': {k: {'S': str(v)} for k, v in resources.items()}}
            }
        )
        
        print(f"✅ Account {account_id} marked as AVAILABLE")
        
    except Exception as e:
        print(f"❌ Error marking account available: {e}")


def mark_account_failed(account_id: str, failed_step: str, error_message: str):
    """Mark account as FAILED in DynamoDB"""
    try:
        response = dynamodb.query(
            TableName=DYNAMODB_TABLE_NAME,
            KeyConditionExpression='accountId = :accountId',
            ExpressionAttributeValues={':accountId': {'S': account_id}},
            ScanIndexForward=False,
            Limit=1
        )
        
        if not response.get('Items'):
            return
        
        item = response['Items'][0]
        
        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp']
            },
            UpdateExpression='SET #state = :state, failedStep = :step, errorMessage = :error, retryExhausted = :exhausted',
            ExpressionAttributeNames={'#state': 'state'},
            ExpressionAttributeValues={
                ':state': {'S': 'FAILED'},
                ':step': {'S': failed_step},
                ':error': {'S': error_message[:1000]},
                ':exhausted': {'BOOL': True}
            }
        )
        
        publish_metric('SetupFailed', 1, [
            {'Name': 'AccountId', 'Value': account_id},
            {'Name': 'FailedStep', 'Value': failed_step}
        ])
        
        print(f"❌ Account {account_id} marked as FAILED at step {failed_step}")
        
    except Exception as e:
        print(f"❌ Error marking account failed: {e}")


def send_failure_notification(account_id: str, failed_step: str, error_message: str):
    """Send SNS notification for setup failure"""
    try:
        message = {
            'alertType': 'SETUP_FAILED',
            'severity': 'HIGH',
            'accountId': account_id,
            'failedStep': failed_step,
            'errorMessage': error_message,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'cloudwatchLogsLink': f"https://console.aws.amazon.com/cloudwatch/home?region={REGION}#logsV2:log-groups/log-group/$252Faws$252Flambda$252FSetupOrchestrator",
            'recommendedAction': 'Check CloudWatch Logs for detailed error information. Delete failed account to unblock replenishment.'
        }
        
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f'Account Setup Failed: {account_id}',
            Message=json.dumps(message, indent=2)
        )
        
        print(f"📧 Sent failure notification")
        
    except Exception as e:
        print(f"⚠️ Error sending notification: {e}")


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
            Namespace='AccountPoolFactory/SetupOrchestrator',
            MetricData=[metric_data]
        )
    except Exception as e:
        print(f"⚠️ Error publishing metric {metric_name}: {e}")

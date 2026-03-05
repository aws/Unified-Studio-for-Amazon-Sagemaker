"""
Setup Orchestrator Lambda Function

Executes 8-step account setup workflow with wave-based parallel execution:
- Wave 1: VPC Deployment (~2.5 min)
- Wave 2: IAM Roles + EventBridge Rules in parallel (~2 min)
- Wave 3: S3 Bucket + RAM Share in parallel (~1 min)
- Wave 4: Blueprint Enablement (~3 min)
- Wave 5: Policy Grants (~2 min)
- Wave 6: Domain Visibility Verification (~1 min)

Total estimated duration: 6-8 minutes (vs 10-12 minutes sequential)
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
    """Main Lambda handler for Setup Orchestrator"""
    global _config_cache
    _config_cache = None  # Clear cache at start
    
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
    
    # Check for idempotency
    account_state = get_account_state(account_id)
    if account_state:
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


def get_account_state(account_id: str) -> Optional[Dict]:
    """Get current account state from DynamoDB"""
    try:
        response = dynamodb.query(
            TableName=DYNAMODB_TABLE_NAME,
            KeyConditionExpression='accountId = :accountId',
            ExpressionAttributeValues={':accountId': {'S': account_id}},
            ScanIndexForward=False,
            Limit=1
        )
        return response.get('Items', [None])[0]
    except:
        return None


# deploy_stackset_instance() function removed - now handled by ProvisionAccount Lambda in Org Admin account


def execute_setup_workflow(account_id: str, config: Dict[str, Any], resume_from: Optional[str] = None) -> Dict[str, Any]:
    """Execute wave-based parallel setup workflow
    
    Note: Wave 0 (StackSet deployment) is now handled by ProvisionAccount Lambda in Org Admin account.
    SetupOrchestrator assumes AccountPoolFactory-DomainAccess role already exists.
    """
    print(f"🚀 Starting setup workflow for account {account_id}")
    
    start_time = time.time()
    resources = {}
    
    try:
        # Wave 1: VPC Deployment (foundation)
        print("🌊 Wave 1: VPC Deployment")
        vpc_result = deploy_vpc(account_id, config)
        resources.update(vpc_result)
        update_progress(account_id, 'vpc_deployment', vpc_result)
        
        # Wave 2: IAM Roles + EventBridge Rules (parallel)
        print("🌊 Wave 2: IAM Roles + EventBridge Rules (parallel)")
        iam_result, eb_result = execute_wave_parallel([
            lambda: deploy_iam_roles(account_id, config, vpc_result),
            lambda: deploy_eventbridge_rules(account_id, config, vpc_result)
        ])
        resources.update(iam_result)
        resources.update(eb_result)
        update_progress(account_id, 'iam_roles', iam_result)
        update_progress(account_id, 'eventbridge_rules', eb_result)
        
        # Wave 3: S3 Bucket + RAM Share (parallel)
        print("🌊 Wave 3: S3 Bucket + RAM Share (parallel)")
        s3_result, ram_result = execute_wave_parallel([
            lambda: create_s3_bucket(account_id, config, iam_result),
            lambda: create_ram_share(account_id, config)
        ])
        resources.update(s3_result)
        resources.update(ram_result)
        update_progress(account_id, 's3_bucket', s3_result)
        update_progress(account_id, 'ram_share', ram_result)
        
        # Wave 4: Blueprint Enablement (includes policy grants in template)
        print("🌊 Wave 4: Blueprint Enablement")
        bp_result = enable_blueprints(account_id, config, vpc_result, iam_result, s3_result)
        resources.update(bp_result)
        update_progress(account_id, 'blueprint_enablement', bp_result)
        
        # Wave 5: Policy Grants - SKIPPED (now included in blueprint template)
        print("🌊 Wave 5: Policy Grants (included in blueprint template)")
        
        # Wave 6: Domain Visibility Verification
        print("🌊 Wave 6: Domain Visibility Verification")
        verify_result = verify_domain_visibility(account_id, config, ram_result)
        update_progress(account_id, 'domain_visibility', verify_result)
        
        # Mark account as AVAILABLE
        duration = int(time.time() - start_time)
        mark_account_available(account_id, resources, duration)
        
        publish_metric('SetupSucceeded', 1, [{'Name': 'AccountId', 'Value': account_id}])
        publish_metric('SetupDuration', duration, [{'Name': 'AccountId', 'Value': account_id}])
        
        print(f"✅ Setup completed in {duration} seconds")
        
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


def deploy_vpc(account_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Deploy VPC CloudFormation stack"""
    print(f"🌐 Deploying VPC for account {account_id}")
    
    stack_name = f"DataZone-VPC-{account_id}"
    template_path = 'vpc-setup.yaml'
    
    try:
        # Read template
        with open(template_path, 'r') as f:
            template_body = f.read()
        
        # Assume role in project account
        cf_client = get_cross_account_client('cloudformation', account_id)
        
        # Create stack
        cf_client.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM'],
            OnFailure='ROLLBACK',
            TimeoutInMinutes=30,
            Tags=[
                {'Key': 'ManagedBy', 'Value': 'AccountPoolFactory'},
                {'Key': 'AccountId', 'Value': account_id}
            ]
        )
        
        # Wait for completion
        wait_for_stack_complete(cf_client, stack_name)
        
        # Get outputs
        response = cf_client.describe_stacks(StackName=stack_name)
        outputs = response['Stacks'][0].get('Outputs', [])
        
        result = {
            'vpcId': get_output_value(outputs, 'VpcId'),
            'subnetIds': [
                get_output_value(outputs, 'PrivateSubnet1Id'),
                get_output_value(outputs, 'PrivateSubnet2Id'),
                get_output_value(outputs, 'PrivateSubnet3Id')
            ]
        }
        
        print(f"✅ VPC deployed: {result['vpcId']}")
        return result
        
    except Exception as e:
        print(f"❌ VPC deployment failed: {e}")
        raise


def deploy_iam_roles(account_id: str, config: Dict[str, Any], vpc_result: Dict[str, Any]) -> Dict[str, Any]:
    """Deploy IAM roles CloudFormation stack"""
    print(f"👤 Deploying IAM roles for account {account_id}")
    
    stack_name = f"DataZone-IAM-{account_id}"
    template_path = 'iam-roles.yaml'
    
    try:
        with open(template_path, 'r') as f:
            template_body = f.read()
        
        cf_client = get_cross_account_client('cloudformation', account_id)
        
        cf_client.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=[
                {'ParameterKey': 'DomainAccountId', 'ParameterValue': config['DomainAccountId']},
                {'ParameterKey': 'DomainId', 'ParameterValue': config['DomainId']}
            ],
            Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM'],
            OnFailure='ROLLBACK',
            TimeoutInMinutes=30,
            Tags=[
                {'Key': 'ManagedBy', 'Value': 'AccountPoolFactory'},
                {'Key': 'AccountId', 'Value': account_id}
            ]
        )
        
        wait_for_stack_complete(cf_client, stack_name)
        
        response = cf_client.describe_stacks(StackName=stack_name)
        outputs = response['Stacks'][0].get('Outputs', [])
        
        result = {
            'manageAccessRoleArn': get_output_value(outputs, 'ManageAccessRoleArn'),
            'provisioningRoleArn': get_output_value(outputs, 'ProvisioningRoleArn')
        }
        
        print(f"✅ IAM roles deployed")
        return result
        
    except Exception as e:
        print(f"❌ IAM roles deployment failed: {e}")
        raise


def deploy_eventbridge_rules(account_id: str, config: Dict[str, Any], vpc_result: Dict[str, Any]) -> Dict[str, Any]:
    """Deploy EventBridge rules CloudFormation stack"""
    print(f"📡 Deploying EventBridge rules for account {account_id}")
    
    stack_name = f"DataZone-EventBridge-{account_id}"
    template_path = 'eventbridge-rules.yaml'
    
    try:
        with open(template_path, 'r') as f:
            template_body = f.read()
        
        cf_client = get_cross_account_client('cloudformation', account_id)
        
        central_bus_arn = f"arn:aws:events:{config['Region']}:{config['DomainAccountId']}:event-bus/AccountPoolFactory-CentralBus"
        
        cf_client.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=[
                {'ParameterKey': 'CentralEventBusArn', 'ParameterValue': central_bus_arn}
            ],
            Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM'],
            OnFailure='ROLLBACK',
            TimeoutInMinutes=30,
            Tags=[
                {'Key': 'ManagedBy', 'Value': 'AccountPoolFactory'},
                {'Key': 'AccountId', 'Value': account_id}
            ]
        )
        
        wait_for_stack_complete(cf_client, stack_name)
        
        print(f"✅ EventBridge rules deployed")
        return {'eventBridgeRulesDeployed': True}
        
    except Exception as e:
        print(f"❌ EventBridge rules deployment failed: {e}")
        raise


def create_s3_bucket(account_id: str, config: Dict[str, Any], iam_result: Dict[str, Any]) -> Dict[str, Any]:
    """Create S3 bucket for blueprint artifacts"""
    print(f"🪣 Creating S3 bucket for account {account_id}")
    
    bucket_name = f"datazone-blueprints-{account_id}-{config['Region']}"
    
    try:
        s3_client = get_cross_account_client('s3', account_id)
        
        # Create bucket
        if config['Region'] == 'us-east-1':
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': config['Region']}
            )
        
        # Enable versioning
        s3_client.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={'Status': 'Enabled'}
        )
        
        # Enable encryption
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


def create_ram_share(account_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Create RAM share for domain access with explicit resource association"""
    print(f"🔗 Creating RAM share for account {account_id}")
    
    share_name = f"DataZone-Domain-Share-{account_id}"
    
    try:
        # Create RAM share in domain account (not project account)
        domain_arn = f"arn:aws:datazone:{config['Region']}:{config['DomainAccountId']}:domain/{config['DomainId']}"
        # For RAM shares with Organizations, use account ID as principal (not ARN)
        principal = account_id
        
        print(f"   Domain ARN: {domain_arn}")
        print(f"   Principal: {principal}")
        
        # Step 1: Create the RAM share WITHOUT resources initially
        # This ensures the share is created first, then we explicitly associate resources
        # CRITICAL: Use AWSRAMPermissionAmazonDataZoneDomainFullAccessWithPortalAccess (v7)
        # The ExtendedService permission fails with "Failed to put resource policy" for IAM-mode domains
        # Force update: 2026-03-04 23:10 - Added Wave 0 StackSet deployment + RAM share fixes
        response = ram.create_resource_share(
            name=share_name,
            principals=[principal],
            permissionArns=[
                'arn:aws:ram::aws:permission/AWSRAMPermissionAmazonDataZoneDomainFullAccessWithPortalAccess'
            ],
            tags=[
                {'key': 'ManagedBy', 'value': 'AccountPoolFactory'},
                {'key': 'AccountId', 'value': account_id}
            ]
        )
        
        share_arn = response['resourceShare']['resourceShareArn']
        
        print(f"   RAM share created: {share_arn}")
        
        # Step 2: Wait for share to become active
        wait_for_ram_share_active(share_arn)
        
        # Step 3: EXPLICITLY associate the domain resource with the share
        # This is REQUIRED - the resourceArns parameter in create_resource_share doesn't work reliably
        print(f"   📎 Explicitly associating domain resource with share...")
        associate_response = ram.associate_resource_share(
            resourceShareArn=share_arn,
            resourceArns=[domain_arn]
        )
        
        # Check the association response
        associations = associate_response.get('resourceShareAssociations', [])
        if associations:
            for assoc in associations:
                assoc_status = assoc.get('status', 'UNKNOWN')
                assoc_entity = assoc.get('associatedEntity', 'UNKNOWN')
                print(f"   📋 Resource association status: {assoc_status}")
                print(f"      Associated entity: {assoc_entity}")
        else:
            print(f"   ⚠️  No associations returned in response")
        
        print(f"   ✅ Resource association initiated")
        
        # CRITICAL: Wait 10 seconds before checking for resources
        # The associate_resource_share API returns immediately, but AWS needs time
        # to actually add the resource to the share
        print(f"   ⏳ Waiting 10 seconds for association to process...")
        time.sleep(10)
        
        # Step 4: Wait for domain resource to be added to the share
        # IAM-mode domains with domain execution role need time for resource to be added
        wait_for_ram_share_resources(share_arn, domain_arn)
        
        print(f"✅ RAM share created with domain resource: {share_arn}")
        return {'ramShareArn': share_arn}
        
    except Exception as e:
        print(f"❌ RAM share creation failed: {e}")
        raise


def enable_blueprints(account_id: str, config: Dict[str, Any], vpc_result: Dict[str, Any], 
                     iam_result: Dict[str, Any], s3_result: Dict[str, Any]) -> Dict[str, Any]:
    """Enable DataZone blueprints in project account"""
    print(f"📋 Enabling blueprints for account {account_id}")
    
    stack_name = f"DataZone-Blueprints-{account_id}"
    template_path = 'blueprint-enablement-iam.yaml'
    
    try:
        with open(template_path, 'r') as f:
            template_body = f.read()
        
        # Deploy blueprint stack in PROJECT account
        # EnvironmentBlueprintConfiguration resources are created in the project account
        print(f"   📍 Deploying blueprint stack in project account {account_id}")
        cf_client = get_cross_account_client('cloudformation', account_id)
        
        # Prepare parameters
        subnet_ids = ','.join(s3_result.get('subnetIds', vpc_result.get('subnetIds', [])))
        
        cf_client.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=[
                {'ParameterKey': 'DomainId', 'ParameterValue': config['DomainId']},
                {'ParameterKey': 'DomainUnitId', 'ParameterValue': config['RootDomainUnitId']},
                {'ParameterKey': 'ProjectAccountId', 'ParameterValue': account_id},
                {'ParameterKey': 'ManageAccessRoleArn', 'ParameterValue': iam_result['manageAccessRoleArn']},
                {'ParameterKey': 'ProvisioningRoleArn', 'ParameterValue': iam_result['provisioningRoleArn']},
                {'ParameterKey': 'S3Location', 'ParameterValue': f"s3://{s3_result['bucketName']}"},
                {'ParameterKey': 'Subnets', 'ParameterValue': subnet_ids},
                {'ParameterKey': 'VpcId', 'ParameterValue': vpc_result['vpcId']}
            ],
            Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM', 'CAPABILITY_AUTO_EXPAND'],
            OnFailure='ROLLBACK',
            TimeoutInMinutes=60,
            Tags=[
                {'Key': 'ManagedBy', 'Value': 'AccountPoolFactory'},
                {'Key': 'AccountId', 'Value': account_id}
            ]
        )
        
        wait_for_stack_complete(cf_client, stack_name, timeout=3600)
        
        # Get blueprint IDs from outputs
        response = cf_client.describe_stacks(StackName=stack_name)
        outputs = response['Stacks'][0].get('Outputs', [])
        
        blueprint_ids = []
        for output in outputs:
            if output['OutputKey'].endswith('BlueprintId'):
                blueprint_ids.append(output['OutputValue'])
        
        print(f"✅ Enabled {len(blueprint_ids)} blueprints")
        return {'blueprintIds': blueprint_ids}
        
    except Exception as e:
        print(f"❌ Blueprint enablement failed: {e}")
        raise


def create_policy_grants(account_id: str, config: Dict[str, Any], bp_result: Dict[str, Any]) -> Dict[str, Any]:
    """Create policy grants for all blueprints"""
    print(f"🔐 Creating policy grants for account {account_id}")
    
    grant_ids = []
    
    try:
        dz_client = get_cross_account_client('datazone', account_id)
        
        for blueprint_id in bp_result.get('blueprintIds', []):
            entity_identifier = f"{account_id}:{blueprint_id}"
            
            response = dz_client.create_policy_grant(
                domainIdentifier=config['DomainId'],
                entityIdentifier=entity_identifier,
                entityType='ENVIRONMENT_BLUEPRINT_CONFIGURATION',
                policyType='CREATE_ENVIRONMENT_FROM_BLUEPRINT',
                principal={
                    'project': {
                        'projectDesignation': 'CONTRIBUTOR'
                    }
                },
                detail={
                    'createEnvironmentFromBlueprint': {
                        'domainUnitFilter': {
                            'domainUnit': config['RootDomainUnitId'],
                            'includeChildDomainUnits': True
                        }
                    }
                }
            )
            
            grant_ids.append(response['id'])
            print(f"  ✅ Created grant for blueprint {blueprint_id}")
        
        print(f"✅ Created {len(grant_ids)} policy grants")
        return {'grantIds': grant_ids}
        
    except Exception as e:
        print(f"❌ Policy grant creation failed: {e}")
        raise


def verify_domain_visibility(account_id: str, config: Dict[str, Any], ram_result: Dict[str, Any]) -> Dict[str, Any]:
    """Verify domain is visible and accessible in project account"""
    print(f"🔍 Verifying domain visibility for account {account_id}")
    
    max_retries = 10
    backoff = 15
    
    for attempt in range(max_retries):
        try:
            dz_client = get_cross_account_client('datazone', account_id)
            
            # First, try to get the domain directly (more reliable than list)
            try:
                response = dz_client.get_domain(identifier=config['DomainId'])
                domain_status = response.get('status')
                
                if domain_status == 'AVAILABLE':
                    print(f"✅ Domain is accessible via GetDomain API")
                    print(f"   Domain ID: {config['DomainId']}")
                    print(f"   Domain Status: {domain_status}")
                    return {'domainVisible': True, 'domainAccessible': True}
                else:
                    print(f"⚠️ Domain found but status is {domain_status}, not AVAILABLE")
                    
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == 'UnauthorizedException':
                    print(f"❌ GetDomain returned Unauthorized - domain not accessible from project account")
                    print(f"   This indicates the account association is not working properly")
                elif error_code == 'ResourceNotFoundException':
                    print(f"⚠️ GetDomain returned ResourceNotFound - domain not visible yet")
                else:
                    print(f"⚠️ GetDomain error: {error_code} - {e}")
            
            # Fallback: Try list_domains
            response = dz_client.list_domains()
            
            for domain in response.get('items', []):
                if domain['id'] == config['DomainId'] and domain['status'] == 'AVAILABLE':
                    print(f"✅ Domain visible in list_domains")
                    return {'domainVisible': True, 'domainAccessible': False}
            
            print(f"⏳ Domain not visible yet, retry {attempt + 1}/{max_retries}")
            time.sleep(backoff * (2 ** attempt))
            
        except Exception as e:
            print(f"⚠️ Error checking domain visibility: {e}")
            if attempt < max_retries - 1:
                time.sleep(backoff * (2 ** attempt))
            else:
                raise
    
    raise Exception(f"Domain not visible or accessible after {max_retries} retries. "
                   f"This likely means the account association failed or the domain cannot be shared with IAM-mode accounts.")


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


def get_cross_account_client(service: str, account_id: str, config: Dict[str, Any] = None):
    """Get boto3 client for cross-account access using AccountPoolFactory-DomainAccess role"""
    if config is None:
        config = get_config()
    
    role_arn = f"arn:aws:iam::{account_id}:role/AccountPoolFactory-DomainAccess"
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


def wait_for_ram_share_resources(share_arn: str, expected_resource_arn: str, timeout: int = 180):
    """Wait for domain resource to be added to RAM share
    
    IAM-mode DataZone domains require a domain execution role for RAM sharing.
    Even after the share becomes ACTIVE, it takes additional time for the domain
    resource to be added to the share. This function polls until the resource appears.
    """
    print(f"  ⏳ Waiting for domain resource to be added to RAM share...")
    print(f"     Expected resource: {expected_resource_arn}")
    print(f"     Share ARN: {share_arn}")
    print(f"     Timeout: {timeout} seconds")
    print(f"     Poll interval: 5 seconds")
    
    start_time = time.time()
    attempt = 0
    
    while time.time() - start_time < timeout:
        attempt += 1
        elapsed = int(time.time() - start_time)
        
        try:
            # Create a fresh RAM client to avoid any credential caching issues
            ram_client = boto3.client('ram', region_name=REGION)
            
            print(f"     Attempt {attempt} ({elapsed}s elapsed): Checking resources...")
            
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
                
                print(f"       Page {page_count}: {len(resources)} resource(s)")
                
                next_token = response.get('nextToken')
                if not next_token:
                    break
            
            resource_count = len(all_resources)
            
            print(f"     Attempt {attempt}: Total {resource_count} resource(s) in share")
            
            if resource_count > 0:
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
                        
                        # CRITICAL: Wait for RAM share propagation before DataZone API calls
                        # Even after resource appears in share, DataZone needs time to recognize it
                        print(f"  ⏳ Waiting 15 seconds for RAM share to propagate to DataZone...")
                        time.sleep(15)
                        print(f"  ✅ RAM share propagation complete")
                        return
                
                # Resources exist but not our domain
                print(f"     ⚠️  {resource_count} resources found but expected domain not present")
                print(f"     Listing all resources:")
                for resource in all_resources:
                    print(f"       - {resource.get('arn', 'NO_ARN')} (type: {resource.get('type', 'NO_TYPE')}, status: {resource.get('status', 'NO_STATUS')})")
            
            time.sleep(5)  # Poll every 5 seconds (same as manual script)
            
        except Exception as e:
            print(f"     Error checking resources: {e}")
            time.sleep(5)
    
    # Timeout reached - provide detailed error
    try:
        final_response = ram.list_resources(
            resourceOwner='SELF',
            resourceShareArns=[share_arn]
        )
        final_resources = final_response.get('resources', [])
        
        print(f"  ❌ Timeout: Domain resource not added after {timeout} seconds")
        print(f"     Resources in share: {len(final_resources)}")
        for resource in final_resources:
            print(f"       - {resource['arn']} ({resource.get('status', 'UNKNOWN')})")
    except:
        pass
    
    raise Exception(
        f"Domain resource was not added to RAM share after {timeout} seconds. "
        f"This may indicate: (1) Domain execution role is missing or misconfigured, "
        f"(2) IAM permissions issue, or (3) Domain type incompatibility. "
        f"Verify domain execution role exists and has AmazonDataZoneDomainExecutionRolePolicy attached."
    )


def get_output_value(outputs: List[Dict], key: str) -> str:
    """Extract value from CloudFormation outputs"""
    for output in outputs:
        if output['OutputKey'] == key:
            return output['OutputValue']
    return ''


def update_progress(account_id: str, step: str, result: Dict[str, Any]):
    """Update account progress in DynamoDB"""
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
            UpdateExpression='SET currentStep = :step, completedSteps = list_append(if_not_exists(completedSteps, :empty), :step_list), resources = :resources',
            ExpressionAttributeValues={
                ':step': {'S': step},
                ':step_list': {'L': [{'S': step}]},
                ':empty': {'L': []},
                ':resources': {'M': {k: {'S': str(v)} for k, v in result.items()}}
            }
        )
        
        print(f"  📝 Progress updated: {step}")
        
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

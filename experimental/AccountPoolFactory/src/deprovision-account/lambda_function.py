"""
DeprovisionAccount Lambda Function

Runs in Domain Account (994753223772)
Safely cleans project accounts for reuse by removing non-approved CloudFormation stacks.

Responsibilities:
1. List all CloudFormation stacks in project account
2. Identify approved vs project stacks
3. Build dependency graph
4. Delete project stacks in reverse topological order
5. Handle deletion failures gracefully
6. Update DynamoDB state (CLEANING → AVAILABLE or FAILED)
7. Send notifications

Security:
- Assumes SMUS-AccountPoolFactory-DomainAccess role in project account
- Never deletes approved infrastructure stacks
- Comprehensive error handling and state management
"""

import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Set, Any, Optional
from collections import defaultdict, deque
import boto3
from botocore.exceptions import ClientError

# Initialize AWS clients
dynamodb = boto3.client('dynamodb')
sns = boto3.client('sns')
cloudwatch = boto3.client('cloudwatch')
sts = boto3.client('sts')

# Environment variables
import os
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'AccountPoolFactory-Accounts')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')
DOMAIN_ID = os.environ.get('DOMAIN_ID', '')
DELETION_TIMEOUT = int(os.environ.get('DELETION_TIMEOUT', '600'))
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '3'))

# Approved stack patterns (protected infrastructure)
APPROVED_STACK_PATTERNS = [
    'AccountPoolFactory-',
    'StackSet-',
]

APPROVED_STACK_NAMES = {
    'SMUS-AccountPoolFactory-StackSetExecutionRole',
    'SMUS-AccountPoolFactory-DomainAccess',
}


def lambda_handler(event, context):
    """Main Lambda handler for DeprovisionAccount"""
    print(f"📥 Received event: {json.dumps(event, indent=2)}")
    
    account_id = event.get('accountId')
    request_id = event.get('requestId', f"deprovision-{int(time.time())}")
    domain_id = event.get('domainId', DOMAIN_ID)
    stacks_to_delete = event.get('stacksToDelete')  # optional explicit list
    
    if not account_id:
        return {
            'status': 'ERROR',
            'message': 'Missing required parameter: accountId'
        }
    
    print(f"🧹 Starting deprovision for account: {account_id}")
    print(f"   Request ID: {request_id}")
    print(f"   Domain ID: {domain_id}")
    
    try:
        # Update state to CLEANING
        update_account_state(account_id, 'CLEANING', cleanupStartDate=datetime.now(timezone.utc).isoformat())
        
        # Perform cleanup
        cleanup_result = cleanup_account(account_id, domain_id, stacks_to_delete=stacks_to_delete)
        
        if cleanup_result['success']:
            # Leave state as CLEANING — caller (recycler) decides next state.
            # DeprovisionAccount's job is only to clean stacks, not manage
            # lifecycle transitions. The recycler will invoke SetupOrchestrator
            # next, and SetupOrchestrator will mark AVAILABLE on success.
            update_account_state(account_id, 'CLEANING',
                                 cleanupCompletedDate=datetime.now(timezone.utc).isoformat())
            
            # Publish success metric
            publish_metric('DeprovisionSucceeded', 1, [{'Name': 'AccountId', 'Value': account_id}])
            publish_metric('StacksDeleted', cleanup_result['stacks_deleted'], [{'Name': 'AccountId', 'Value': account_id}])
            
            # Send success notification
            send_success_notification(account_id, cleanup_result)
            
            print(f"✅ Deprovision complete: {account_id}")
            return {
                'status': 'SUCCESS',
                'accountId': account_id,
                'stacksDeleted': cleanup_result['stacks_deleted'],
                'message': 'Account cleaned, ready for re-setup'
            }
        else:
            # Mark account as FAILED
            mark_account_failed(account_id, cleanup_result)
            
            # Publish failure metric
            publish_metric('DeprovisionFailed', 1, [
                {'Name': 'AccountId', 'Value': account_id},
                {'Name': 'FailedStack', 'Value': cleanup_result.get('failed_stack', 'Unknown')}
            ])
            
            # Send failure notification
            send_failure_notification(account_id, cleanup_result)
            
            print(f"❌ Deprovision failed: {account_id}")
            return {
                'status': 'FAILED',
                'accountId': account_id,
                'failedStack': cleanup_result.get('failed_stack'),
                'errorMessage': cleanup_result.get('error_message'),
                'message': 'Account cleanup failed, manual intervention required'
            }
            
    except Exception as e:
        print(f"❌ Unexpected error during deprovision: {e}")
        
        # Mark account as FAILED
        error_details = {
            'failed_stack': 'Unknown',
            'error_message': str(e),
            'stacks_deleted': 0
        }
        mark_account_failed(account_id, error_details)
        
        # Publish failure metric
        publish_metric('DeprovisionFailed', 1, [{'Name': 'AccountId', 'Value': account_id}])
        
        return {
            'status': 'ERROR',
            'accountId': account_id,
            'message': str(e)
        }


def _remove_datazone_roles_from_lf_admins(account_id: str, domain_id: str):
    """TEMPORARY WORKAROUND: Remove datazone_usr_role_* from LF admins before cleanup.

    SetupOrchestrator adds these roles as LF admins for resource link visibility.
    We remove them here to avoid leaving stale LF admin entries after account reclaim.
    Non-fatal — cleanup continues even if this fails.

    TODO: Remove when proper LF tag-based access control is implemented.
    """
    try:
        role_arn = f"arn:aws:iam::{account_id}:role/SMUS-AccountPoolFactory-DomainAccess"
        assumed = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName='deprovision-lf-cleanup',
            ExternalId=domain_id,
            DurationSeconds=900)
        creds = assumed['Credentials']

        lf_client = boto3.client('lakeformation',
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken'],
            region_name=os.environ.get('AWS_REGION', 'us-east-2'))

        settings = lf_client.get_data_lake_settings()
        admins = settings['DataLakeSettings'].get('DataLakeAdmins', [])
        original_count = len(admins)

        # Filter out datazone_usr_role_* entries
        cleaned = [a for a in admins
                    if not a.get('DataLakePrincipalIdentifier', '').split('/')[-1].startswith('datazone_usr_role_')]
        removed = original_count - len(cleaned)

        if removed > 0:
            settings['DataLakeSettings']['DataLakeAdmins'] = cleaned
            lf_client.put_data_lake_settings(DataLakeSettings=settings['DataLakeSettings'])
            print(f"  ✅ Removed {removed} datazone_usr_role(s) from LF admins in {account_id}")
        else:
            print(f"  ℹ️  No datazone_usr_role LF admins to remove in {account_id}")

    except Exception as e:
        print(f"  ⚠️  Failed to remove datazone roles from LF admins in {account_id}: {e}")


def cleanup_account(account_id: str, domain_id: str, stacks_to_delete: list = None) -> Dict[str, Any]:
    """Clean project account by deleting non-approved stacks.

    If stacks_to_delete is provided, only those specific stack names are deleted
    (used by cleanupStacks action to precisely remove direct CF stacks).
    Otherwise all non-approved stacks are discovered and deleted.
    """
    
    start_time = time.time()
    
    try:
        # TEMPORARY WORKAROUND: Remove datazone_usr_role_* from LF admins before cleanup.
        # SetupOrchestrator adds these as LF admins for resource link visibility.
        # We remove them here to avoid leaving stale LF admin entries after account reclaim.
        # TODO: Remove when proper LF tag-based access control is implemented.
        _remove_datazone_roles_from_lf_admins(account_id, domain_id)

        # Assume role in project account
        print(f"🔐 Assuming role in account {account_id}")
        cf_client = get_cloudformation_client(account_id, domain_id)
        
        # List all stacks
        print(f"📋 Listing all stacks...")
        all_stacks = list_all_stacks(cf_client)
        print(f"   Found {len(all_stacks)} total stacks")

        # Load per-account approved StackSets from DynamoDB
        deployed_stacksets = _get_deployed_stacksets(account_id)
        print(f"   deployedStackSets: {deployed_stacksets or '(none — using fallback patterns)'}")

        # Categorize stacks
        approved_stacks = []
        project_stacks = []

        if stacks_to_delete is not None:
            # Explicit list — only delete named stacks, treat everything else as approved
            stack_name_set = set(stacks_to_delete)
            for stack in all_stacks:
                if stack['StackName'] in stack_name_set:
                    project_stacks.append(stack)
                else:
                    approved_stacks.append(stack)
            print(f"   Explicit stacksToDelete: targeting {len(project_stacks)} of {len(stack_name_set)} requested")
        else:
            for stack in all_stacks:
                if is_approved_stack(stack, deployed_stacksets):
                    approved_stacks.append(stack)
                else:
                    project_stacks.append(stack)
        print(f"   Approved stacks: {len(approved_stacks)}")
        print(f"   Project stacks to delete: {len(project_stacks)}")
        
        if approved_stacks:
            print(f"   Protected stacks: {[s['StackName'] for s in approved_stacks]}")
        
        if not project_stacks:
            print(f"✅ No project stacks to delete")
            return {
                'success': True,
                'stacks_deleted': 0,
                'duration': time.time() - start_time
            }
        
        # Build dependency graph
        print(f"🔗 Building dependency graph...")
        dependency_graph = build_dependency_graph(cf_client, project_stacks)
        
        # Determine deletion order
        print(f"📊 Determining deletion order...")
        deletion_order = reverse_topological_sort(dependency_graph)
        print(f"   Deletion order: {deletion_order}")
        
        # Delete stacks in order
        stacks_deleted = 0
        for stack_name in deletion_order:
            print(f"🗑️  Deleting stack: {stack_name}")
            
            try:
                delete_stack_safe(cf_client, stack_name)
                wait_for_stack_deletion(cf_client, stack_name, timeout=DELETION_TIMEOUT)
                stacks_deleted += 1
                print(f"   ✅ Stack deleted: {stack_name}")
                
            except Exception as e:
                print(f"   ❌ Failed to delete stack {stack_name}: {e}")
                return {
                    'success': False,
                    'failed_stack': stack_name,
                    'error_message': str(e),
                    'stacks_deleted': stacks_deleted,
                    'duration': time.time() - start_time
                }
        
        duration = time.time() - start_time
        print(f"✅ All project stacks deleted successfully in {duration:.1f}s")
        
        return {
            'success': True,
            'stacks_deleted': stacks_deleted,
            'duration': duration
        }
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        return {
            'success': False,
            'failed_stack': 'Unknown',
            'error_message': str(e),
            'stacks_deleted': 0,
            'duration': time.time() - start_time
        }


def get_cloudformation_client(account_id: str, domain_id: str):
    """Get CloudFormation client for project account"""
    
    role_arn = f"arn:aws:iam::{account_id}:role/SMUS-AccountPoolFactory-DomainAccess"
    
    assumed_role = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName='DeprovisionAccount',
        ExternalId=domain_id
    )
    
    credentials = assumed_role['Credentials']
    
    return boto3.client(
        'cloudformation',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken']
    )


def list_all_stacks(cf_client) -> List[Dict]:
    """List all stacks (excluding DELETED)"""
    
    stacks = []
    paginator = cf_client.get_paginator('list_stacks')
    
    # Exclude DELETE_COMPLETE stacks
    status_filter = [
        'CREATE_COMPLETE', 'CREATE_IN_PROGRESS', 'CREATE_FAILED',
        'ROLLBACK_COMPLETE', 'ROLLBACK_IN_PROGRESS', 'ROLLBACK_FAILED',
        'UPDATE_COMPLETE', 'UPDATE_IN_PROGRESS', 'UPDATE_ROLLBACK_COMPLETE',
        'UPDATE_ROLLBACK_IN_PROGRESS', 'UPDATE_ROLLBACK_FAILED',
        'DELETE_IN_PROGRESS', 'DELETE_FAILED'
    ]
    
    for page in paginator.paginate(StackStatusFilter=status_filter):
        stacks.extend(page['StackSummaries'])
    
    return stacks


def _get_deployed_stacksets(account_id: str) -> Set[str]:
    """Read deployedStackSets from the account's DynamoDB record.
    Returns a set of StackSet names (e.g. 'SMUS-AccountPoolFactory-DomainAccess').
    Falls back to empty set if not found.
    """
    try:
        resp = dynamodb.query(
            TableName=DYNAMODB_TABLE_NAME,
            KeyConditionExpression='accountId = :a',
            ExpressionAttributeValues={':a': {'S': account_id}},
            ScanIndexForward=False,
            Limit=1
        )
        items = resp.get('Items', [])
        if items:
            ss_list = items[0].get('deployedStackSets', {}).get('L', [])
            return {s.get('S', '') for s in ss_list if s.get('S')}
    except Exception as e:
        print(f'Warning: could not read deployedStackSets for {account_id}: {e}')
    return set()


def is_approved_stack(stack: Dict, deployed_stacksets: Set[str] = None) -> bool:
    """Check if stack is part of approved infrastructure.

    Prefers per-account deployedStackSets from DynamoDB.
    Falls back to hardcoded patterns for backward compat.
    """
    stack_name = stack['StackName']

    # StackSet-deployed stacks: name starts with StackSet-{StackSetName}-
    if deployed_stacksets:
        for ss_name in deployed_stacksets:
            if stack_name.startswith(f'StackSet-{ss_name}-'):
                return True
        # Also protect the StackSetExecution role stack
        if stack_name == 'SMUS-AccountPoolFactory-StackSetExecutionRole':
            return True
        # If we have a per-account list, don't fall through to hardcoded patterns
        # (only protect what's explicitly listed + the execution role)
        return False

    # Fallback: hardcoded patterns (backward compat for accounts without deployedStackSets)
    if stack_name in APPROVED_STACK_NAMES:
        return True
    for pattern in APPROVED_STACK_PATTERNS:
        if stack_name.startswith(pattern):
            return True
    if 'ParentId' in stack and stack['ParentId'].startswith('arn:aws:cloudformation'):
        return True
    return False


def build_dependency_graph(cf_client, stacks: List[Dict]) -> Dict[str, Set[str]]:
    """Build dependency graph from stack exports/imports
    
    Returns: Dict mapping stack_name -> set of stacks that depend on it
    """
    
    graph = defaultdict(set)
    stack_names = {s['StackName'] for s in stacks}
    
    # Get all exports
    exports = {}
    try:
        paginator = cf_client.get_paginator('list_exports')
        for page in paginator.paginate():
            for export in page['Exports']:
                exports[export['Name']] = export.get('ExportingStackId', '')
    except Exception as e:
        print(f"   ⚠️  Could not list exports: {e}")
    
    # For each stack, find what it imports
    for stack in stacks:
        stack_name = stack['StackName']
        
        try:
            # Get stack details
            response = cf_client.describe_stacks(StackName=stack_name)
            if not response['Stacks']:
                continue
            
            stack_detail = response['Stacks'][0]
            
            # Check for imports in parameters
            for param in stack_detail.get('Parameters', []):
                param_value = param.get('ParameterValue', '')
                
                # Check if parameter value matches an export
                if param_value in exports:
                    exporting_stack_id = exports[param_value]
                    # Extract stack name from ARN
                    exporting_stack_name = exporting_stack_id.split('/')[-2] if '/' in exporting_stack_id else ''
                    
                    if exporting_stack_name in stack_names:
                        # stack_name depends on exporting_stack_name
                        # So exporting_stack_name must be deleted AFTER stack_name
                        graph[exporting_stack_name].add(stack_name)
            
        except Exception as e:
            print(f"   ⚠️  Could not analyze stack {stack_name}: {e}")
    
    return graph


def reverse_topological_sort(graph: Dict[str, Set[str]]) -> List[str]:
    """Return deletion order using topological sort
    
    Stacks with no dependencies are deleted first.
    Stacks that others depend on are deleted last.
    """
    
    # Get all nodes
    all_nodes = set(graph.keys())
    for dependents in graph.values():
        all_nodes.update(dependents)
    
    # Calculate in-degree (number of dependencies)
    in_degree = {node: 0 for node in all_nodes}
    for node in graph:
        for dependent in graph[node]:
            in_degree[dependent] += 1
    
    # Start with nodes that have no dependencies
    queue = deque([node for node in all_nodes if in_degree[node] == 0])
    result = []
    
    while queue:
        node = queue.popleft()
        result.append(node)
        
        # Remove this node from graph
        for dependent in graph.get(node, []):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)
    
    # Check for cycles
    if len(result) != len(all_nodes):
        print(f"   ⚠️  Dependency cycle detected, using simple reverse order")
        return list(all_nodes)
    
    return result


def delete_stack_safe(cf_client, stack_name: str):
    """Delete stack with retry logic"""
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            cf_client.delete_stack(StackName=stack_name)
            return
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            
            if error_code == 'ValidationError' and 'does not exist' in str(e):
                # Stack already deleted
                print(f"   ℹ️  Stack already deleted: {stack_name}")
                return
            
            if attempt < MAX_RETRIES:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"   ⏳ Retry {attempt}/{MAX_RETRIES} after {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise


def wait_for_stack_deletion(cf_client, stack_name: str, timeout: int = 600):
    """Wait for stack deletion to complete"""
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            response = cf_client.describe_stacks(StackName=stack_name)
            
            if not response['Stacks']:
                # Stack deleted
                return
            
            status = response['Stacks'][0]['StackStatus']
            
            if status == 'DELETE_COMPLETE':
                return
            elif status == 'DELETE_FAILED':
                # Get failure reason
                events = cf_client.describe_stack_events(StackName=stack_name, MaxResults=10)
                failure_reason = 'Unknown'
                for event in events['StackEvents']:
                    if event.get('ResourceStatus') == 'DELETE_FAILED':
                        failure_reason = event.get('ResourceStatusReason', 'Unknown')
                        break
                raise Exception(f"Stack deletion failed: {failure_reason}")
            
            time.sleep(10)
            
        except ClientError as e:
            if 'does not exist' in str(e):
                # Stack deleted
                return
            raise
    
    raise Exception(f"Stack deletion timed out after {timeout} seconds")


def update_account_state(account_id: str, state: str, **kwargs):
    """Update DynamoDB account record"""
    
    try:
        # Get current record
        response = dynamodb.query(
            TableName=DYNAMODB_TABLE_NAME,
            KeyConditionExpression='accountId = :accountId',
            ExpressionAttributeValues={':accountId': {'S': account_id}},
            ScanIndexForward=False,
            Limit=1
        )
        
        if not response.get('Items'):
            print(f"⚠️  Account {account_id} not found in DynamoDB")
            return
        
        item = response['Items'][0]
        
        # Build update expression
        update_parts = ['#state = :state']
        attr_names = {'#state': 'state'}
        attr_values = {':state': {'S': state}}
        
        for key, value in kwargs.items():
            update_parts.append(f'{key} = :{key}')
            attr_values[f':{key}'] = {'S': value}
        
        update_expression = 'SET ' + ', '.join(update_parts)
        
        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': item['accountId'],
                'timestamp': item['timestamp']
            },
            UpdateExpression=update_expression,
            ExpressionAttributeNames=attr_names,
            ExpressionAttributeValues=attr_values
        )
        
        print(f"✅ Updated account state to {state}")
        
    except Exception as e:
        print(f"❌ Error updating account state: {e}")


def mark_account_available(account_id: str):
    """Mark account as AVAILABLE for reuse"""
    
    update_account_state(
        account_id,
        'AVAILABLE',
        cleanupCompletedDate=datetime.now(timezone.utc).isoformat()
    )


def mark_account_failed(account_id: str, error_details: Dict):
    """Mark account as FAILED with error details"""
    
    update_account_state(
        account_id,
        'FAILED',
        failedStep='deprovision',
        failedStack=error_details.get('failed_stack', 'Unknown'),
        errorMessage=error_details.get('error_message', 'Unknown error')[:1000]  # DynamoDB limit
    )


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
            Namespace='AccountPoolFactory/DeprovisionAccount',
            MetricData=[metric_data]
        )
    except Exception as e:
        print(f"⚠️  Error publishing metric {metric_name}: {e}")


def send_success_notification(account_id: str, result: Dict):
    """Send SNS notification for successful cleanup"""
    
    if not SNS_TOPIC_ARN:
        return
    
    try:
        message = {
            'alertType': 'DEPROVISION_SUCCESS',
            'severity': 'INFO',
            'accountId': account_id,
            'stacksDeleted': result['stacks_deleted'],
            'duration': f"{result['duration']:.1f}s",
            'message': f'Account {account_id} cleaned and returned to pool',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f'Account Cleanup Success: {account_id}',
            Message=json.dumps(message, indent=2)
        )
        
        print(f"📧 Sent success notification")
        
    except Exception as e:
        print(f"⚠️  Error sending notification: {e}")


def send_failure_notification(account_id: str, result: Dict):
    """Send SNS notification for failed cleanup"""
    
    if not SNS_TOPIC_ARN:
        return
    
    try:
        message = {
            'alertType': 'DEPROVISION_FAILED',
            'severity': 'HIGH',
            'accountId': account_id,
            'failedStack': result.get('failed_stack', 'Unknown'),
            'errorMessage': result.get('error_message', 'Unknown error'),
            'stacksDeleted': result.get('stacks_deleted', 0),
            'message': f'Account {account_id} cleanup failed, manual intervention required',
            'action': f'Investigate failed stack and retry cleanup or force account to AVAILABLE state',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f'Account Cleanup Failed: {account_id}',
            Message=json.dumps(message, indent=2)
        )
        
        print(f"📧 Sent failure notification")
        
    except Exception as e:
        print(f"⚠️  Error sending notification: {e}")

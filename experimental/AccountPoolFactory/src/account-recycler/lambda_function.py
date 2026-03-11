"""
AccountRecycler Lambda Function

Runs in Domain Account (994753223772)
Recycles failed, orphaned, and cleaning accounts back to AVAILABLE state.
This is the FIXER — it handles all repair operations.

Responsibilities:
1. Process single account or batch of accounts (high parallelism)
2. CLEANING: deprovision -> setup -> AVAILABLE
3. FAILED: classify by failure reason, fix accordingly:
   - NEEDS_STACKSET: deploy StackSet (via ProvisionAccount) -> setup -> AVAILABLE
   - NEEDS_SETUP: run SetupOrchestrator -> AVAILABLE
   - Other: retry deprovision -> setup, or mark DELETING if non-recoverable
4. ORPHANED: check DomainAccess role -> provision if needed -> setup -> AVAILABLE
5. AVAILABLE: no-op (idempotent), unless force=True

Cross-Account Access:
- Invokes DeprovisionAccount, SetupOrchestrator (same account)
- Invokes ProvisionAccount (cross-account in Org Admin) for StackSet fixes and ORPHANED accounts
"""

import json
import os
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict
import boto3
import botocore.config
from botocore.exceptions import ClientError

# Initialize AWS clients
dynamodb = boto3.client('dynamodb')
lambda_client = boto3.client('lambda')
# Lambda client with extended timeout for synchronous invocations of DeprovisionAccount
lambda_client_sync = boto3.client('lambda', config=botocore.config.Config(
    read_timeout=900,
    connect_timeout=10,
    retries={'max_attempts': 0}  # we handle retries ourselves
))
sqs = boto3.client('sqs')
sns = boto3.client('sns')
cloudwatch = boto3.client('cloudwatch')
ssm = boto3.client('ssm')
sts = boto3.client('sts')

# Environment variables
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'AccountPoolFactory-AccountState')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')
DOMAIN_ID = os.environ.get('DOMAIN_ID', '')
DOMAIN_ACCOUNT_ID = os.environ.get('DOMAIN_ACCOUNT_ID', '')
ORG_ADMIN_ACCOUNT_ID = os.environ.get('ORG_ADMIN_ACCOUNT_ID', '')
DEPROVISION_FUNCTION = os.environ.get('DEPROVISION_ACCOUNT_FUNCTION_NAME', 'DeprovisionAccount')
SETUP_FUNCTION = os.environ.get('SETUP_ORCHESTRATOR_FUNCTION_NAME', 'SetupOrchestrator')
SETUP_QUEUE_URL = os.environ.get('SETUP_QUEUE_URL', '')
PROVISION_FUNCTION_ARN = os.environ.get('PROVISION_ACCOUNT_FUNCTION_ARN', '')

# Non-recoverable error patterns
NON_RECOVERABLE_PATTERNS = [
    'account suspended', 'account closed', 'account not found',
    'organizationaccountaccessrole', 'access denied permanently'
]


# ============================================================
# Retry / backoff helpers
# ============================================================

def retry_with_backoff(fn, max_retries=3, base_delay=1.0, max_delay=10.0):
    """Call fn() with exponential backoff on throttling errors."""
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except ClientError as e:
            code = e.response['Error']['Code']
            if code in ('TooManyRequestsException', 'Throttling', 'ThrottlingException',
                        'RequestLimitExceeded', 'ServiceUnavailableException') and attempt < max_retries:
                delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                print(f"  Throttled ({code}), retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                raise


# ============================================================
# Config
# ============================================================

def load_config():
    """Load configuration from SSM Parameter Store"""
    try:
        config = {}
        next_token = None
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
            next_token = response.get('NextToken')
            if not next_token:
                break
        config.setdefault('MaxRecycleRetries', '3')
        config.setdefault('MaxConcurrentRecycles', '10')
        return config
    except Exception as e:
        print(f"Warning: Failed to load SSM parameters: {e}")
        return {'MaxRecycleRetries': '3', 'MaxConcurrentRecycles': '10'}



# ============================================================
# Lambda handler
# ============================================================

def lambda_handler(event, context):
    """Main handler for AccountRecycler.

    The fixer: handles all repair operations for unhealthy accounts.
    Supports force=true to re-recycle AVAILABLE accounts (e.g. incomplete setup).

    Self-healing: if work remains and Lambda timeout is near (<120s), re-invokes
    itself asynchronously so processing continues without manual intervention.
    """
    print(f"Received event: {json.dumps(event, indent=2)}")

    config = load_config()
    max_retries = int(config.get('MaxRecycleRetries', '3'))
    max_concurrent = int(config.get('MaxConcurrentRecycles', '10'))

    account_id = event.get('accountId')
    recycle_all = event.get('recycleAll', False)
    account_ids = event.get('accountIds', [])
    force = event.get('force', False)
    update_blueprints = event.get('updateBlueprints', False)

    results = []

    if update_blueprints:
        # Update blueprints on all AVAILABLE accounts in waves with self-trigger
        available = get_available_accounts()
        print(f"Found {len(available)} AVAILABLE accounts to update blueprints")
        batch_size = max_concurrent
        offset = 0
        while offset < len(available):
            remaining_ms = context.get_remaining_time_in_millis()
            if remaining_ms < 120_000:
                still_remaining = get_available_accounts()
                # Only re-trigger if there are accounts we haven't processed yet
                unprocessed = [a for a in still_remaining if a not in [r['accountId'] for r in results]]
                if unprocessed:
                    print(f"Timeout approaching, {len(unprocessed)} accounts remain — self-triggering...")
                    _self_trigger(event)
                break
            wave = available[offset:offset + batch_size]
            wave_results = update_blueprints_batch(wave, max_concurrent)
            results.extend(wave_results)
            offset += batch_size

        succeeded = sum(1 for r in results if r['result'] == 'UPDATED')
        failed = sum(1 for r in results if r['result'] == 'FAILED')
        return {
            'status': 'SUCCESS',
            'summary': {'totalProcessed': len(results), 'succeeded': succeeded, 'failed': failed},
            'results': results
        }

    elif event.get('action') == 'cleanupStacks':
        # Strip direct CF stacks from AVAILABLE accounts so reconciliation can
        # re-setup them via the new StackSet-driven flow.
        target_ids = event.get('accountIds') or (get_available_accounts() if event.get('all') else [])
        print(f"cleanupStacks: targeting {len(target_ids)} AVAILABLE accounts")
        offset = 0
        while offset < len(target_ids):
            remaining_ms = context.get_remaining_time_in_millis()
            if remaining_ms < 120_000:
                unprocessed = target_ids[offset:]
                if unprocessed:
                    print(f"Timeout approaching, {len(unprocessed)} accounts remain — self-triggering...")
                    _self_trigger({'action': 'cleanupStacks', 'accountIds': unprocessed})
                break
            wave = target_ids[offset:offset + max_concurrent]
            wave_results = cleanup_stacks_batch(wave, max_concurrent)
            results.extend(wave_results)
            offset += max_concurrent

        succeeded = sum(1 for r in results if r['result'] == 'CLEANED')
        failed = sum(1 for r in results if r['result'] == 'FAILED')
        skipped = sum(1 for r in results if r['result'] == 'SKIPPED')
        return {
            'status': 'SUCCESS',
            'summary': {'totalProcessed': len(results), 'succeeded': succeeded,
                        'failed': failed, 'skipped': skipped},
            'results': results
        }

    elif account_id:
        result = recycle_account(account_id, max_retries, force=force)
        results.append(result)
    elif account_ids:
        results = recycle_batch(account_ids, max_concurrent, max_retries, force=force)
    elif recycle_all:
        recyclable = get_recyclable_accounts()
        print(f"Found {len(recyclable)} recyclable accounts")

        # Pre-process: batch-fix all NEEDS_STACKSET accounts first (single StackSet operation)
        # This avoids OperationInProgressException from concurrent single-account calls
        stackset_accounts = _get_needs_stackset_accounts(recyclable)
        if stackset_accounts:
            print(f"Pre-processing {len(stackset_accounts)} NEEDS_STACKSET accounts as batch...")
            try:
                ok, failed_map = ensure_stackset_batch(stackset_accounts)
                # Mark batch failures so they're retried next wave
                for acct_id, err in failed_map.items():
                    item = get_latest_record(acct_id)
                    if item:
                        mark_failed(acct_id, item, err, 'batch_stackset')
                # Remove stackset accounts from recyclable — handle_failed will now
                # see DomainAccess role OK and route to NEEDS_SETUP path
                print(f"Batch StackSet done: {len(ok)} ready, {len(failed_map)} failed")
            except Exception as e:
                print(f"Batch StackSet fix failed: {e} — accounts will retry individually next wave")

        # Process in waves so we can self-trigger if timeout is near
        batch_size = max_concurrent
        offset = 0
        while offset < len(recyclable):
            # Check remaining time — if <120s, self-trigger and stop
            remaining_ms = context.get_remaining_time_in_millis()
            if remaining_ms < 120_000:
                still_remaining = get_recyclable_accounts()
                if still_remaining:
                    print(f"Timeout approaching ({remaining_ms}ms left), {len(still_remaining)} accounts remain — self-triggering...")
                    _self_trigger(event)
                break

            wave = recyclable[offset:offset + batch_size]
            wave_results = recycle_batch(wave, max_concurrent, max_retries, force=force)
            results.extend(wave_results)
            offset += batch_size
    else:
        return {'status': 'ERROR', 'message': 'Provide accountId, accountIds, or recycleAll=true'}

    succeeded = sum(1 for r in results if r['result'] == 'RECYCLED')
    failed = sum(1 for r in results if r['result'] == 'FAILED')
    skipped = sum(1 for r in results if r['result'] == 'SKIPPED')

    publish_metric('BatchRecyclingCompleted', 1, [
        {'Name': 'TotalProcessed', 'Value': str(len(results))},
        {'Name': 'Succeeded', 'Value': str(succeeded)},
        {'Name': 'Failed', 'Value': str(failed)}
    ])

    return {
        'status': 'SUCCESS',
        'summary': {
            'totalProcessed': len(results),
            'succeeded': succeeded,
            'failed': failed,
            'skipped': skipped
        },
        'results': results
    }


def _self_trigger(original_event):
    """Re-invoke this Lambda asynchronously to continue processing remaining accounts."""
    try:
        lambda_client.invoke(
            FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'AccountRecycler'),
            InvocationType='Event',
            Payload=json.dumps(original_event)
        )
        print("Self-triggered next recycler wave")
    except Exception as e:
        print(f"Warning: Failed to self-trigger: {e}")


def _get_needs_stackset_accounts(account_ids):
    """From a list of recyclable account IDs, return those with NEEDS_STACKSET failure reason."""
    result = []
    for account_id in account_ids:
        item = get_latest_record(account_id)
        if not item:
            continue
        note = item.get('reconciliationNote', {}).get('S', '')
        err = item.get('errorMessage', {}).get('S', '')
        if 'NEEDS_STACKSET' in note or 'NEEDS_STACKSET' in err:
            # Only include if DomainAccess role is actually missing (not just stale note)
            if not check_domain_access_role(account_id):
                result.append(account_id)
    return result


def get_recyclable_accounts():
    """Query DynamoDB for accounts in recyclable states"""
    account_ids = []
    for state in ['CLEANING', 'FAILED', 'ORPHANED']:
        try:
            response = dynamodb.query(
                TableName=DYNAMODB_TABLE_NAME,
                IndexName='StateIndex',
                KeyConditionExpression='#state = :state',
                ExpressionAttributeNames={'#state': 'state'},
                ExpressionAttributeValues={':state': {'S': state}}
            )
            for item in response.get('Items', []):
                acct_id = item.get('accountId', {}).get('S', '')
                if acct_id:
                    account_ids.append(acct_id)
        except Exception as e:
            print(f"Error querying {state} accounts: {e}")
    print(f"Found {len(account_ids)} recyclable accounts")
    return account_ids


def get_available_accounts():
    """Query DynamoDB for all AVAILABLE accounts"""
    account_ids = []
    try:
        paginator_kwargs = {
            'TableName': DYNAMODB_TABLE_NAME,
            'IndexName': 'StateIndex',
            'KeyConditionExpression': '#state = :state',
            'ExpressionAttributeNames': {'#state': 'state'},
            'ExpressionAttributeValues': {':state': {'S': 'AVAILABLE'}}
        }
        response = dynamodb.query(**paginator_kwargs)
        for item in response.get('Items', []):
            acct_id = item.get('accountId', {}).get('S', '')
            if acct_id:
                account_ids.append(acct_id)
    except Exception as e:
        print(f"Error querying AVAILABLE accounts: {e}")
    return account_ids


# Direct CF stack names created by the old SetupOrchestrator (pre-StackSet migration)
_DIRECT_CF_STACKS = [
    'DataZone-Blueprints-{account_id}',  # delete first — depends on IAM outputs
    'DataZone-VPC-{account_id}',
    'DataZone-IAM-{account_id}',
    'DataZone-EventBridge-{account_id}',
    'DataZone-ProjectRole-{account_id}',
]


def cleanup_stacks_batch(account_ids, max_concurrent):
    """Delete direct CF stacks from AVAILABLE accounts in parallel."""
    results = []
    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = {executor.submit(_cleanup_stacks_one, aid): aid for aid in account_ids}
        for future in as_completed(futures):
            aid = futures[future]
            try:
                results.append(future.result())
            except Exception as e:
                print(f"cleanupStacks error for {aid}: {e}")
                results.append({'accountId': aid, 'result': 'FAILED', 'error': str(e)})
    return results


def _cleanup_stacks_one(account_id):
    """Delete the 5 direct CF stacks from one AVAILABLE account, then reset DynamoDB."""
    item = get_latest_record(account_id)
    if not item:
        return {'accountId': account_id, 'result': 'SKIPPED', 'error': 'No DynamoDB record'}

    state = item.get('state', {}).get('S', '')
    if state != 'AVAILABLE':
        return {'accountId': account_id, 'result': 'SKIPPED',
                'error': f'State is {state}, only AVAILABLE accounts are cleaned'}

    stacks_to_delete = [s.format(account_id=account_id) for s in _DIRECT_CF_STACKS]

    print(f"  [{account_id}] Invoking DeprovisionAccount with stacksToDelete={stacks_to_delete}")
    try:
        result = invoke_lambda_sync(
            DEPROVISION_FUNCTION,
            {
                'accountId': account_id,
                'requestId': f'cleanup-{int(time.time())}',
                'domainId': DOMAIN_ID,
                'stacksToDelete': stacks_to_delete,
            }
        )
        if result.get('status') not in ('SUCCESS', 'COMPLETED'):
            raise Exception(f"DeprovisionAccount returned: {result.get('status')} — {result.get('message','')}")
    except Exception as e:
        print(f"  [{account_id}] DeprovisionAccount failed: {e}")
        return {'accountId': account_id, 'result': 'FAILED', 'error': str(e)}

    # Reset DynamoDB record — state stays AVAILABLE, setup fields cleared
    _reset_dynamodb_record(account_id, item)
    print(f"  [{account_id}] Stacks deleted and DynamoDB reset")
    return {'accountId': account_id, 'result': 'CLEANED'}


def _reset_dynamodb_record(account_id, item):
    """Clear setup-related fields from DynamoDB, preserving identity fields.

    Fields removed: completedSteps, resources, deployedStackSets, setupCompleteDate,
    setupDuration, errorMessage, failedStep, reconciliationNote, retryCount.
    State stays AVAILABLE — reconciler will detect missing stacks → NEEDS_SETUP.
    """
    fields_to_remove = [
        'completedSteps', 'resources', 'deployedStackSets',
        'setupCompleteDate', 'setupDuration', 'errorMessage',
        'failedStep', 'reconciliationNote', 'cleanupStartDate',
        'cleanupCompletedDate', 'recycledDate',
    ]
    remove_expr = 'REMOVE ' + ', '.join(fields_to_remove)
    try:
        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': item['accountId'],
                'timestamp': item['timestamp'],
            },
            UpdateExpression=remove_expr + ' SET retryCount = :zero, lastReconciled = :now',
            ExpressionAttributeValues={
                ':zero': {'N': '0'},
                ':now': {'S': datetime.now(timezone.utc).isoformat()},
            }
        )
    except Exception as e:
        print(f"  [{account_id}] Warning: DynamoDB reset failed: {e}")


def update_blueprints_batch(account_ids, max_concurrent):
    """Invoke SetupOrchestrator in updateBlueprints mode for a batch of accounts"""
    results = []
    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = {
            executor.submit(_update_blueprints_one, aid): aid
            for aid in account_ids
        }
        for future in as_completed(futures):
            aid = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"Blueprint update error for {aid}: {e}")
                results.append({'accountId': aid, 'result': 'FAILED', 'error': str(e)})
    return results


def _update_blueprints_one(account_id):
    """Update blueprints on a single account via SetupOrchestrator"""
    try:
        result = invoke_lambda_sync(
            SETUP_FUNCTION,
            {'accountId': account_id, 'mode': 'updateBlueprints'}
        )
        if result.get('status') == 'ERROR':
            raise Exception(result.get('message', 'unknown'))
        print(f"  [{account_id}] Blueprints updated")
        return {'accountId': account_id, 'result': 'UPDATED'}
    except Exception as e:
        print(f"  [{account_id}] Blueprint update failed: {e}")
        return {'accountId': account_id, 'result': 'FAILED', 'error': str(e)}


def recycle_batch(account_ids, max_concurrent, max_retries, force=False):
    """Process multiple accounts with thread pool"""
    results = []
    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = {
            executor.submit(recycle_account, aid, max_retries, force=force): aid
            for aid in account_ids
        }
        for future in as_completed(futures):
            aid = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"Error recycling {aid}: {e}")
                results.append({
                    'accountId': aid,
                    'result': 'FAILED',
                    'error': str(e)
                })
    return results



# ============================================================
# Core recycling logic
# ============================================================

def recycle_account(account_id, max_retries, force=False):
    """Recycle a single account based on its current state and failure reason.

    Routes to the appropriate handler based on state:
    - AVAILABLE: skip (or force re-recycle)
    - CLEANING: deprovision -> setup -> AVAILABLE
    - FAILED: inspect failure reason, fix accordingly
    - ORPHANED: provision StackSet if needed -> setup -> AVAILABLE
    """
    item = get_latest_record(account_id)
    if not item:
        return {
            'accountId': account_id,
            'result': 'SKIPPED',
            'error': 'No DynamoDB record found'
        }

    current_state = item.get('state', {}).get('S', '')
    retry_count = int(item.get('retryCount', {}).get('N', '0'))

    print(f"Recycling {account_id}: state={current_state}, retryCount={retry_count}, force={force}")

    if current_state == 'AVAILABLE':
        if force:
            print(f"  [{account_id}] Force recycling AVAILABLE account")
            update_state_simple(account_id, item, 'CLEANING', 'Force recycle from AVAILABLE')
            item = get_latest_record(account_id)
            if item:
                return handle_cleaning(account_id, item, max_retries)
            return {'accountId': account_id, 'previousState': 'AVAILABLE',
                    'result': 'FAILED', 'error': 'Record lost after state update'}
        return {'accountId': account_id, 'previousState': 'AVAILABLE',
                'result': 'SKIPPED', 'newState': 'AVAILABLE'}

    if current_state == 'ASSIGNED':
        if force:
            print(f"  [{account_id}] Force recycling ASSIGNED account (no real project)")
            update_state_simple(account_id, item, 'CLEANING', 'Force recycle from ASSIGNED')
            item = get_latest_record(account_id)
            if item:
                return handle_cleaning(account_id, item, max_retries)
            return {'accountId': account_id, 'previousState': 'ASSIGNED',
                    'result': 'FAILED', 'error': 'Record lost after state update'}
        return {'accountId': account_id, 'previousState': 'ASSIGNED',
                'result': 'SKIPPED', 'error': 'Cannot recycle ASSIGNED account without force=true'}

    if current_state == 'CLEANING':
        return handle_cleaning(account_id, item, max_retries)
    elif current_state == 'FAILED':
        return handle_failed(account_id, item, max_retries, retry_count, force)
    elif current_state == 'ORPHANED':
        return handle_orphaned(account_id, item, max_retries)
    elif current_state == 'PROVISIONED':
        # PROVISIONED → SETTING_UP → AVAILABLE (no deprovision needed)
        print(f"  [{account_id}] Setting up PROVISIONED account")
        update_state_simple(account_id, item, 'SETTING_UP', 'Promoting PROVISIONED to AVAILABLE')
        try:
            run_setup(account_id)
            return {'accountId': account_id, 'previousState': 'PROVISIONED',
                    'result': 'SETUP_TRIGGERED', 'newState': 'SETTING_UP'}
        except Exception as e:
            mark_failed(account_id, item, str(e), 'setup')
            return {'accountId': account_id, 'previousState': 'PROVISIONED',
                    'result': 'FAILED', 'error': str(e)}
    else:
        return {'accountId': account_id, 'previousState': current_state,
                'result': 'SKIPPED', 'error': f'Cannot recycle from state {current_state}'}


def handle_cleaning(account_id, item, max_retries):
    """Handle CLEANING state: deprovision -> setup -> AVAILABLE"""
    try:
        # Step 1: Deprovision
        print(f"  [{account_id}] Invoking DeprovisionAccount...")
        deprovision_result = invoke_lambda_sync(
            DEPROVISION_FUNCTION,
            {
                'accountId': account_id,
                'requestId': f"recycle-{int(time.time())}",
                'domainId': DOMAIN_ID
            }
        )
        if deprovision_result.get('status') == 'ERROR':
            raise Exception(f"Deprovision failed: {deprovision_result.get('message')}")

        # Step 2: Ensure StackSet is deployed (may be missing on legacy accounts)
        ensure_stackset(account_id)

        # Step 3: Enqueue setup via SQS — SetupOrchestrator marks AVAILABLE when done
        print(f"  [{account_id}] Enqueuing SetupOrchestrator via SQS...")
        update_state_simple(account_id, item, 'SETTING_UP', 'Deprovision complete, setup enqueued')
        run_setup(account_id)

        publish_metric('RecyclingSucceeded', 1,
                       [{'Name': 'AccountId', 'Value': account_id}])
        return {'accountId': account_id, 'previousState': 'CLEANING',
                'result': 'ENQUEUED', 'newState': 'SETTING_UP'}

    except Exception as e:
        error_msg = str(e)
        print(f"  [{account_id}] Recycling failed: {error_msg}")
        if 'TooManyRequestsException' in error_msg or 'Rate Exceeded' in error_msg or 'Throttling' in error_msg:
            print(f"  [{account_id}] Throttle error — leaving in CLEANING, will retry next cycle")
            return {'accountId': account_id, 'previousState': 'CLEANING',
                    'result': 'THROTTLED', 'error': error_msg}
        mark_failed(account_id, item, error_msg, 'deprovision_or_setup')
        publish_metric('RecyclingFailed', 1, [
            {'Name': 'AccountId', 'Value': account_id},
            {'Name': 'FailedStep', 'Value': 'deprovision_or_setup'}
        ])
        return {'accountId': account_id, 'previousState': 'CLEANING',
                'result': 'FAILED', 'error': error_msg}


def handle_failed(account_id, item, max_retries, retry_count, force=False):
    """Handle FAILED state: inspect failure reason and fix accordingly.

    The reconciler sets descriptive failure reasons:
    - 'NEEDS_STACKSET: ...' -> deploy StackSet, then run setup
    - 'NEEDS_SETUP: ...' -> just run setup (SetupOrchestrator handles bad stacks)
    - Other -> full deprovision + setup cycle

    SetupOrchestrator is idempotent: it skips healthy stacks, deletes and
    recreates stacks in bad states, and creates missing stacks.
    """
    error_msg = item.get('errorMessage', {}).get('S', '')
    note = item.get('reconciliationNote', {}).get('S', '')
    failure_reason = note or error_msg

    # Non-recoverable: force does NOT override these
    if is_non_recoverable(error_msg):
        print(f"  [{account_id}] Non-recoverable error, marking DELETING")
        update_state_simple(account_id, item, 'DELETING', f'Non-recoverable: {error_msg}')
        return {'accountId': account_id, 'previousState': 'FAILED',
                'result': 'FAILED', 'newState': 'DELETING',
                'error': f'Non-recoverable: {error_msg}'}

    # Force mode OR recoverable failure: reset retry count so accounts never stay
    # permanently stuck. NEEDS_SETUP / NEEDS_STACKSET are always worth retrying.
    is_recoverable = ('NEEDS_SETUP' in failure_reason or 'NEEDS_STACKSET' in failure_reason)
    if force or is_recoverable:
        if retry_count >= max_retries:
            print(f"  [{account_id}] Resetting retryCount ({retry_count}) — recoverable failure, retrying")
            retry_count = 0

    # Check retry limit (only blocks non-recoverable / unknown failures)
    if retry_count >= max_retries:
        print(f"  [{account_id}] Max retries ({max_retries}) exceeded")
        update_state_simple(account_id, item, 'FAILED', 'Max recycling retries exceeded')
        return {'accountId': account_id, 'previousState': 'FAILED',
                'result': 'FAILED', 'error': 'Max recycling retries exceeded'}
    increment_retry(account_id, item)

    try:
        if 'NEEDS_STACKSET' in failure_reason:
            # Missing DomainAccess role — deploy StackSet first, then setup
            print(f"  [{account_id}] Fixing missing StackSet...")
            ensure_stackset(account_id)
            print(f"  [{account_id}] Enqueuing SetupOrchestrator...")
            update_state_simple(account_id, item, 'SETTING_UP', 'StackSet fixed, setup enqueued')
            run_setup(account_id)

        elif 'NEEDS_SETUP' in failure_reason:
            # Role exists but stacks missing/broken — setup handles it
            print(f"  [{account_id}] Enqueuing SetupOrchestrator (stacks missing/broken)...")
            update_state_simple(account_id, item, 'SETTING_UP', 'Setup enqueued via SQS')
            run_setup(account_id)

        else:
            # Unknown failure — full deprovision + setup cycle
            print(f"  [{account_id}] Full recycle (attempt {retry_count + 1}/{max_retries})...")
            update_state_simple(account_id, item, 'CLEANING', f'Retry attempt {retry_count + 1}')
            item = get_latest_record(account_id)
            if item:
                return handle_cleaning(account_id, item, max_retries)
            return {'accountId': account_id, 'previousState': 'FAILED',
                    'result': 'FAILED', 'error': 'Record lost after state update'}

        publish_metric('RecyclingSucceeded', 1,
                       [{'Name': 'AccountId', 'Value': account_id}])
        return {'accountId': account_id, 'previousState': 'FAILED',
                'result': 'ENQUEUED', 'newState': 'SETTING_UP'}

    except Exception as e:
        error_msg = str(e)
        print(f"  [{account_id}] Fix failed: {error_msg}")
        # Throttling errors are transient infrastructure issues — don't count against the account.
        # Reset retry count so the next reconciler run tries again cleanly.
        if 'TooManyRequestsException' in error_msg or 'Rate Exceeded' in error_msg or 'Throttling' in error_msg:
            print(f"  [{account_id}] Throttle error — resetting retryCount, will retry next cycle")
            dynamodb.update_item(
                TableName=DYNAMODB_TABLE_NAME,
                Key={'accountId': {'S': account_id}, 'timestamp': item['timestamp']},
                UpdateExpression='SET retryCount = :zero, errorMessage = :msg',
                ExpressionAttributeValues={
                    ':zero': {'N': '0'},
                    ':msg': {'S': f'Throttled (will retry): {error_msg}'}
                }
            )
            return {'accountId': account_id, 'previousState': 'FAILED',
                    'result': 'THROTTLED', 'error': error_msg}
        mark_failed(account_id, item, error_msg, 'targeted_fix')
        publish_metric('RecyclingFailed', 1, [
            {'Name': 'AccountId', 'Value': account_id},
            {'Name': 'FailedStep', 'Value': 'targeted_fix'}
        ])
        return {'accountId': account_id, 'previousState': 'FAILED',
                'result': 'FAILED', 'error': error_msg}


def handle_orphaned(account_id, item, max_retries):
    """Handle ORPHANED state: ensure StackSet -> setup -> AVAILABLE.
    SetupOrchestrator is idempotent and handles bad stacks."""
    try:
        # Ensure DomainAccess role exists (deploy StackSet if needed)
        ensure_stackset(account_id)

        # Run SetupOrchestrator (idempotent — skips healthy stacks, fixes bad ones)
        print(f"  [{account_id}] Running SetupOrchestrator...")
        run_setup(account_id)

        transition_to_available(account_id, item)
        publish_metric('RecyclingSucceeded', 1,
                       [{'Name': 'AccountId', 'Value': account_id}])
        return {'accountId': account_id, 'previousState': 'ORPHANED',
                'result': 'RECYCLED', 'newState': 'AVAILABLE'}

    except Exception as e:
        error_msg = str(e)
        print(f"  [{account_id}] Orphan recycling failed: {error_msg}")
        mark_failed(account_id, item, error_msg, 'orphan_setup')
        publish_metric('RecyclingFailed', 1, [
            {'Name': 'AccountId', 'Value': account_id},
            {'Name': 'FailedStep', 'Value': 'orphan_setup'}
        ])
        return {'accountId': account_id, 'previousState': 'ORPHANED',
                'result': 'FAILED', 'error': error_msg}



# ============================================================
# StackSet fix + Setup helpers
# ============================================================

def check_domain_access_role(account_id):
    """Check if DomainAccess role is assumable. Retries on throttling."""
    role_arn = (
        f"arn:aws:iam::{account_id}"
        f":role/SMUS-AccountPoolFactory-DomainAccess"
    )
    try:
        retry_with_backoff(lambda: sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName='recycler-check',
            ExternalId=DOMAIN_ID,
            DurationSeconds=900
        ))
        return True
    except ClientError:
        return False


def ensure_stackset(account_id):
    """Ensure DomainAccess StackSet is deployed to the account.
    If the role is already assumable, this is a no-op.
    """
    if check_domain_access_role(account_id):
        print(f"  [{account_id}] DomainAccess role OK")
        return

    print(f"  [{account_id}] DomainAccess role missing, deploying StackSet...")
    if not PROVISION_FUNCTION_ARN:
        raise Exception('PROVISION_ACCOUNT_FUNCTION_ARN not set, cannot fix StackSet')

    # Read poolName from DynamoDB record so ProvisionAccount uses the right pool config
    item = get_latest_record(account_id)
    pool_name = item.get('poolName', {}).get('S', 'default') if item else 'default'

    result = invoke_lambda_sync(
        PROVISION_FUNCTION_ARN,
        {
            'action': 'fixStackSet',
            'accountId': account_id,
            'domainId': DOMAIN_ID,
            'domainAccountId': DOMAIN_ACCOUNT_ID,
            'poolName': pool_name,
        }
    )
    status = result.get('status')
    if status != 'SUCCESS':
        raise Exception(f"StackSet fix failed: {result.get('message', 'unknown')}")

    print(f"  [{account_id}] StackSet deployed, waiting for IAM propagation...")
    time.sleep(15)

    if not check_domain_access_role(account_id):
        time.sleep(15)
        if not check_domain_access_role(account_id):
            raise Exception('DomainAccess role still not assumable after StackSet deployment')

    print(f"  [{account_id}] DomainAccess role confirmed")


def ensure_stackset_batch(account_ids):
    """Deploy DomainAccess StackSet to multiple accounts in a single operation.

    Uses fixStackSetBatch action in ProvisionAccount — one create_stack_instances
    call for all accounts, avoiding OperationInProgressException from concurrent calls.

    Returns (succeeded: list, failed: dict[account_id -> error])
    """
    if not PROVISION_FUNCTION_ARN:
        raise Exception('PROVISION_ACCOUNT_FUNCTION_ARN not set')

    print(f"  Batch StackSet fix for {len(account_ids)} accounts...")
    result = invoke_lambda_sync(
        PROVISION_FUNCTION_ARN,
        {
            'action': 'fixStackSetBatch',
            'accountIds': account_ids,
            'domainId': DOMAIN_ID,
            'domainAccountId': DOMAIN_ACCOUNT_ID
        }
    )

    if result.get('status') != 'SUCCESS':
        raise Exception(f"Batch StackSet fix failed: {result.get('message', 'unknown')}")

    succeeded = result.get('accountIds', [])
    failed_execution = result.get('failedExecutionRole', [])
    print(f"  Batch StackSet: {len(succeeded)} succeeded, {len(failed_execution)} failed execution role")

    # Wait for IAM propagation across all accounts
    if succeeded:
        print(f"  Waiting 30s for IAM propagation across {len(succeeded)} accounts...")
        time.sleep(30)

    # Verify each account — collect failures
    failed = {a: 'StackSetExecution role deployment failed' for a in failed_execution}
    for account_id in succeeded:
        if not check_domain_access_role(account_id):
            time.sleep(10)
            if not check_domain_access_role(account_id):
                failed[account_id] = 'DomainAccess role not assumable after StackSet deployment'
            else:
                print(f"  [{account_id}] DomainAccess role confirmed (delayed)")
        else:
            print(f"  [{account_id}] DomainAccess role confirmed")

    ok = [a for a in succeeded if a not in failed]
    return ok, failed


def run_setup(account_id):
    """Enqueue account for SetupOrchestrator via SQS.

    Fire-and-forget: SQS delivers the message to SetupOrchestrator at the
    configured concurrency level. SetupOrchestrator marks the account AVAILABLE
    when done — no need to wait here.

    Falls back to direct async Lambda invoke if SETUP_QUEUE_URL is not set.
    """
    payload = {
        'accountId': account_id,
        'requestId': f"recycle-setup-{int(time.time())}",
        'mode': 'setup'
    }
    if SETUP_QUEUE_URL:
        sqs.send_message(
            QueueUrl=SETUP_QUEUE_URL,
            MessageBody=json.dumps(payload),
            MessageGroupId=account_id if SETUP_QUEUE_URL.endswith('.fifo') else None
        ) if SETUP_QUEUE_URL.endswith('.fifo') else sqs.send_message(
            QueueUrl=SETUP_QUEUE_URL,
            MessageBody=json.dumps(payload)
        )
        print(f"  [{account_id}] Enqueued setup job in SQS")
    else:
        # Fallback: async Lambda invoke
        lambda_client.invoke(
            FunctionName=SETUP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
        print(f"  [{account_id}] Invoked SetupOrchestrator async (no queue configured)")



# ============================================================
# Lambda invocation helper
# ============================================================

def invoke_lambda_sync(function_name, payload):
    """Invoke a Lambda function synchronously and return parsed response.

    Uses lambda_client_sync with extended read timeout (900s) to handle
    long-running Lambdas like SetupOrchestrator and DeprovisionAccount.
    Retries on TooManyRequestsException with generous backoff — under high
    concurrency (10 workers) all hitting ProvisionAccount simultaneously,
    we need more retries and longer delays.
    """
    def _invoke():
        return lambda_client_sync.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )

    response = retry_with_backoff(_invoke, max_retries=6, base_delay=2.0, max_delay=30.0)
    result = json.loads(response['Payload'].read())

    # Check for Lambda invocation error (unhandled exception in target)
    if 'FunctionError' in response:
        error_msg = result.get('errorMessage', str(result))
        raise Exception(f"{function_name} invocation error: {error_msg}")

    # Check for application-level error (statusCode 4xx/5xx)
    status_code = result.get('statusCode', 200)
    if isinstance(status_code, int) and status_code >= 400:
        body = result.get('body', 'Unknown error')
        raise Exception(f"{function_name} returned {status_code}: {body}")

    return result


# ============================================================
# DynamoDB helpers
# ============================================================

def get_latest_record(account_id):
    """Get the latest DynamoDB record for an account"""
    try:
        response = dynamodb.query(
            TableName=DYNAMODB_TABLE_NAME,
            KeyConditionExpression='accountId = :aid',
            ExpressionAttributeValues={':aid': {'S': account_id}},
            ScanIndexForward=False,
            Limit=1
        )
        items = response.get('Items', [])
        return items[0] if items else None
    except Exception as e:
        print(f"Error querying DynamoDB for {account_id}: {e}")
        return None


def transition_to_available(account_id, item):
    """Transition account to AVAILABLE, clearing project attributes"""
    now = datetime.now(timezone.utc).isoformat()
    try:
        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp']
            },
            UpdateExpression=(
                'SET #state = :available, recycledDate = :now, '
                'retryCount = :zero '
                'REMOVE projectStackName, assignedDate, errorMessage, '
                'failedStep, cleanupStartDate, projectId, '
                'reconciliationNote'
            ),
            ExpressionAttributeNames={'#state': 'state'},
            ExpressionAttributeValues={
                ':available': {'S': 'AVAILABLE'},
                ':now': {'S': now},
                ':zero': {'N': '0'}
            }
        )
        print(f"  [{account_id}] Transitioned to AVAILABLE")
    except Exception as e:
        print(f"Error transitioning {account_id} to AVAILABLE: {e}")


def mark_failed(account_id, item, error_msg, failed_step):
    """Mark account as FAILED with error details"""
    now = datetime.now(timezone.utc).isoformat()
    try:
        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp']
            },
            UpdateExpression=(
                'SET #state = :failed, errorMessage = :error, '
                'failedStep = :step, lastReconciled = :now'
            ),
            ExpressionAttributeNames={'#state': 'state'},
            ExpressionAttributeValues={
                ':failed': {'S': 'FAILED'},
                ':error': {'S': error_msg[:500]},
                ':step': {'S': failed_step},
                ':now': {'S': now}
            }
        )
    except Exception as e:
        print(f"Error marking {account_id} as FAILED: {e}")


def update_state_simple(account_id, item, new_state, note):
    """Simple state update without condition check"""
    now = datetime.now(timezone.utc).isoformat()
    try:
        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp']
            },
            UpdateExpression=(
                'SET #state = :state, reconciliationNote = :note, '
                'lastReconciled = :now'
            ),
            ExpressionAttributeNames={'#state': 'state'},
            ExpressionAttributeValues={
                ':state': {'S': new_state},
                ':note': {'S': note},
                ':now': {'S': now}
            }
        )
    except Exception as e:
        print(f"Error updating {account_id} to {new_state}: {e}")


def increment_retry(account_id, item):
    """Increment retry count"""
    try:
        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp']
            },
            UpdateExpression='ADD retryCount :inc',
            ExpressionAttributeValues={':inc': {'N': '1'}}
        )
    except Exception as e:
        print(f"Error incrementing retry for {account_id}: {e}")


def is_non_recoverable(error_msg):
    """Check if error is non-recoverable"""
    lower = error_msg.lower()
    return any(pattern in lower for pattern in NON_RECOVERABLE_PATTERNS)



# ============================================================
# Metrics & notifications
# ============================================================

def publish_metric(metric_name, value, dimensions=None):
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
            Namespace='AccountPoolFactory',
            MetricData=[metric_data]
        )
    except Exception as e:
        print(f"Warning: Failed to publish metric {metric_name}: {e}")


def send_failure_notification(account_id, operation, error_msg):
    """Send SNS notification for failure"""
    if not SNS_TOPIC_ARN:
        return
    try:
        message = {
            'alertType': 'RECYCLING_FAILED',
            'severity': 'HIGH',
            'accountId': account_id,
            'operation': operation,
            'errorMessage': error_msg,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f'Account Recycling Failed: {account_id}',
            Message=json.dumps(message, indent=2)
        )
    except Exception as e:
        print(f"Warning: Failed to send notification: {e}")

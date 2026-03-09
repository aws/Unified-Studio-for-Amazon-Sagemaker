"""
AccountReconciler Lambda Function

Runs in Domain Account (994753223772)
Reconciles AWS Organizations accounts with DynamoDB pool state.

Responsibilities (DETECT ONLY — no fixing):
1. List accounts in target OU from AWS Organizations (via cross-account role)
2. Identify pool accounts by tag (ManagedBy=AccountPoolFactory) or name prefix
3. Backfill tags on legacy untagged accounts
4. Create ORPHANED records for untracked accounts
5. Validate AVAILABLE accounts (DomainAccess role + setup stacks)
6. Mark unhealthy accounts as FAILED with descriptive reason
7. Detect stale DynamoDB records with no matching org account
8. Queue unhealthy accounts for AccountRecycler (async)
9. Optionally trigger Pool Manager replenishment

Cross-Account Access:
- Assumes SMUS-AccountPoolFactory-AccountCreation role in Org Admin (495869084367)
  to call Organizations APIs (ListAccountsForParent, ListTagsForResource, TagResource)
- Assumes SMUS-AccountPoolFactory-DomainAccess role in project accounts
  to validate role availability
"""

import json
import os
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
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
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'AccountPoolFactory-AccountState')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')
DOMAIN_ID = os.environ.get('DOMAIN_ID', '')
DOMAIN_ACCOUNT_ID = os.environ.get('DOMAIN_ACCOUNT_ID', '')
ORG_ADMIN_ACCOUNT_ID = os.environ.get('ORG_ADMIN_ACCOUNT_ID', '')
ACCOUNT_RECYCLER_FUNCTION_NAME = os.environ.get('ACCOUNT_RECYCLER_FUNCTION_NAME', '')
POOL_MANAGER_FUNCTION_NAME = os.environ.get('POOL_MANAGER_FUNCTION_NAME', '')
REGION = os.environ.get('AWS_REGION', 'us-east-2')

# Rate limit delay between list_tags_for_resource calls (seconds)
TAG_API_DELAY = 0.2

# Concurrency for validation pass
MAX_VALIDATION_WORKERS = 5

# Expected setup stacks — loaded from SSM on first use
_expected_setup_stacks = None



# ============================================================
# Retry / backoff helpers
# ============================================================

def retry_with_backoff(fn, max_retries=3, base_delay=1.0, max_delay=10.0):
    """Call fn() with exponential backoff on throttling errors.
    Returns the result of fn() on success, raises on non-throttle errors."""
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
# Config loading
# ============================================================

def get_expected_setup_stacks():
    """Load expected stack patterns from SSM Parameter Store.
    Cached after first call (Lambda cold start)."""
    global _expected_setup_stacks
    if _expected_setup_stacks is not None:
        return _expected_setup_stacks
    try:
        resp = ssm.get_parameter(
            Name='/AccountPoolFactory/SetupOrchestrator/ExpectedStackPatterns'
        )
        raw = resp['Parameter']['Value']
        _expected_setup_stacks = [p.strip() for p in raw.split(',') if p.strip()]
        print(f"Loaded {len(_expected_setup_stacks)} expected stack patterns from SSM")
    except Exception as e:
        print(f"Warning: Failed to load ExpectedStackPatterns from SSM: {e}")
        _expected_setup_stacks = []
    return _expected_setup_stacks


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

        config.setdefault('PoolName', 'AccountPoolFactory')
        config.setdefault('NamePrefix', 'DataZone-Pool')
        config.setdefault('TargetOUId', '')
        config.setdefault('MinimumPoolSize', '5')
        config.setdefault('MaxRecycleRetries', '3')

        # Load per-pool OU IDs from org SSM (written by org deploy script)
        # These are in the org account — read via AccountCreation role
        pools = {}
        try:
            org_client = get_org_client()
            # Use the org SSM via assumed role
            import boto3 as _boto3
            assumed = sts.assume_role(
                RoleArn=f"arn:aws:iam::{ORG_ADMIN_ACCOUNT_ID}:role/SMUS-AccountPoolFactory-AccountCreation",
                RoleSessionName='ReconcilerSSM',
                ExternalId=f'AccountPoolFactory-{DOMAIN_ACCOUNT_ID}'
            )
            creds = assumed['Credentials']
            org_ssm = _boto3.client('ssm', region_name=REGION,
                aws_access_key_id=creds['AccessKeyId'],
                aws_secret_access_key=creds['SecretAccessKey'],
                aws_session_token=creds['SessionToken'])
            resp = org_ssm.get_parameters_by_path(
                Path='/AccountPoolFactory/Pools/',
                Recursive=True,
                WithDecryption=False
            )
            for param in resp['Parameters']:
                parts = param['Name'].split('/')
                if len(parts) >= 5:
                    pool_name = parts[3]
                    key = parts[4]
                    pools.setdefault(pool_name, {})[key] = param['Value']
        except Exception as e:
            print(f'Warning: could not load pool OU IDs from org SSM: {e}')

        config['pools'] = pools
        print(f"Loaded {len(config)} SSM parameters, {len(pools)} pools: {list(pools.keys())}")
        return config
    except Exception as e:
        print(f"Warning: Failed to load SSM parameters: {e}")
        return {
            'PoolName': 'AccountPoolFactory',
            'NamePrefix': 'DataZone-Pool',
            'TargetOUId': '',
            'MinimumPoolSize': '5',
            'MaxRecycleRetries': '3',
            'pools': {},
        }


def get_org_client():
    """Assume AccountCreation role in Org Admin and return Organizations client"""
    external_id = f"AccountPoolFactory-{DOMAIN_ACCOUNT_ID}"
    role_arn = (
        f"arn:aws:iam::{ORG_ADMIN_ACCOUNT_ID}"
        f":role/SMUS-AccountPoolFactory-AccountCreation"
    )
    assumed = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName='AccountReconciler',
        ExternalId=external_id
    )
    creds = assumed['Credentials']
    return boto3.client(
        'organizations',
        aws_access_key_id=creds['AccessKeyId'],
        aws_secret_access_key=creds['SecretAccessKey'],
        aws_session_token=creds['SessionToken']
    )



# ============================================================
# Lambda handler
# ============================================================

def lambda_handler(event, context):
    """Main handler for AccountReconciler.

    Detect-only: scans accounts, validates health, marks unhealthy ones,
    queues them for the recycler. Does NOT attempt any fixes itself.
    """
    print(f"Received event: {json.dumps(event, indent=2)}")

    source = event.get('source', 'manual')
    dry_run = event.get('dryRun', False)
    account_ids_filter = event.get('accountIds', [])
    auto_recycle = event.get('autoRecycle', False)
    auto_replenish = event.get('autoReplenish', False)

    config = load_config()
    pool_name = config['PoolName']
    name_prefix = config['NamePrefix']
    target_ou_id = config.get('TargetOUId', '')

    # Build list of (pool_name, ou_id) pairs to scan
    pools = config.get('pools', {})
    if pools:
        pool_ou_pairs = [(pn, pc.get('OUId', '')) for pn, pc in pools.items() if pc.get('OUId')]
        if not pool_ou_pairs:
            pool_ou_pairs = [(pool_name, target_ou_id)]
    else:
        pool_ou_pairs = [(pool_name, target_ou_id)]

    try:
        org_client = get_org_client()
    except Exception as e:
        print(f"Failed to assume Org Admin role: {e}")
        return {'status': 'ERROR', 'message': str(e)}

    # Scan all pool OUs and merge results
    all_org_accounts = []
    all_pool_accounts = []
    seen_ids = set()

    for scan_pool_name, scan_ou_id in pool_ou_pairs:
        ou_accounts = list_org_accounts(org_client, scan_ou_id)
        for a in ou_accounts:
            if a['Id'] not in seen_ids:
                all_org_accounts.append(a)
                seen_ids.add(a['Id'])

        pool_accts = identify_pool_accounts(
            org_client, ou_accounts, scan_pool_name, name_prefix,
            account_ids_filter, dry_run
        )
        all_pool_accounts.extend(pool_accts)

    print(f"Found {len(all_org_accounts)} accounts across {len(pool_ou_pairs)} OUs")
    print(f"Identified {len(all_pool_accounts)} pool accounts")

    # Step 3: Reconcile with DynamoDB (includes parallel validation)
    summary = reconcile_with_dynamodb(all_pool_accounts, all_org_accounts, dry_run)

    # Step 4: Detect stale DynamoDB records
    stale_count = detect_stale_records(
        {a['Id'] for a in all_org_accounts}, dry_run
    )
    summary['staleUpdated'] = stale_count

    # Step 5: Publish metrics
    publish_reconciliation_metrics(summary)

    # Step 6: Auto-recycle if requested — only unhealthy accounts
    recycling_triggered = False
    if auto_recycle and not dry_run:
        recyclable = summary.get('recyclableAccountIds', [])
        if recyclable:
            recycling_triggered = trigger_recycler(recyclable)

    # Step 7: Auto-replenish if requested
    replenishment_triggered = False
    if auto_replenish and not dry_run:
        replenishment_triggered = check_and_replenish(config)

    # Step 8: Check if blueprint template version needs updating across the fleet.
    # Compares one sample AVAILABLE account's DataZone-Blueprints-* stack TemplateVersion
    # output against the current version. If outdated, triggers recycler updateBlueprints.
    blueprints_update_triggered = False
    if not dry_run and source == 'schedule':
        blueprints_update_triggered = check_and_trigger_blueprint_update()

    result = {
        'status': 'SUCCESS',
        'dryRun': dry_run,
        'summary': {
            'totalOrgAccounts': len(all_org_accounts),
            'totalPoolAccounts': len(all_pool_accounts),
            'orphanedCreated': summary.get('orphanedCreated', 0),
            'staleUpdated': stale_count,
            'unchanged': summary.get('unchanged', 0),
            'tagsBackfilled': summary.get('tagsBackfilled', 0),
            'failedValidation': summary.get('failedValidation', 0),
        },
        'details': summary.get('details', []),
        'recyclingTriggered': recycling_triggered,
        'replenishmentTriggered': replenishment_triggered,
        'blueprintsUpdateTriggered': blueprints_update_triggered
    }
    print(f"Reconciliation complete: {json.dumps(result['summary'])}")
    return result



# ============================================================
# Org account listing & identification
# ============================================================

def list_org_accounts(org_client, target_ou_id):
    """List accounts from Organizations, scoped to OU if configured"""
    accounts = []
    try:
        if target_ou_id and target_ou_id != 'root':
            paginator = org_client.get_paginator('list_accounts_for_parent')
            for page in paginator.paginate(ParentId=target_ou_id):
                accounts.extend(page['Accounts'])
        else:
            paginator = org_client.get_paginator('list_accounts')
            for page in paginator.paginate():
                accounts.extend(page['Accounts'])
    except Exception as e:
        print(f"Error listing org accounts: {e}")
    return accounts


def identify_pool_accounts(org_client, org_accounts, pool_name,
                           name_prefix, account_ids_filter, dry_run):
    """Identify pool accounts by tag or name prefix, backfill tags"""
    pool_accounts = []

    for account in org_accounts:
        acct_id = account['Id']
        acct_name = account.get('Name', '')
        acct_status = account.get('Status', 'ACTIVE')

        # If filtering by specific account IDs, skip non-matching
        if account_ids_filter and acct_id not in account_ids_filter:
            continue

        # Skip suspended/closed accounts from pool identification
        if acct_status != 'ACTIVE':
            continue

        # Check name prefix first (cheap filter)
        name_matches = acct_name.startswith(name_prefix) or acct_name.startswith('smus-')
        if not name_matches and not account_ids_filter:
            continue

        # Check tags (with backoff for throttling)
        time.sleep(TAG_API_DELAY)
        tags = get_account_tags(org_client, acct_id)
        managed_by = tags.get('ManagedBy', '')
        tag_pool_name = tags.get('PoolName', '')

        if managed_by == 'AccountPoolFactory':
            if tag_pool_name and tag_pool_name != pool_name:
                continue
            pool_accounts.append({
                'accountId': acct_id,
                'accountName': acct_name,
                'status': acct_status,
                'identifiedBy': 'tag',
                'poolName': tag_pool_name or pool_name,
            })
        elif name_matches:
            pool_accounts.append({
                'accountId': acct_id,
                'accountName': acct_name,
                'status': acct_status,
                'identifiedBy': 'namePrefix',
                'poolName': pool_name,
            })
            if not dry_run:
                try:
                    retry_with_backoff(lambda: org_client.tag_resource(
                        ResourceId=acct_id,
                        Tags=[
                            {'Key': 'ManagedBy', 'Value': 'AccountPoolFactory'},
                            {'Key': 'PoolName', 'Value': pool_name}
                        ]
                    ))
                    print(f"Backfilled tags on {acct_id} ({acct_name})")
                except Exception as e:
                    print(f"Warning: Failed to backfill tags on {acct_id}: {e}")

    return pool_accounts


def get_account_tags(org_client, account_id):
    """Get tags for an account, return as dict. Retries on throttling."""
    try:
        response = retry_with_backoff(
            lambda: org_client.list_tags_for_resource(ResourceId=account_id)
        )
        return {t['Key']: t['Value'] for t in response.get('Tags', [])}
    except Exception as e:
        print(f"Warning: Failed to get tags for {account_id}: {e}")
        return {}



# ============================================================
# Validation (detect-only, no fixing)
# ============================================================

def validate_domain_access_role(account_id):
    """Check if DomainAccess role is assumable. Returns (ok, credentials|None).
    Retries on throttling."""
    role_arn = (
        f"arn:aws:iam::{account_id}"
        f":role/SMUS-AccountPoolFactory-DomainAccess"
    )
    try:
        response = retry_with_backoff(lambda: sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName='reconciliation-check',
            ExternalId=DOMAIN_ID,
            DurationSeconds=900
        ))
        return True, response['Credentials']
    except ClientError:
        return False, None


def validate_setup_stacks(account_id, creds, item=None):
    """Check all expected setup stacks exist and are healthy.

    Prefers per-account deployedStackSets from DynamoDB record (item).
    Falls back to global ExpectedStackPatterns SSM if not available.
    Returns (ok, missing_list, unhealthy_list).
    """
    try:
        cf_client = boto3.client(
            'cloudformation',
            region_name=REGION,
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken']
        )

        # Build list of stack names to check
        stack_names = []

        # Prefer per-account deployedStackSets (StackSet-deployed stacks)
        if item:
            deployed = item.get('deployedStackSets', {}).get('L', [])
            if deployed:
                # These are StackSet names — the actual CF stack in the account
                # is named StackSet-{StackSetName}-{uuid}, so we check by prefix
                for entry in deployed:
                    ss_name = entry.get('S', '')
                    if ss_name:
                        stack_names.append(('stackset_prefix', ss_name))

        # Also check SetupOrchestrator-deployed stacks via global patterns
        for pattern in get_expected_setup_stacks():
            stack_names.append(('pattern', pattern.format(account_id=account_id)))

        if not stack_names:
            return True, [], []  # Nothing to validate

        missing = []
        unhealthy = []
        healthy_statuses = {'CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE'}

        for check_type, name in stack_names:
            if check_type == 'stackset_prefix':
                # Find stacks with this StackSet name prefix
                try:
                    resp = cf_client.list_stacks(
                        StackStatusFilter=list(healthy_statuses) + ['CREATE_IN_PROGRESS']
                    )
                    prefix = f'StackSet-{name}-'
                    found = [s for s in resp.get('StackSummaries', [])
                             if s['StackName'].startswith(prefix)]
                    if not found:
                        missing.append(f'StackSet:{name}')
                    elif not any(s['StackStatus'] in healthy_statuses for s in found):
                        unhealthy.append(f'StackSet:{name}={found[0]["StackStatus"]}')
                except Exception as e:
                    missing.append(f'StackSet:{name} (error: {e})')
            else:
                try:
                    resp = retry_with_backoff(
                        lambda sn=name: cf_client.describe_stacks(StackName=sn)
                    )
                    status = resp['Stacks'][0]['StackStatus']
                    if status not in healthy_statuses:
                        unhealthy.append(f'{name}={status}')
                except ClientError as e:
                    if 'does not exist' in str(e):
                        missing.append(name)
                    else:
                        missing.append(f'{name} (error: {e})')

        return (not missing and not unhealthy), missing, unhealthy

    except Exception as e:
        return False, [f'Stack validation error: {e}'], []


def validate_available_account(account_id, item=None):
    """Full health check for AVAILABLE accounts (detect-only).

    Validates:
    1. DomainAccess role is assumable
    2. All expected setup stacks exist and are healthy

    Returns (ok: bool, failure_reason: str)
    Does NOT attempt any fixes — just reports what's wrong.
    """
    # Check 1: DomainAccess role
    role_ok, creds = validate_domain_access_role(account_id)
    if not role_ok:
        return False, 'NEEDS_STACKSET: DomainAccess role not assumable'

    # Check 2: All expected stacks exist
    stacks_ok, missing, unhealthy = validate_setup_stacks(account_id, creds, item=item)
    if not stacks_ok:
        reasons = []
        if missing:
            reasons.append(f"Missing: {', '.join(missing)}")
        if unhealthy:
            reasons.append(f"Unhealthy: {', '.join(unhealthy)}")
        return False, f"NEEDS_SETUP: {'; '.join(reasons)}"

    return True, ''



# ============================================================
# DynamoDB reconciliation (with parallel validation)
# ============================================================

def reconcile_with_dynamodb(pool_accounts, org_accounts, dry_run):
    """Reconcile pool accounts with DynamoDB records.

    Accounts that need validation (AVAILABLE state) are checked in parallel
    using a thread pool for speed.
    """
    summary = {
        'orphanedCreated': 0,
        'unchanged': 0,
        'tagsBackfilled': 0,
        'failedValidation': 0,
        'details': [],
        'recyclableAccountIds': []
    }

    # First pass: classify accounts by DynamoDB state
    needs_validation = []  # (acct, item) tuples for AVAILABLE accounts
    for acct in pool_accounts:
        acct_id = acct['accountId']
        item = get_latest_record(acct_id)

        if not item:
            # No DynamoDB record — create ORPHANED
            # Read PoolName tag from org account to assign correct pool
            pool_from_tag = ''
            try:
                tags = get_account_tags(org_client, acct_id)
                pool_from_tag = tags.get('PoolName', '')
            except Exception:
                pass
            # Fall back to the pool name from the OU scan context
            pool_for_record = pool_from_tag or acct.get('poolName', '')

            summary['orphanedCreated'] += 1
            summary['recyclableAccountIds'].append(acct_id)
            summary['details'].append({
                'accountId': acct_id, 'action': 'CREATED_ORPHANED',
                'newState': 'ORPHANED', 'poolName': pool_for_record
            })
            if not dry_run:
                create_orphaned_record(acct_id, acct.get('accountName', ''), pool_for_record)
        else:
            current_state = item.get('state', {}).get('S', '')

            if current_state == 'AVAILABLE':
                needs_validation.append((acct, item))

            elif current_state == 'ASSIGNED':
                has_stack = item.get('projectStackName', {}).get('S', '')
                if not has_stack:
                    summary['details'].append({
                        'accountId': acct_id, 'action': 'UPDATED_STATE',
                        'note': 'ASSIGNED but missing projectStackName'
                    })
                    if not dry_run:
                        add_reconciliation_note(acct_id, item, 'ASSIGNED but missing projectStackName')
                else:
                    summary['unchanged'] += 1
                    summary['details'].append({'accountId': acct_id, 'action': 'UNCHANGED'})

            elif current_state in ('FAILED', 'ORPHANED', 'CLEANING'):
                summary['unchanged'] += 1
                summary['recyclableAccountIds'].append(acct_id)
                summary['details'].append({
                    'accountId': acct_id, 'action': 'UNCHANGED',
                    'note': f'Already in {current_state} state'
                })

            else:
                summary['unchanged'] += 1
                summary['details'].append({'accountId': acct_id, 'action': 'UNCHANGED'})

        if acct.get('identifiedBy') == 'namePrefix':
            summary['tagsBackfilled'] += 1

    # Second pass: validate AVAILABLE accounts in parallel
    if needs_validation:
        print(f"Validating {len(needs_validation)} AVAILABLE accounts (workers={MAX_VALIDATION_WORKERS})...")
        with ThreadPoolExecutor(max_workers=MAX_VALIDATION_WORKERS) as executor:
            future_to_acct = {
                executor.submit(_validate_one, acct, item, dry_run): acct
                for acct, item in needs_validation
            }
            for future in as_completed(future_to_acct):
                acct = future_to_acct[future]
                acct_id = acct['accountId']
                try:
                    detail, is_healthy = future.result()
                    summary['details'].append(detail)
                    if is_healthy:
                        summary['unchanged'] += 1
                    else:
                        summary['failedValidation'] += 1
                        summary['recyclableAccountIds'].append(acct_id)
                except Exception as e:
                    print(f"Validation error for {acct_id}: {e}")
                    summary['unchanged'] += 1
                    summary['details'].append({
                        'accountId': acct_id, 'action': 'VALIDATION_ERROR',
                        'note': str(e)
                    })

    return summary


def _validate_one(acct, item, dry_run):
    """Validate a single AVAILABLE account. Returns (detail_dict, is_healthy)."""
    acct_id = acct['accountId']
    ok, failure_reason = validate_available_account(acct_id, item=item)
    if ok:
        return {'accountId': acct_id, 'action': 'UNCHANGED'}, True
    else:
        print(f"  [{acct_id}] FAILED validation: {failure_reason}")
        detail = {
            'accountId': acct_id,
            'action': 'FAILED_VALIDATION',
            'previousState': 'AVAILABLE',
            'newState': 'FAILED',
            'note': failure_reason
        }
        if not dry_run:
            update_state(acct_id, item, 'AVAILABLE', 'FAILED', failure_reason)
        return detail, False



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


def create_orphaned_record(account_id, account_name, pool_name=''):
    """Create a new ORPHANED record in DynamoDB"""
    now = datetime.now(timezone.utc).isoformat()
    timestamp = int(time.time())
    item = {
        'accountId': {'S': account_id},
        'timestamp': {'N': str(timestamp)},
        'state': {'S': 'ORPHANED'},
        'accountName': {'S': account_name},
        'createdDate': {'S': now},
        'reconciliationNote': {'S': 'Discovered by AccountReconciler'},
        'lastReconciled': {'S': now},
        'retryCount': {'N': '0'}
    }
    if pool_name:
        item['poolName'] = {'S': pool_name}
    try:
        dynamodb.put_item(TableName=DYNAMODB_TABLE_NAME, Item=item)
        print(f"Created ORPHANED record for {account_id} (pool={pool_name or 'unknown'})")
    except Exception as e:
        print(f"Error creating ORPHANED record for {account_id}: {e}")


def update_state(account_id, item, expected_state, new_state, note):
    """Update account state with conditional write"""
    now = datetime.now(timezone.utc).isoformat()
    try:
        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp']
            },
            UpdateExpression=(
                'SET #state = :new_state, '
                'reconciliationNote = :note, '
                'lastReconciled = :now'
            ),
            ConditionExpression='#state = :expected_state',
            ExpressionAttributeNames={'#state': 'state'},
            ExpressionAttributeValues={
                ':new_state': {'S': new_state},
                ':expected_state': {'S': expected_state},
                ':note': {'S': note},
                ':now': {'S': now}
            }
        )
        print(f"Updated {account_id}: {expected_state} -> {new_state} | reason: {note}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            print(f"Concurrent update on {account_id}, skipping")
        else:
            print(f"Error updating {account_id}: {e}")


def add_reconciliation_note(account_id, item, note):
    """Add a reconciliation note without changing state"""
    now = datetime.now(timezone.utc).isoformat()
    try:
        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'accountId': {'S': account_id},
                'timestamp': item['timestamp']
            },
            UpdateExpression=(
                'SET reconciliationNote = :note, lastReconciled = :now'
            ),
            ExpressionAttributeValues={
                ':note': {'S': note},
                ':now': {'S': now}
            }
        )
    except Exception as e:
        print(f"Error adding note to {account_id}: {e}")



# ============================================================
# Stale record detection, metrics, recycler trigger, replenish
# ============================================================

def detect_stale_records(org_account_ids, dry_run):
    """Find DynamoDB records with no matching org account and mark SUSPENDED"""
    stale_count = 0
    try:
        for state in ['AVAILABLE', 'ASSIGNED', 'SETTING_UP']:
            response = dynamodb.query(
                TableName=DYNAMODB_TABLE_NAME,
                IndexName='StateIndex',
                KeyConditionExpression='#state = :state',
                ExpressionAttributeNames={'#state': 'state'},
                ExpressionAttributeValues={':state': {'S': state}}
            )
            for item in response.get('Items', []):
                acct_id = item.get('accountId', {}).get('S', '')
                if acct_id and acct_id not in org_account_ids:
                    stale_count += 1
                    print(f"Stale record: {acct_id} in state {state} not found in org")
                    if not dry_run:
                        update_state(acct_id, item, state, 'SUSPENDED',
                                     'Account not found in AWS Organizations')
    except Exception as e:
        print(f"Error detecting stale records: {e}")
    return stale_count


def publish_reconciliation_metrics(summary):
    """Publish CloudWatch metrics for reconciliation"""
    try:
        metrics = [
            {
                'MetricName': 'ReconciliationCompleted',
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': datetime.now(timezone.utc),
                'Dimensions': [
                    {'Name': 'OrphanedCount',
                     'Value': str(summary.get('orphanedCreated', 0))},
                    {'Name': 'StaleCount',
                     'Value': str(summary.get('staleUpdated', 0))},
                    {'Name': 'UnchangedCount',
                     'Value': str(summary.get('unchanged', 0))}
                ]
            }
        ]
        cloudwatch.put_metric_data(
            Namespace='AccountPoolFactory',
            MetricData=metrics
        )
    except Exception as e:
        print(f"Warning: Failed to publish metrics: {e}")


def trigger_recycler(account_ids):
    """Invoke AccountRecycler asynchronously for unhealthy accounts"""
    if not ACCOUNT_RECYCLER_FUNCTION_NAME:
        print("Warning: ACCOUNT_RECYCLER_FUNCTION_NAME not set, skipping")
        return False
    try:
        payload = {'recycleAll': False, 'accountIds': account_ids}
        lambda_client.invoke(
            FunctionName=ACCOUNT_RECYCLER_FUNCTION_NAME,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
        print(f"Triggered AccountRecycler for {len(account_ids)} accounts")
        return True
    except Exception as e:
        print(f"Error triggering AccountRecycler: {e}")
        return False


def check_and_replenish(config):
    """Check AVAILABLE count and trigger replenishment if needed"""
    if not POOL_MANAGER_FUNCTION_NAME:
        print("Warning: POOL_MANAGER_FUNCTION_NAME not set, skipping")
        return False
    try:
        response = dynamodb.query(
            TableName=DYNAMODB_TABLE_NAME,
            IndexName='StateIndex',
            KeyConditionExpression='#state = :state',
            ExpressionAttributeNames={'#state': 'state'},
            ExpressionAttributeValues={':state': {'S': 'AVAILABLE'}},
            Select='COUNT'
        )
        available_count = response.get('Count', 0)
        min_pool_size = int(config.get('MinimumPoolSize', '5'))

        if available_count < min_pool_size:
            print(f"AVAILABLE ({available_count}) < MinimumPoolSize ({min_pool_size}), triggering replenishment")
            lambda_client.invoke(
                FunctionName=POOL_MANAGER_FUNCTION_NAME,
                InvocationType='Event',
                Payload=json.dumps({'action': 'force_replenishment'})
            )
            return True
        print(f"AVAILABLE ({available_count}) >= MinimumPoolSize ({min_pool_size}), no replenishment needed")
        return False
    except Exception as e:
        print(f"Error checking pool size: {e}")
        return False


def check_and_trigger_blueprint_update():
    """Check if any AVAILABLE account has an outdated blueprint stack version.

    Samples one AVAILABLE account and checks its DataZone-Blueprints-* stack
    TemplateVersion output. If it doesn't match CURRENT_BLUEPRINT_VERSION,
    triggers AccountRecycler with updateBlueprints=true to update the fleet.

    This runs on every scheduled reconciler invocation, so template updates
    are automatically pushed to all accounts within one reconciler cycle.
    """
    # Must match the TemplateVersion output in blueprint-enablement-iam.yaml
    CURRENT_BLUEPRINT_VERSION = "2"
    ACCOUNT_RECYCLER = os.environ.get('ACCOUNT_RECYCLER_FUNCTION_NAME', 'AccountRecycler')

    try:
        # Sample one AVAILABLE account
        resp = dynamodb.query(
            TableName=DYNAMODB_TABLE_NAME,
            IndexName='StateIndex',
            KeyConditionExpression='#s = :s',
            ExpressionAttributeNames={'#s': 'state'},
            ExpressionAttributeValues={':s': {'S': 'AVAILABLE'}},
            Limit=1
        )
        items = resp.get('Items', [])
        if not items:
            return False

        sample_account_id = items[0]['accountId']['S']

        # Assume DomainAccess role in the sample account
        domain_id = DOMAIN_ID
        role_arn = f"arn:aws:iam::{sample_account_id}:role/SMUS-AccountPoolFactory-DomainAccess"
        assumed = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName='reconciler-blueprint-check',
            ExternalId=domain_id,
            DurationSeconds=900
        )
        creds = assumed['Credentials']
        cf = boto3.client(
            'cloudformation',
            region_name=REGION,
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken']
        )

        stack_name = f"DataZone-Blueprints-{sample_account_id}"
        resp = cf.describe_stacks(StackName=stack_name)
        outputs = resp['Stacks'][0].get('Outputs', [])
        deployed_version = next(
            (o['OutputValue'] for o in outputs if o['OutputKey'] == 'TemplateVersion'),
            None
        )

        if deployed_version == CURRENT_BLUEPRINT_VERSION:
            print(f"Blueprint template version up to date (v{deployed_version}), no update needed")
            return False

        print(f"Blueprint template version outdated (deployed={deployed_version}, current={CURRENT_BLUEPRINT_VERSION}) — triggering fleet update")
        lambda_client.invoke(
            FunctionName=ACCOUNT_RECYCLER,
            InvocationType='Event',
            Payload=json.dumps({'updateBlueprints': True})
        )
        return True

    except Exception as e:
        print(f"Warning: Blueprint version check failed: {e}")
        return False

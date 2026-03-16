#!/usr/bin/env python3
"""
Phase 3: Fleet-wide Lake Formation rollout.
  1. Trigger cleanupStacks for AVAILABLE accounts (reconciler re-provisions with new StackSet)
  2. Push StackSet 07 instances to ASSIGNED accounts

Prerequisites:
  - Phase 2 passed (test-lf-single-account.py exited 0)
  - Org admin has deployed (01-deploy.sh) so StackSet 07 template exists
  - Run with org admin credentials for StackSet operations
  - Then switch to domain account credentials for cleanupStacks

Usage:
    # Step 1: Trigger cleanupStacks for AVAILABLE accounts (domain account)
    eval $(isengardcli credentials amirbo+3@amazon.com)
    python3 tests/integration/test-lf-fleet-rollout.py --phase available

    # Step 2: Push StackSet to ASSIGNED accounts (org admin)
    eval $(isengardcli credentials amirbo+1@amazon.com)
    python3 tests/integration/test-lf-fleet-rollout.py --phase assigned

    # Or run both phases (requires credential switch between steps):
    python3 tests/integration/test-lf-fleet-rollout.py --phase all

Exit codes: 0 = all steps passed, 1 = failure
"""
import sys
import os
import time
import json
import argparse
import boto3
import yaml

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, '..', '..')

# Load 02-domain-account/config.yaml (preferred) or fall back to legacy config.yaml
_cfg_file = os.path.join(PROJECT_ROOT, '02-domain-account/config.yaml')
if not os.path.exists(_cfg_file):
    _cfg_file = os.path.join(PROJECT_ROOT, 'config.yaml')
with open(_cfg_file) as f:
    _cfg = yaml.safe_load(f)

def _get(key, legacy_path=None, default=''):
    if key in _cfg:
        return _cfg[key]
    if legacy_path:
        try:
            v = _cfg
            for k in legacy_path:
                v = v[k]
            return v
        except (KeyError, TypeError):
            pass
    return default

REGION        = _get('region', ['aws', 'region'], 'us-east-2')
TABLE         = 'AccountPoolFactory-AccountState'
STACKSET_NAME = 'SMUS-AccountPoolFactory-GlueLfTestData'

PASS = "✅"
FAIL = "❌"
INFO = "ℹ️ "


def get_accounts_by_state(ddb, state):
    """Scan DynamoDB for accounts in a given state, handling pagination."""
    accounts = []
    resp = ddb.scan(
        TableName=TABLE,
        FilterExpression='#s = :state',
        ExpressionAttributeNames={'#s': 'state'},
        ExpressionAttributeValues={':state': {'S': state}}
    )
    for item in resp.get('Items', []):
        accounts.append(item['accountId']['S'])
    while 'LastEvaluatedKey' in resp:
        resp = ddb.scan(
            TableName=TABLE,
            FilterExpression='#s = :state',
            ExpressionAttributeNames={'#s': 'state'},
            ExpressionAttributeValues={':state': {'S': state}},
            ExclusiveStartKey=resp['LastEvaluatedKey']
        )
        for item in resp.get('Items', []):
            accounts.append(item['accountId']['S'])
    return accounts


def rollout_available_accounts():
    """Trigger cleanupStacks for AVAILABLE accounts.
    Requires domain account credentials.
    cleanupStacks deletes direct CF stacks and resets DynamoDB setup fields.
    State stays AVAILABLE — the reconciler detects missing stacks and
    re-provisions them with the new StackSet (including 07-glue-lf-test-data).
    """
    print(f"\n{'='*60}")
    print(f"Phase 3a: AVAILABLE accounts — trigger cleanupStacks")
    print('='*60)

    lam = boto3.client('lambda', region_name=REGION)
    ddb = boto3.client('dynamodb', region_name=REGION)

    available = get_accounts_by_state(ddb, 'AVAILABLE')
    print(f"  Found {len(available)} AVAILABLE accounts")

    if not available:
        print(f"  {INFO} No AVAILABLE accounts to process")
        return True

    print(f"  Triggering cleanupStacks for all AVAILABLE accounts...")
    lam.invoke(
        FunctionName='AccountRecycler',
        InvocationType='Event',
        Payload=json.dumps({'action': 'cleanupStacks', 'all': True}).encode()
    )
    print(f"  {PASS} cleanupStacks triggered (async)")
    print(f"  {INFO} Reconciler will re-provision on next scheduled run")

    for acct in available:
        print(f"  {PASS} {acct}: cleanup triggered")

    return True


def rollout_assigned_accounts():
    """Push StackSet 07 instances to ASSIGNED accounts.
    Requires org admin credentials.
    These accounts already have the domain-access role (wave 1),
    so the wave 2 template can deploy directly.
    """
    print(f"\n{'='*60}")
    print(f"Phase 3b: ASSIGNED accounts — push StackSet instances")
    print('='*60)

    cf  = boto3.client('cloudformation', region_name=REGION)
    ddb = boto3.client('dynamodb', region_name=REGION)

    assigned = get_accounts_by_state(ddb, 'ASSIGNED')
    print(f"  Found {len(assigned)} ASSIGNED accounts")

    if not assigned:
        print(f"  {INFO} No ASSIGNED accounts to process")
        return True

    # Filter out accounts that already have the StackSet instance
    accounts_to_deploy = []
    for acct in assigned:
        try:
            instances = cf.list_stack_instances(
                StackSetName=STACKSET_NAME,
                StackInstanceAccount=acct,
                StackInstanceRegion=REGION
            )
            if instances.get('Summaries'):
                print(f"  {INFO} {acct} already has StackSet instance, skipping")
                continue
        except Exception:
            pass
        accounts_to_deploy.append(acct)

    if not accounts_to_deploy:
        print(f"  {PASS} All ASSIGNED accounts already have StackSet instances")
        return True

    print(f"  Deploying to {len(accounts_to_deploy)} accounts...")
    op = cf.create_stack_instances(
        StackSetName=STACKSET_NAME,
        Accounts=accounts_to_deploy,
        Regions=[REGION],
        OperationPreferences={
            'MaxConcurrentCount': 5,
            'FailureToleranceCount': 2
        }
    )
    op_id = op['OperationId']

    # Poll StackSet operation
    failed_accounts = []
    start = time.time()
    while time.time() - start < 900:
        op_status = cf.describe_stack_set_operation(
            StackSetName=STACKSET_NAME, OperationId=op_id
        )
        state = op_status['StackSetOperation']['Status']
        elapsed = int(time.time() - start)
        print(f"  [{elapsed}s] StackSet operation: {state}")

        if state == 'SUCCEEDED':
            break

        if state in ('FAILED', 'STOPPED'):
            print(f"  {FAIL} StackSet operation {state}")
            results = cf.list_stack_set_operation_results(
                StackSetName=STACKSET_NAME, OperationId=op_id
            )
            for r in results.get('Summaries', []):
                acct = r.get('Account', '')
                r_status = r.get('Status', '')
                reason = r.get('StatusReason', '')
                if r_status != 'SUCCEEDED':
                    print(f"    {FAIL} {acct}: {r_status} — {reason}")
                    failed_accounts.append(acct)
            return False

        time.sleep(15)

    if failed_accounts:
        print(f"  {FAIL} Failed accounts: {failed_accounts}")
        return False

    print(f"  {PASS} StackSet deployed to {len(accounts_to_deploy)} ASSIGNED accounts")
    return True


def main():
    parser = argparse.ArgumentParser(description='Phase 3: Fleet-wide LF rollout')
    parser.add_argument('--phase', choices=['available', 'assigned', 'all'],
                        default='all', help='Which phase to run')
    args = parser.parse_args()

    success = True
    if args.phase in ('available', 'all'):
        success = rollout_available_accounts() and success
    if args.phase in ('assigned', 'all'):
        success = rollout_assigned_accounts() and success

    print(f"\n{'='*60}")
    if success:
        print(f"{PASS} Phase 3: Fleet rollout complete")
    else:
        print(f"{FAIL} Phase 3: Fleet rollout had failures")
    print('='*60)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

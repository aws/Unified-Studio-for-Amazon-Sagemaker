#!/usr/bin/env python3
"""
Check that a pool account returns to AVAILABLE state after project deletion.

Usage:
    python3 tests/integration/check-reclaim.py <account_id> [--timeout 300]

Polls DynamoDB until the account reaches AVAILABLE state or timeout.
The reclaim is triggered by DataZone Environment Deletion Completed events
or by the hourly reconciler.
"""
import sys
import os
import time
import argparse
import boto3
import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, '..', '..')

_cfg_file = os.path.join(PROJECT_ROOT, 'domain-config.yaml')
if not os.path.exists(_cfg_file):
    _cfg_file = os.path.join(PROJECT_ROOT, 'config.yaml')
with open(_cfg_file) as f:
    config = yaml.safe_load(f)

REGION = config.get('region') or config.get('aws', {}).get('region', 'us-east-2')
TABLE  = 'AccountPoolFactory-AccountState'


def check_reclaim(account_id: str, timeout: int) -> bool:
    ddb = boto3.client('dynamodb', region_name=REGION)
    start = time.time()
    interval = 15

    print(f"Polling DynamoDB for account {account_id} to return to AVAILABLE (timeout={timeout}s)...")
    print(f"Note: reclaim is triggered by DataZone Environment Deletion Completed events.")
    print(f"      If environments take time to delete, this may take several minutes.")

    while time.time() - start < timeout:
        resp = ddb.query(
            TableName=TABLE,
            KeyConditionExpression='accountId = :a',
            ExpressionAttributeValues={':a': {'S': account_id}},
            ScanIndexForward=False,
            Limit=1
        )
        items = resp.get('Items', [])
        if items:
            state = items[0].get('state', {}).get('S', 'UNKNOWN')
            recycled_date = items[0].get('recycledDate', {}).get('S', '')
            elapsed = int(time.time() - start)
            print(f"  [{elapsed}s] state={state}")
            if state == 'AVAILABLE':
                print(f"\n✅ Account {account_id} is back to AVAILABLE")
                if recycled_date:
                    print(f"   recycledDate : {recycled_date}")
                return True
            if state in ('CLEANING', 'DELETING'):
                print(f"  (reclaim in progress...)")
        else:
            print(f"  Account {account_id} not found in pool")
            return False
        time.sleep(interval)

    print(f"\n❌ Timeout: account {account_id} did not return to AVAILABLE within {timeout}s")
    print(f"   Check PoolManager and AccountRecycler CloudWatch logs for details.")
    return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('account_id', help='Pool account ID to check')
    parser.add_argument('--timeout', type=int, default=300, help='Max wait seconds (default: 300)')
    args = parser.parse_args()

    ok = check_reclaim(args.account_id, args.timeout)
    sys.exit(0 if ok else 1)

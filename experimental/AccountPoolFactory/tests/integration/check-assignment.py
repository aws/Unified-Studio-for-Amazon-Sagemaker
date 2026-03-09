#!/usr/bin/env python3
"""
Check that a pool account is in ASSIGNED state after project creation.

Usage:
    python3 tests/integration/check-assignment.py <account_id> [--timeout 120]

Polls DynamoDB until the account reaches ASSIGNED state or timeout.
"""
import sys
import os
import time
import json
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

def check_assignment(account_id: str, timeout: int) -> bool:
    ddb = boto3.client('dynamodb', region_name=REGION)
    start = time.time()
    interval = 10

    print(f"Polling DynamoDB for account {account_id} to reach ASSIGNED state (timeout={timeout}s)...")

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
            assigned_date = items[0].get('assignedDate', {}).get('S', '')
            project_id = items[0].get('projectId', {}).get('S', '')
            elapsed = int(time.time() - start)
            print(f"  [{elapsed}s] state={state}")
            if state == 'ASSIGNED':
                print(f"\n✅ Account {account_id} is ASSIGNED")
                print(f"   assignedDate : {assigned_date}")
                print(f"   projectId    : {project_id or '(set by PoolManager on env event)'}")
                return True
        else:
            print(f"  Account {account_id} not found in pool")
            return False
        time.sleep(interval)

    print(f"\n❌ Timeout: account {account_id} did not reach ASSIGNED state within {timeout}s")
    return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('account_id', help='Pool account ID to check')
    parser.add_argument('--timeout', type=int, default=120, help='Max wait seconds (default: 120)')
    args = parser.parse_args()

    ok = check_assignment(args.account_id, args.timeout)
    sys.exit(0 if ok else 1)

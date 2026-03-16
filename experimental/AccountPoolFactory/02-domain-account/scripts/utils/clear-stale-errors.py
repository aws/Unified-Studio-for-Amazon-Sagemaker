#!/usr/bin/env python3
"""
Clear stale error fields from AVAILABLE accounts in DynamoDB.

Finds AVAILABLE accounts that still have errorMessage, failedStep, or
retryCount > 0, and removes those fields. This is a one-time fix for
accounts that were marked AVAILABLE by SetupOrchestrator without clearing
error fields from a previous failure.

Usage:
    eval $(isengardcli credentials amirbo+3@amazon.com)
    python3 02-domain-account/scripts/utils/clear-stale-errors.py
    python3 02-domain-account/scripts/utils/clear-stale-errors.py --dry-run
"""
import argparse
import boto3

TABLE = 'AccountPoolFactory-AccountState'
REGION = 'us-east-2'

dynamodb = boto3.client('dynamodb', region_name=REGION)


def get_available_with_errors():
    """Find AVAILABLE accounts that have stale error fields."""
    results = []
    resp = dynamodb.scan(TableName=TABLE)
    items = resp.get('Items', [])
    while 'LastEvaluatedKey' in resp:
        resp = dynamodb.scan(TableName=TABLE, ExclusiveStartKey=resp['LastEvaluatedKey'])
        items.extend(resp.get('Items', []))

    # Get latest record per account
    latest = {}
    for item in items:
        aid = item['accountId']['S']
        ts = item['timestamp'].get('S', item['timestamp'].get('N', ''))
        if aid not in latest or ts > latest[aid]['timestamp'].get('S', latest[aid]['timestamp'].get('N', '')):
            latest[aid] = item

    for aid, item in latest.items():
        state = item.get('state', {}).get('S', '')
        if state != 'AVAILABLE':
            continue
        error = item.get('errorMessage', {}).get('S', '')
        failed = item.get('failedStep', {}).get('S', '')
        retry = int(item.get('retryCount', {}).get('N', '0'))
        recon = item.get('reconciliationNote', {}).get('S', '')
        if error or failed or retry > 0 or recon:
            results.append({
                'accountId': aid,
                'timestamp': item['timestamp'],
                'error': error[:80] if error else '',
                'failedStep': failed,
                'retryCount': retry,
                'reconciliationNote': recon[:80] if recon else '',
            })
    return results


def clear_errors(account_id, timestamp, dry_run=False):
    """Remove stale error fields from one account."""
    if dry_run:
        return True
    try:
        dynamodb.update_item(
            TableName=TABLE,
            Key={'accountId': {'S': account_id}, 'timestamp': timestamp},
            UpdateExpression='REMOVE errorMessage, failedStep, reconciliationNote SET retryCount = :zero',
            ExpressionAttributeValues={':zero': {'N': '0'}})
        return True
    except Exception as e:
        print(f'  ❌ {account_id}: {e}')
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    accounts = get_available_with_errors()
    print(f'Found {len(accounts)} AVAILABLE accounts with stale errors')

    if not accounts:
        print('Nothing to fix')
        return

    fixed = 0
    for a in accounts:
        prefix = '🔍' if args.dry_run else '✅'
        ok = clear_errors(a['accountId'], a['timestamp'], args.dry_run)
        if ok:
            fixed += 1
            print(f'  {prefix} {a["accountId"]}: retry={a["retryCount"]} error="{a["error"]}"')

    action = 'would fix' if args.dry_run else 'fixed'
    print(f'\nDone: {action} {fixed}/{len(accounts)} accounts')


if __name__ == '__main__':
    main()

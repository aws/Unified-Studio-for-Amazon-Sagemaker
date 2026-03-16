#!/usr/bin/env python3
"""Monitor pool seeding progress. Run with domain account credentials."""
import boto3, time, sys
from collections import Counter
from datetime import datetime, timezone

ddb = boto3.client('dynamodb', region_name='us-east-2')
TABLE = 'AccountPoolFactory-AccountState'

def poll():
    r = ddb.scan(TableName=TABLE)
    items = r.get('Items', [])
    states = Counter(i['state']['S'] for i in items)
    now = datetime.now(timezone.utc).strftime('%H:%M:%S')
    print(f'\n=== {now} UTC  Total: {len(items)}  {dict(states)} ===')
    for i in sorted(items, key=lambda x: x['state']['S']):
        ss = [s['S'].split('-')[-1] for s in i.get('deployedStackSets', {}).get('L', [])]
        pool = i.get('poolName', {}).get('S', '-')
        name = i.get('accountName', {}).get('S', '-')
        print(f'  {i["accountId"]["S"]}  {i["state"]["S"]:12}  pool={pool}  stacks={ss}  {name}')
    return states

interval = int(sys.argv[1]) if len(sys.argv) > 1 else 30
target = 5

print(f'Monitoring pool (target={target}, polling every {interval}s). Ctrl+C to stop.')
while True:
    try:
        states = poll()
        available = states.get('AVAILABLE', 0)
        if available >= target:
            print(f'\n✅ Pool seeded! {available} AVAILABLE accounts.')
            break
    except Exception as e:
        print(f'Error: {e}')
    time.sleep(interval)

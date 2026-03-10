#!/usr/bin/env python3
"""
One-time backfill: set poolName on DynamoDB records that are missing it.

Scans AccountPoolFactory-AccountState for records without a poolName attribute,
looks up the PoolName tag on the account in AWS Organizations, and patches the
DynamoDB record in-place.

Requires two sets of credentials — run in two steps:

  Step 1: dump org tags (run as org admin amirbo+1)
    eval $(isengardcli credentials amirbo+1@amazon.com)
    python3 scripts/utils/backfill-pool-names.py --dump-tags

  Step 2: patch DynamoDB (run as domain account amirbo+3)
    eval $(isengardcli credentials amirbo+3@amazon.com)
    python3 scripts/utils/backfill-pool-names.py [--dry-run]
"""

import sys
import json
import os
import boto3

DRY_RUN = '--dry-run' in sys.argv
DUMP_TAGS = '--dump-tags' in sys.argv

TABLE = 'AccountPoolFactory-AccountState'
REGION = 'us-east-2'
TAGS_CACHE_FILE = '/tmp/account-pool-tags.json'

# ── Step 1: dump org tags ─────────────────────────────────────────────────────

if DUMP_TAGS:
    print("Dumping PoolName tags from AWS Organizations...")
    org = boto3.client('organizations', region_name=REGION)
    paginator = org.get_paginator('list_accounts')
    tags_map = {}
    for page in paginator.paginate():
        for acct in page['Accounts']:
            acct_id = acct['Id']
            try:
                resp = org.list_tags_for_resource(ResourceId=acct_id)
                tags = {t['Key']: t['Value'] for t in resp.get('Tags', [])}
                pool = tags.get('PoolName', '')
                if pool:
                    tags_map[acct_id] = pool
                    print(f"  {acct_id} → {pool}")
            except Exception as e:
                print(f"  WARN {acct_id}: {e}")
    with open(TAGS_CACHE_FILE, 'w') as f:
        json.dump(tags_map, f, indent=2)
    print(f"\nWrote {len(tags_map)} entries to {TAGS_CACHE_FILE}")
    print("Now switch to domain account and run without --dump-tags")
    sys.exit(0)

# ── Step 2: patch DynamoDB ────────────────────────────────────────────────────

print(f"{'[DRY RUN] ' if DRY_RUN else ''}Backfilling poolName on DynamoDB records")
print(f"Table: {TABLE}  Region: {REGION}\n")

if not os.path.exists(TAGS_CACHE_FILE):
    print(f"ERROR: {TAGS_CACHE_FILE} not found.")
    print("Run with --dump-tags first (as org admin amirbo+1).")
    sys.exit(1)

with open(TAGS_CACHE_FILE) as f:
    tag_cache = json.load(f)
print(f"Loaded {len(tag_cache)} account→pool mappings from {TAGS_CACHE_FILE}\n")

dynamodb = boto3.client('dynamodb', region_name=REGION)

# ── Scan for records missing poolName ─────────────────────────────────────────

paginator = dynamodb.get_paginator('scan')
missing = []

for page in paginator.paginate(
    TableName=TABLE,
    FilterExpression='attribute_not_exists(poolName)',
    ProjectionExpression='accountId, #ts, #st',
    ExpressionAttributeNames={'#ts': 'timestamp', '#st': 'state'}
):
    for item in page['Items']:
        account_id = item.get('accountId', {}).get('S', '')
        timestamp = item.get('timestamp', {}).get('N', '')
        state = item.get('state', {}).get('S', '')
        if account_id and timestamp:
            missing.append((account_id, timestamp, state))

print(f"Found {len(missing)} records missing poolName\n")

if not missing:
    print("Nothing to backfill.")
    sys.exit(0)

# ── Look up PoolName org tag and patch each record ────────────────────────────

patched = 0
skipped = 0

for account_id, timestamp, state in missing:
    if account_id not in tag_cache:
        print(f"  SKIP  {account_id} (state={state}) — not in org tags dump")
        skipped += 1
        continue

    pool_name = tag_cache[account_id]

    if not pool_name:
        print(f"  SKIP  {account_id} (state={state}) — no PoolName tag in Organizations")
        skipped += 1
        continue

    prefix = '[DRY RUN] ' if DRY_RUN else ''
    print(f"  {prefix}PATCH {account_id} (state={state}) → poolName={pool_name}")

    if not DRY_RUN:
        try:
            dynamodb.update_item(
                TableName=TABLE,
                Key={
                    'accountId': {'S': account_id},
                    'timestamp': {'N': timestamp}
                },
                UpdateExpression='SET poolName = :pool',
                ConditionExpression='attribute_not_exists(poolName)',
                ExpressionAttributeValues={':pool': {'S': pool_name}}
            )
            patched += 1
        except dynamodb.exceptions.ConditionalCheckFailedException:
            print(f"         (already set, skipping)")
        except Exception as e:
            print(f"         ERROR: {e}")
            skipped += 1

print(f"\nDone — patched={patched}  skipped={skipped}  dry_run={DRY_RUN}")

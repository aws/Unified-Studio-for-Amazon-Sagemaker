#!/usr/bin/env python3
"""Check recent AccountRecycler and SetupOrchestrator logs."""
import boto3, time

logs = boto3.client('logs', region_name='us-east-2')
now = int(time.time() * 1000)
five_min_ago = now - 5 * 60 * 1000

for log_group in ['/aws/lambda/AccountRecycler', '/aws/lambda/SetupOrchestrator']:
    print(f"\n{'='*60}")
    print(f"  {log_group} (last 5 min)")
    print(f"{'='*60}")
    try:
        resp = logs.filter_log_events(
            logGroupName=log_group,
            startTime=five_min_ago,
            endTime=now,
            limit=50,
            interleaved=True
        )
        events = resp.get('events', [])
        if not events:
            print("  (no events)")
        for e in events:
            msg = e['message'].strip()
            if msg.startswith('START ') or msg.startswith('END ') or msg.startswith('REPORT '):
                continue
            print(f"  {msg[:200]}")
    except Exception as e:
        print(f"  ERROR: {e}")

#!/usr/bin/env python3
"""Check SetupOrchestrator recent logs — last 10 minutes, focus on blueprint retries and completions."""
import boto3, time

logs = boto3.client('logs', region_name='us-east-2')
now = int(time.time() * 1000)
ten_min_ago = now - 10 * 60 * 1000

log_group = '/aws/lambda/SetupOrchestrator'

try:
    resp = logs.filter_log_events(
        logGroupName=log_group,
        startTime=ten_min_ago,
        endTime=now,
        limit=500,
        interleaved=True
    )
    events = resp.get('events', [])
    
    cleanup = 0
    completed = 0
    failed = 0
    retries = 0
    bp_retries = 0
    wave1_done = 0
    wave2_done = 0
    
    for e in events:
        msg = e['message'].strip()
        if 'Old stack cleanup complete' in msg: cleanup += 1
        elif 'Setup completed' in msg: completed += 1
        elif 'Setup workflow failed' in msg: failed += 1
        elif 'busy, retry' in msg: retries += 1
        elif 'BlueprintEnablement attempt' in msg: bp_retries += 1
        elif 'Wave 1 completed' in msg: wave1_done += 1
        elif 'Wave 2 completed' in msg: wave2_done += 1
    
    print(f"SetupOrchestrator (last 10 min, {len(events)} events):")
    print(f"  Old stack cleanups: {cleanup}")
    print(f"  Wave 1 completed: {wave1_done}")
    print(f"  Wave 2 completed: {wave2_done}")
    print(f"  Setup fully completed: {completed}")
    print(f"  Setup failed: {failed}")
    print(f"  StackSet busy retries: {retries}")
    print(f"  Blueprint retries: {bp_retries}")

except Exception as e:
    print(f"ERROR: {e}")

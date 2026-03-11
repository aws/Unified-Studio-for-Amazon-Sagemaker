#!/usr/bin/env python3
"""Check BlueprintEnablement failures in detail."""
import boto3, time

logs = boto3.client('logs', region_name='us-east-2')
now = int(time.time() * 1000)
ten_min_ago = now - 10 * 60 * 1000

resp = logs.filter_log_events(
    logGroupName='/aws/lambda/SetupOrchestrator',
    startTime=ten_min_ago,
    endTime=now,
    limit=500,
    interleaved=True
)

for e in resp.get('events', []):
    msg = e['message'].strip()
    if 'Blueprint' in msg or 'blueprint' in msg or 'Wave 2' in msg:
        print(msg[:300])

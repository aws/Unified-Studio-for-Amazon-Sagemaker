#!/usr/bin/env python3
"""Check for Lambda timeouts and long-running invocations."""
import boto3, time

logs = boto3.client('logs', region_name='us-east-2')
now = int(time.time() * 1000)
thirty_min_ago = now - 30 * 60 * 1000

# Check for REPORT lines to see durations and timeouts
resp = logs.filter_log_events(
    logGroupName='/aws/lambda/SetupOrchestrator',
    startTime=thirty_min_ago,
    endTime=now,
    filterPattern='REPORT',
    limit=50,
    interleaved=True
)

timeouts = 0
completed = 0
durations = []

for e in resp.get('events', []):
    msg = e['message'].strip()
    if 'Task timed out' in msg:
        timeouts += 1
    elif 'REPORT' in msg:
        completed += 1
        # Extract duration
        parts = msg.split('\t')
        for p in parts:
            if 'Duration:' in p and 'Billed' not in p:
                try:
                    dur_ms = float(p.split(':')[1].strip().replace(' ms', ''))
                    durations.append(dur_ms)
                except:
                    pass

print(f"Lambda invocations (last 30 min): {completed}")
print(f"Timeouts: {timeouts}")
if durations:
    print(f"Duration range: {min(durations)/1000:.0f}s - {max(durations)/1000:.0f}s")
    print(f"Average: {sum(durations)/len(durations)/1000:.0f}s")
    over_10min = sum(1 for d in durations if d > 600000)
    print(f"Over 10 min: {over_10min}")

# Also check for Task timed out
resp2 = logs.filter_log_events(
    logGroupName='/aws/lambda/SetupOrchestrator',
    startTime=thirty_min_ago,
    endTime=now,
    filterPattern='Task timed out',
    limit=20,
    interleaved=True
)
timeout_events = resp2.get('events', [])
if timeout_events:
    print(f"\nTimeout events: {len(timeout_events)}")
    for e in timeout_events[:5]:
        print(f"  {e['message'].strip()[:200]}")

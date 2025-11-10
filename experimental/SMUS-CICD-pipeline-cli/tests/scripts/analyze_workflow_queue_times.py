#!/usr/bin/env python3
"""
Analyze workflow queue times from EventBridge events in CloudWatch Logs.

This script queries CloudWatch Logs for workflow state changes captured by EventBridge
and calculates the time workflows spend in QUEUED state before transitioning to RUNNING.
"""

import boto3
import json
import time
from datetime import datetime, timedelta
from collections import defaultdict

def analyze_queue_times(region='us-east-2', days_back=7):
    """Analyze workflow queue times from EventBridge events."""
    
    logs = boto3.client('logs', region_name=region)
    log_group = '/aws/events/airflow-serverless-workflows'
    
    # Calculate time range
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days_back)
    
    print(f"Analyzing workflow queue times from {start_time} to {end_time}")
    print(f"Log group: {log_group}\n")
    
    # Query for workflow events
    query = """
    fields @timestamp, @message
    | parse @message /RunId['":\s]+(?<run_id>[^'"]+)/
    | parse @message /Status['":\s]+(?<status>[^'"]+)/
    | parse @message /WorkflowArn['":\s]+(?<workflow_arn>[^'"]+)/
    | filter @message like /StartWorkflowRun/ or @message like /status/ or @message like /QUEUED/ or @message like /RUNNING/
    | sort @timestamp asc
    """
    
    try:
        # Start query
        response = logs.start_query(
            logGroupName=log_group,
            startTime=int(start_time.timestamp()),
            endTime=int(end_time.timestamp()),
            queryString=query,
            limit=1000
        )
        
        query_id = response['queryId']
        print(f"Query started: {query_id}")
        print("Waiting for results...\n")
        
        # Wait for query to complete
        while True:
            result = logs.get_query_results(queryId=query_id)
            status = result['status']
            
            if status == 'Complete':
                break
            elif status == 'Failed':
                print(f"Query failed: {result}")
                return
            
            time.sleep(2)
        
        # Process results
        events = result['results']
        
        if not events:
            print("No events found. The EventBridge rules may need time to capture events.")
            print("\nTo test, run a workflow and check back in a few minutes:")
            print("  cd experimental/SMUS-CICD-pipeline-cli")
            print("  pytest tests/integration/examples-analytics-workflows/notebooks/test_notebooks_workflow.py -v")
            return
        
        print(f"Found {len(events)} events\n")
        
        # Group events by run_id
        runs = defaultdict(dict)
        
        for event in events:
            event_dict = {field['field']: field['value'] for field in event}
            timestamp = event_dict.get('@timestamp')
            message = event_dict.get('@message', '')
            
            # Parse event details
            if 'StartWorkflowRun' in message:
                # Extract run_id from API call
                try:
                    msg_json = json.loads(message)
                    run_id = msg_json.get('detail', {}).get('responseElements', {}).get('runId')
                    if run_id:
                        runs[run_id]['started'] = timestamp
                except:
                    pass
            
            # Look for status changes in message
            if 'QUEUED' in message or 'RUNNING' in message:
                # Try to extract run_id and status
                pass
        
        # Calculate queue times
        queue_times = []
        for run_id, data in runs.items():
            if 'started' in data and 'running' in data:
                start = datetime.fromisoformat(data['started'].replace('Z', '+00:00'))
                running = datetime.fromisoformat(data['running'].replace('Z', '+00:00'))
                queue_seconds = (running - start).total_seconds()
                
                queue_times.append({
                    'run_id': run_id,
                    'queue_seconds': queue_seconds,
                    'started': start,
                    'running': running
                })
        
        if queue_times:
            # Print statistics
            avg = sum(d['queue_seconds'] for d in queue_times) / len(queue_times)
            min_time = min(d['queue_seconds'] for d in queue_times)
            max_time = max(d['queue_seconds'] for d in queue_times)
            
            print("=" * 80)
            print("WORKFLOW QUEUE TIME ANALYSIS")
            print("=" * 80)
            print(f"Total workflows: {len(queue_times)}")
            print(f"Average queue time: {avg:.0f}s ({avg/60:.1f}m)")
            print(f"Min queue time: {min_time:.0f}s ({min_time/60:.1f}m)")
            print(f"Max queue time: {max_time:.0f}s ({max_time/60:.1f}m)")
            print("=" * 80)
        else:
            print("No complete workflow runs found with both start and running timestamps.")
            print("\nNote: EventBridge events may take a few minutes to appear in CloudWatch Logs.")
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure:")
        print("1. EventBridge rules are created")
        print("2. CloudWatch Logs permissions are set")
        print("3. At least one workflow has been run since rules were created")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze workflow queue times from EventBridge events')
    parser.add_argument('--region', default='us-east-2', help='AWS region')
    parser.add_argument('--days', type=int, default=7, help='Number of days to look back')
    
    args = parser.parse_args()
    
    analyze_queue_times(region=args.region, days_back=args.days)

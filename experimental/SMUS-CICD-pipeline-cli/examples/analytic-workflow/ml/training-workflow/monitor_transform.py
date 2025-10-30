#!/usr/bin/env python3
import boto3
import time

job_name = 'json-test-1761679957'
region = 'us-east-1'

sm = boto3.client('sagemaker', region_name=region)

print(f"Monitoring batch transform job: {job_name}\n")

while True:
    response = sm.describe_transform_job(TransformJobName=job_name)
    status = response['TransformJobStatus']
    
    print(f"[{time.strftime('%H:%M:%S')}] Status: {status}")
    
    if status in ['Completed', 'Failed', 'Stopped']:
        print(f"\n✅ Job finished with status: {status}")
        if status == 'Failed':
            print(f"Failure reason: {response.get('FailureReason', 'Unknown')}")
        elif status == 'Completed':
            print(f"Output location: {response['TransformOutput']['S3OutputPath']}")
        break
    
    time.sleep(10)

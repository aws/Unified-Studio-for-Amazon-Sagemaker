#!/usr/bin/env python3
"""Test batch transform directly with latest trained model"""
import boto3
import time

# Configuration
REGION = 'us-east-1'
BUCKET = 'amazon-sagemaker-198737698272-us-east-1-4pg255jku47vdz'
ROLE = 'arn:aws:iam::198737698272:role/SMUSCICDTestRole'
MODEL_DATA = 's3://amazon-sagemaker-198737698272-us-east-1-4pg255jku47vdz/shared/ml/output/model-artifacts/orchestrated-training-1762188005/output/model.tar.gz'
INFERENCE_DATA = f's3://{BUCKET}/shared/ml/bundle/inference-data/'
OUTPUT_PATH = f's3://{BUCKET}/shared/ml/output/test-inference-results/'

sm = boto3.client('sagemaker', region_name=REGION)

# Create model
model_name = f'test-sklearn-model-{int(time.time())}'
print(f"Creating model: {model_name}")

sm.create_model(
    ModelName=model_name,
    PrimaryContainer={
        'Image': '683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3',
        'ModelDataUrl': MODEL_DATA,
        'Environment': {
            'SAGEMAKER_PROGRAM': 'inference.py',
            'SAGEMAKER_SUBMIT_DIRECTORY': MODEL_DATA,
        }
    },
    ExecutionRoleArn=ROLE
)

# Create transform job
job_name = f'test-inference-{int(time.time())}'
print(f"Starting transform job: {job_name}")

sm.create_transform_job(
    TransformJobName=job_name,
    ModelName=model_name,
    TransformInput={
        'DataSource': {
            'S3DataSource': {
                'S3DataType': 'S3Prefix',
                'S3Uri': INFERENCE_DATA
            }
        },
        'ContentType': 'text/csv',
        'SplitType': 'Line'
    },
    TransformOutput={
        'S3OutputPath': OUTPUT_PATH,
        'AssembleWith': 'Line'
    },
    TransformResources={
        'InstanceType': 'ml.m5.large',
        'InstanceCount': 1
    }
)

print(f"\nMonitor at: https://console.aws.amazon.com/sagemaker/home?region={REGION}#/transform-jobs/{job_name}")
print(f"\nCheck status with:")
print(f"aws sagemaker describe-transform-job --transform-job-name {job_name} --region {REGION}")

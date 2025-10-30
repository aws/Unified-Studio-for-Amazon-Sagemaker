#!/usr/bin/env python3
import boto3
import time
from sagemaker.sklearn.model import SKLearnModel
from sagemaker import Session

region = 'us-east-1'
bucket = f'demo-bucket-smus-ml-{region}'
role = 'arn:aws:iam::058264284947:role/service-role/AmazonSageMaker-ExecutionRole-20241115T121975'

# Use latest trained model from us-east-1
model_data = f's3://{bucket}/model-artifacts/orchestrated-training-1761669076/output/model.tar.gz'
source_dir = f's3://{bucket}/training_code.tar.gz'

boto_session = boto3.Session(region_name=region)
sagemaker_session = Session(boto_session=boto_session)

print(f"Creating SKLearnModel with inference script...")
sklearn_model = SKLearnModel(
    model_data=model_data,
    role=role,
    entry_point='inference.py',
    source_dir=source_dir,
    framework_version='1.2-1',
    py_version='py3',
    sagemaker_session=sagemaker_session
)

print(f"Creating batch transformer...")
transformer = sklearn_model.transformer(
    instance_count=1,
    instance_type='ml.m5.large',
    output_path=f's3://{bucket}/inference-results/',
    accept='application/json'
)

job_name = f'json-test-{int(time.time())}'
print(f"Starting batch transform job: {job_name}")

transformer.transform(
    data=f's3://{bucket}/inference-data/inference_data.csv',
    content_type='text/csv',
    split_type='Line',
    job_name=job_name,
    wait=False
)

print(f"\n✅ Batch transform job started: {job_name}")
print(f"Monitor: aws sagemaker describe-transform-job --transform-job-name {job_name} --region {region}")
print(f"Logs: aws logs tail /aws/sagemaker/TransformJobs --region {region} --follow --filter-pattern '{job_name}'")

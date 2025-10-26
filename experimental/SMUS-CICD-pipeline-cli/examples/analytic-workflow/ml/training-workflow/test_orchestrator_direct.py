#!/usr/bin/env python3

import boto3
import time
import json

def test_sagemaker_distribution_orchestrator():
    """Test SageMaker Distribution image with orchestration code using direct SageMaker API"""
    
    print("🧪 Testing SageMaker Distribution Image with Orchestration Code")
    
    # Configuration
    role_arn = "arn:aws:iam::058264284947:role/service-role/AmazonSageMaker-ExecutionRole-20241115T121975"
    bucket = "demo-bucket-smus-ml-us-west-2"
    region = "us-west-2"
    
    # Use SageMaker Distribution image with pre-installed SDK
    training_image = "542918446943.dkr.ecr.us-west-2.amazonaws.com/sagemaker-distribution-prod:1-cpu"
    
    sagemaker_client = boto3.client('sagemaker', region_name=region)
    
    # Create training job directly using SageMaker API
    job_name = f"test-orchestrator-{int(time.time())}"
    
    training_job_config = {
        'TrainingJobName': job_name,
        'AlgorithmSpecification': {
            'TrainingImage': training_image,
            'TrainingInputMode': 'File'
        },
        'RoleArn': role_arn,
        'InputDataConfig': [
            {
                'ChannelName': 'training',
                'DataSource': {
                    'S3DataSource': {
                        'S3DataType': 'S3Prefix',
                        'S3Uri': f's3://{bucket}/training-data/',
                        'S3DataDistributionType': 'FullyReplicated'
                    }
                },
                'ContentType': 'text/csv',
                'InputMode': 'File'
            }
        ],
        'OutputDataConfig': {
            'S3OutputPath': f's3://{bucket}/orchestrator-test-results/'
        },
        'ResourceConfig': {
            'InstanceType': 'ml.m5.large',
            'InstanceCount': 1,
            'VolumeSizeInGB': 30
        },
        'StoppingCondition': {
            'MaxRuntimeInSeconds': 3600
        },
        'HyperParameters': {
            'sagemaker_program': 'sagemaker_ml_orchestrator.py',
            'sagemaker_submit_directory': f's3://{bucket}/orchestrator_code.tar.gz'
        },
        'Environment': {
            'MLFLOW_TRACKING_SERVER_ARN': 'arn:aws:sagemaker:us-east-1:058264284947:mlflow-tracking-server/wine-classification-mlflow-v2'
        }
    }
    
    print(f"Creating training job: {job_name}")
    print(f"Using image: {training_image}")
    print(f"Using orchestrator code: s3://{bucket}/orchestrator_code.tar.gz")
    
    try:
        response = sagemaker_client.create_training_job(**training_job_config)
        print(f"✅ Training job created successfully!")
        print(f"Training Job ARN: {response['TrainingJobArn']}")
        
        # Monitor job status
        print("\n👀 Monitoring training job...")
        for i in range(30):  # Monitor for up to 30 minutes
            status_response = sagemaker_client.describe_training_job(TrainingJobName=job_name)
            status = status_response['TrainingJobStatus']
            secondary_status = status_response.get('SecondaryStatus', 'Unknown')
            
            print(f"[{i+1}] Status: {status} - {secondary_status}")
            
            if status == 'Completed':
                print("🎉 Training job completed successfully!")
                print(f"Model artifacts: {status_response['ModelArtifacts']['S3ModelArtifacts']}")
                return True
            elif status == 'Failed':
                print(f"❌ Training job failed: {status_response.get('FailureReason', 'Unknown error')}")
                return False
            elif status in ['Stopped', 'Stopping']:
                print(f"⚠️ Training job stopped: {status}")
                return False
            
            time.sleep(60)  # Wait 1 minute between checks
        
        print("⏰ Monitoring timeout reached")
        return False
        
    except Exception as e:
        print(f"❌ Failed to create training job: {e}")
        return False

def main():
    success = test_sagemaker_distribution_orchestrator()
    if success:
        print("\n✅ SageMaker Distribution image orchestration test PASSED!")
        print("✅ Ready to use in SMUS workflow")
    else:
        print("\n❌ SageMaker Distribution image orchestration test FAILED!")
        print("❌ Need to debug before using in workflow")

if __name__ == "__main__":
    main()

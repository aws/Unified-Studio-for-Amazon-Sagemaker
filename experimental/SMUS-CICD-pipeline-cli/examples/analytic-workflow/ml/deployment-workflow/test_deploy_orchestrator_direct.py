#!/usr/bin/env python3

import boto3
import time
import json

def test_deployment_orchestrator():
    """Test deployment orchestrator using direct SageMaker API"""
    
    print("🧪 Testing Deployment Orchestrator")
    
    # Configuration
    role_arn = "arn:aws:iam::058264284947:role/service-role/AmazonSageMaker-ExecutionRole-20241115T121975"
    bucket = "demo-bucket-smus-ml-us-west-2"
    region = "us-west-2"
    
    # Use standard scikit-learn image
    training_image = "246618743249.dkr.ecr.us-west-2.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3"
    
    sagemaker_client = boto3.client('sagemaker', region_name=region)
    
    # Create training job to run deployment orchestrator
    job_name = f"test-deploy-orchestrator-{int(time.time())}"
    
    training_job_config = {
        'TrainingJobName': job_name,
        'AlgorithmSpecification': {
            'TrainingImage': training_image,
            'TrainingInputMode': 'File'
        },
        'RoleArn': role_arn,
        'HyperParameters': {
            'sagemaker_program': 'sagemaker_deploy_orchestrator.py',
            'sagemaker_submit_directory': f's3://{bucket}/deploy_orchestrator_code.tar.gz'
        },
        'OutputDataConfig': {
            'S3OutputPath': f's3://{bucket}/deployment-test-results/'
        },
        'ResourceConfig': {
            'InstanceType': 'ml.m5.large',
            'InstanceCount': 1,
            'VolumeSizeInGB': 30
        },
        'StoppingCondition': {
            'MaxRuntimeInSeconds': 3600
        }
    }
    
    print(f"Creating deployment orchestrator job: {job_name}")
    print(f"Using image: {training_image}")
    print(f"Using orchestrator code: s3://{bucket}/deploy_orchestrator_code.tar.gz")
    
    try:
        response = sagemaker_client.create_training_job(**training_job_config)
        print(f"✅ Deployment orchestrator job created successfully!")
        print(f"Training Job ARN: {response['TrainingJobArn']}")
        
        # Monitor job status
        print("\n👀 Monitoring deployment orchestrator job...")
        for i in range(30):  # Monitor for up to 30 minutes
            status_response = sagemaker_client.describe_training_job(TrainingJobName=job_name)
            status = status_response['TrainingJobStatus']
            secondary_status = status_response.get('SecondaryStatus', 'Unknown')
            
            print(f"[{i+1}] Status: {status} - {secondary_status}")
            
            if status == 'Completed':
                print("🎉 Deployment orchestrator job completed successfully!")
                print(f"Results: {status_response['ModelArtifacts']['S3ModelArtifacts']}")
                return True
            elif status == 'Failed':
                print(f"❌ Deployment orchestrator job failed: {status_response.get('FailureReason', 'Unknown error')}")
                return False
            elif status in ['Stopped', 'Stopping']:
                print(f"⚠️ Deployment orchestrator job stopped: {status}")
                return False
            
            time.sleep(60)  # Wait 1 minute between checks
        
        print("⏰ Monitoring timeout reached")
        return False
        
    except Exception as e:
        print(f"❌ Failed to create deployment orchestrator job: {e}")
        return False

def main():
    success = test_deployment_orchestrator()
    if success:
        print("\n✅ Deployment orchestrator test PASSED!")
        print("✅ Ready to use in SMUS workflow")
    else:
        print("\n❌ Deployment orchestrator test FAILED!")
        print("❌ Need to debug before using in workflow")

if __name__ == "__main__":
    main()

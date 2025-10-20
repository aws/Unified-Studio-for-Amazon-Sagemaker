#!/usr/bin/env python3

import boto3
import json
import time
import os

def create_sagemaker_endpoint():
    """Create SageMaker endpoint from the champion model"""
    
    print("=== Creating SageMaker Endpoint ===")
    
    # Configuration
    region = 'us-east-1'
    role_arn = 'arn:aws:iam::058264284947:role/service-role/AmazonSageMaker-ExecutionRole-20241115T121975'
    
    # Get model data from config
    config_file = 'config/realistic_experiment.json'
    if not os.path.exists(config_file):
        print("❌ No model config found. Run training first.")
        return
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    model_data_url = config['model_data']
    timestamp = str(int(time.time()))
    
    model_name = f"realistic-classifier-endpoint-{timestamp}"
    endpoint_config_name = f"realistic-classifier-config-{timestamp}"
    endpoint_name = f"realistic-classifier-endpoint-{timestamp}"
    
    sagemaker = boto3.client('sagemaker', region_name=region)
    
    try:
        # Step 1: Create Model
        print(f"Creating SageMaker model: {model_name}")
        sagemaker.create_model(
            ModelName=model_name,
            PrimaryContainer={
                'Image': '683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3',
                'ModelDataUrl': model_data_url,
                'Environment': {
                    'SAGEMAKER_PROGRAM': 'inference.py',
                    'SAGEMAKER_SUBMIT_DIRECTORY': '/opt/ml/code'
                }
            },
            ExecutionRoleArn=role_arn
        )
        print("✅ Model created")
        
        # Step 2: Create Endpoint Configuration
        print(f"Creating endpoint config: {endpoint_config_name}")
        sagemaker.create_endpoint_config(
            EndpointConfigName=endpoint_config_name,
            ProductionVariants=[{
                'VariantName': 'primary',
                'ModelName': model_name,
                'InitialInstanceCount': 1,
                'InstanceType': 'ml.m5.large',
                'InitialVariantWeight': 1.0
            }]
        )
        print("✅ Endpoint config created")
        
        # Step 3: Create Endpoint
        print(f"Creating endpoint: {endpoint_name}")
        sagemaker.create_endpoint(
            EndpointName=endpoint_name,
            EndpointConfigName=endpoint_config_name
        )
        print("✅ Endpoint creation started")
        
        # Wait for endpoint to be in service
        print("Waiting for endpoint to be InService...")
        waiter = sagemaker.get_waiter('endpoint_in_service')
        waiter.wait(
            EndpointName=endpoint_name,
            WaiterConfig={
                'Delay': 30,
                'MaxAttempts': 20
            }
        )
        
        print("✅ Endpoint is InService!")
        
        # Save endpoint info
        endpoint_info = {
            'endpoint_name': endpoint_name,
            'endpoint_config_name': endpoint_config_name,
            'model_name': model_name,
            'model_data_url': model_data_url,
            'region': region,
            'created_at': timestamp
        }
        
        os.makedirs('config', exist_ok=True)
        with open('config/endpoint_info.json', 'w') as f:
            json.dump(endpoint_info, f, indent=2)
        
        print(f"Endpoint info saved to config/endpoint_info.json")
        print(f"🎯 Endpoint ready for inference: {endpoint_name}")
        
        return endpoint_name
        
    except Exception as e:
        print(f"❌ Endpoint creation failed: {e}")
        raise

if __name__ == "__main__":
    endpoint_name = create_sagemaker_endpoint()
    print(f"✅ Endpoint created successfully: {endpoint_name}")

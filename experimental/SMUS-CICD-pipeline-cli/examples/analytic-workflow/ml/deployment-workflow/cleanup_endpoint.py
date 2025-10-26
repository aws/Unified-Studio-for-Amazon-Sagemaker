#!/usr/bin/env python3

import boto3
import json
import os

def cleanup_sagemaker_endpoint():
    """Clean up SageMaker endpoint resources"""
    
    print("=== Cleaning Up SageMaker Resources ===")
    
    # Load endpoint info
    config_file = 'config/endpoint_info.json'
    if not os.path.exists(config_file):
        print("❌ No endpoint config found. Nothing to clean up.")
        return
    
    with open(config_file, 'r') as f:
        endpoint_info = json.load(f)
    
    endpoint_name = endpoint_info['endpoint_name']
    endpoint_config_name = endpoint_info['endpoint_config_name']
    model_name = endpoint_info['model_name']
    region = endpoint_info['region']
    
    sagemaker = boto3.client('sagemaker', region_name=region)
    
    try:
        # Delete endpoint
        print(f"Deleting endpoint: {endpoint_name}")
        sagemaker.delete_endpoint(EndpointName=endpoint_name)
        print("✅ Endpoint deleted")
        
        # Delete endpoint config
        print(f"Deleting endpoint config: {endpoint_config_name}")
        sagemaker.delete_endpoint_config(EndpointConfigName=endpoint_config_name)
        print("✅ Endpoint config deleted")
        
        # Delete model
        print(f"Deleting model: {model_name}")
        sagemaker.delete_model(ModelName=model_name)
        print("✅ Model deleted")
        
        # Remove config file
        os.remove(config_file)
        print("✅ Config file removed")
        
        print("✅ All resources cleaned up successfully!")
        
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")

if __name__ == "__main__":
    cleanup_sagemaker_endpoint()

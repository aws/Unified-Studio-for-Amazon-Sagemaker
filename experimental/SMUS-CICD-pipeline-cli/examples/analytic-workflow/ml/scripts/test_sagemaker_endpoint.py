#!/usr/bin/env python3

import boto3
import json
import numpy as np
import os
from sklearn.datasets import make_classification

def test_sagemaker_endpoint():
    """Test the deployed SageMaker endpoint"""
    
    print("=== Testing SageMaker Endpoint ===")
    
    # Load endpoint info
    config_file = 'config/endpoint_info.json'
    if not os.path.exists(config_file):
        print("❌ No endpoint config found. Create endpoint first.")
        return
    
    with open(config_file, 'r') as f:
        endpoint_info = json.load(f)
    
    endpoint_name = endpoint_info['endpoint_name']
    region = endpoint_info['region']
    
    print(f"Testing endpoint: {endpoint_name}")
    
    # Create test data
    print("Creating test data...")
    X, _ = make_classification(
        n_samples=5, n_features=20, n_classes=3, 
        n_informative=12, random_state=42
    )
    
    # Convert to CSV format (no headers)
    test_rows = []
    for row in X:
        test_rows.append(','.join(map(str, row)))
    
    payload = '\n'.join(test_rows)
    print(f"Test data: {len(test_rows)} samples")
    
    # Test endpoint
    runtime = boto3.client('sagemaker-runtime', region_name=region)
    
    try:
        print("Invoking endpoint...")
        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType='text/csv',
            Body=payload
        )
        
        # Parse response
        result = response['Body'].read().decode('utf-8')
        predictions = result.strip().split('\n')
        
        print("✅ Endpoint test successful!")
        print(f"Predictions: {predictions}")
        print(f"Unique classes: {set(predictions)}")
        
        # Save test results
        test_results = {
            'endpoint_name': endpoint_name,
            'test_samples': len(predictions),
            'predictions': predictions,
            'unique_classes': list(set(predictions)),
            'status': 'success'
        }
        
        with open('config/endpoint_test_results.json', 'w') as f:
            json.dump(test_results, f, indent=2)
        
        print("Test results saved to config/endpoint_test_results.json")
        return True
        
    except Exception as e:
        print(f"❌ Endpoint test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_sagemaker_endpoint()
    if success:
        print("✅ Endpoint is working correctly!")
    else:
        print("❌ Endpoint test failed!")

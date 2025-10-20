#!/usr/bin/env python3
"""
Airflow task functions for ML workflow
"""

import boto3
import json
import numpy as np
import pandas as pd
from sklearn.datasets import make_classification


def tag_champion_model_task(model_name, tracking_server_arn, **context):
    """Tag the best model version as 'champion'"""
    import mlflow
    
    mlflow.set_tracking_uri(tracking_server_arn)
    client = mlflow.MlflowClient()
    
    print(f"Finding best model version for: {model_name}")
    
    # Get all versions of the model
    versions = client.search_model_versions(f"name='{model_name}'")
    
    if not versions:
        raise ValueError(f"No versions found for model: {model_name}")
    
    # Find the latest version
    latest_version = max(versions, key=lambda x: int(x.version))
    
    print(f"Latest version: {latest_version.version}")
    
    # Set alias to "champion"
    client.set_registered_model_alias(
        name=model_name,
        alias="champion",
        version=latest_version.version
    )
    
    print(f"✅ Tagged version {latest_version.version} as 'champion'")
    return f"models:/{model_name}@champion"


def test_endpoint_task(endpoint_name, region_name, **context):
    """Test the deployed SageMaker endpoint"""
    
    # Create test data
    print("Creating test data for endpoint testing...")
    X, _ = make_classification(
        n_samples=5, n_features=20, n_classes=3, 
        n_informative=12, random_state=42
    )
    
    # Convert to CSV format for SageMaker
    test_data = []
    for row in X:
        test_data.append(','.join(map(str, row)))
    
    payload = '\n'.join(test_data)
    
    # Test the endpoint
    runtime = boto3.client('sagemaker-runtime', region_name=region_name)
    
    try:
        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType='text/csv',
            Body=payload
        )
        
        result = response['Body'].read().decode('utf-8')
        predictions = result.strip().split('\n')
        
        print(f"✅ Endpoint test successful!")
        print(f"Predictions: {predictions}")
        print(f"Number of predictions: {len(predictions)}")
        
        return {
            'endpoint_name': endpoint_name,
            'test_samples': len(predictions),
            'predictions': predictions[:3],  # First 3 predictions
            'status': 'success'
        }
        
    except Exception as e:
        print(f"❌ Endpoint test failed: {e}")
        raise


def create_test_data_task(bucket_name, **context):
    """Create test data for batch inference"""
    
    print("Creating test data for batch inference...")
    
    # Create synthetic test data
    X, _ = make_classification(
        n_samples=100, n_features=20, n_classes=3, 
        n_informative=12, random_state=123
    )
    
    # Create DataFrame
    feature_names = [f'feature_{i:02d}' for i in range(20)]
    df = pd.DataFrame(X, columns=feature_names)
    
    # Save to CSV (no headers for SageMaker)
    csv_content = df.to_csv(index=False, header=False)
    
    # Upload to S3
    s3_client = boto3.client('s3')
    key = 'batch-inference/input/airflow_test_data.csv'
    
    s3_client.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=csv_content
    )
    
    s3_uri = f's3://{bucket_name}/{key}'
    print(f"✅ Test data uploaded to: {s3_uri}")
    
    return {
        'test_data_uri': s3_uri,
        'sample_count': len(df),
        'feature_count': len(feature_names)
    }


def validate_batch_results_task(bucket_name, output_prefix, **context):
    """Validate batch inference results"""
    
    s3_client = boto3.client('s3')
    
    # List output files
    response = s3_client.list_objects_v2(
        Bucket=bucket_name,
        Prefix=output_prefix
    )
    
    if 'Contents' not in response:
        raise ValueError("No batch inference results found")
    
    # Get the first result file
    result_key = response['Contents'][0]['Key']
    
    # Download and read results
    obj = s3_client.get_object(Bucket=bucket_name, Key=result_key)
    results = obj['Body'].read().decode('utf-8')
    
    predictions = results.strip().split('\n')
    unique_classes = set()
    
    for pred in predictions:
        if pred.strip():
            unique_classes.add(pred.strip())
    
    print(f"✅ Batch inference validation successful!")
    print(f"Total predictions: {len(predictions)}")
    print(f"Unique classes: {sorted(unique_classes)}")
    print(f"Sample predictions: {predictions[:5]}")
    
    return {
        'total_predictions': len(predictions),
        'unique_classes': sorted(unique_classes),
        'sample_predictions': predictions[:5],
        'result_s3_key': result_key
    }


def cleanup_resources_task(endpoint_name, model_name, endpoint_config_name, region_name, **context):
    """Clean up SageMaker resources"""
    
    sagemaker = boto3.client('sagemaker', region_name=region_name)
    
    try:
        # Delete endpoint
        print(f"Deleting endpoint: {endpoint_name}")
        sagemaker.delete_endpoint(EndpointName=endpoint_name)
        
        # Delete endpoint config
        print(f"Deleting endpoint config: {endpoint_config_name}")
        sagemaker.delete_endpoint_config(EndpointConfigName=endpoint_config_name)
        
        # Delete model
        print(f"Deleting model: {model_name}")
        sagemaker.delete_model(ModelName=model_name)
        
        print("✅ Resources cleaned up successfully")
        
        return {
            'endpoint_deleted': endpoint_name,
            'config_deleted': endpoint_config_name,
            'model_deleted': model_name,
            'status': 'success'
        }
        
    except Exception as e:
        print(f"⚠️ Cleanup warning: {e}")
        return {
            'status': 'partial_success',
            'error': str(e)
        }

#!/usr/bin/env python3

import boto3
import mlflow.pyfunc
import pandas as pd
import numpy as np
import time
import os
from sklearn.datasets import make_classification

def create_test_data():
    """Create test data for inference"""
    print("Creating test data...")
    X, _ = make_classification(
        n_samples=100, n_features=20, n_classes=3, 
        n_informative=12, random_state=42
    )
    
    # Create DataFrame with feature names
    feature_names = [f'feature_{i:02d}' for i in range(20)]
    df = pd.DataFrame(X, columns=feature_names)
    
    return df

def run_mlflow_inference():
    """Run inference using MLflow model registry"""
    
    # MLflow setup
    tracking_server_arn = "arn:aws:sagemaker:us-east-1:058264284947:mlflow-tracking-server/wine-classification-mlflow-v2"
    mlflow.set_tracking_uri(tracking_server_arn)
    
    model_name = "realistic-classifier-v1"
    alias = "champion"
    
    print(f"Loading champion model: {model_name}@{alias}")
    
    try:
        # Load the champion model
        champion_model = mlflow.pyfunc.load_model(f"models:/{model_name}@{alias}")
        
        # Create test data
        test_data = create_test_data()
        
        print(f"Running inference on {len(test_data)} samples...")
        
        # Run predictions
        predictions = champion_model.predict(test_data)
        
        print("✅ Inference completed!")
        print(f"Predictions shape: {predictions.shape}")
        print(f"Unique predictions: {np.unique(predictions)}")
        print(f"Sample predictions: {predictions[:10]}")
        
        return predictions
        
    except Exception as e:
        print(f"❌ MLflow inference failed: {e}")
        return None

def run_sagemaker_batch_transform():
    """Run SageMaker Batch Transform job"""
    
    print("Setting up SageMaker Batch Transform...")
    
    # Get account info
    sts_client = boto3.client('sts')
    account_id = sts_client.get_caller_identity()['Account']
    region = 'us-east-1'
    bucket_name = f"sagemaker-ml-workflow-{account_id}-{region}"
    
    # Create test data and upload to S3
    test_data = create_test_data()
    
    # Save test data to CSV
    test_file = '/tmp/test_data.csv'
    test_data.to_csv(test_file, index=False, header=False)
    
    # Upload to S3
    s3_client = boto3.client('s3')
    input_key = "batch-inference/input/test_data.csv"
    s3_client.upload_file(test_file, bucket_name, input_key)
    
    input_path = f"s3://{bucket_name}/{input_key}"
    output_path = f"s3://{bucket_name}/batch-inference/output/"
    
    print(f"Input data: {input_path}")
    print(f"Output path: {output_path}")
    
    # Get the latest model from our training job
    config_file = 'config/realistic_experiment.json'
    if os.path.exists(config_file):
        import json
        with open(config_file, 'r') as f:
            config = json.load(f)
        model_data = config['model_data']
    else:
        print("❌ No model config found. Run training first.")
        return
    
    # Create SageMaker model
    sagemaker_client = boto3.client('sagemaker')
    role = "arn:aws:iam::058264284947:role/service-role/AmazonSageMaker-ExecutionRole-20241115T121975"
    
    model_name = f"realistic-classifier-{int(time.time())}"
    
    try:
        sagemaker_client.create_model(
            ModelName=model_name,
            PrimaryContainer={
                'Image': '683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3',
                'ModelDataUrl': model_data,
                'Environment': {
                    'SAGEMAKER_PROGRAM': 'inference.py',
                    'SAGEMAKER_SUBMIT_DIRECTORY': '/opt/ml/code'
                }
            },
            ExecutionRoleArn=role
        )
        
        # Create batch transform job
        transform_job_name = f"batch-inference-{int(time.time())}"
        
        sagemaker_client.create_transform_job(
            TransformJobName=transform_job_name,
            ModelName=model_name,
            TransformInput={
                'DataSource': {
                    'S3DataSource': {
                        'S3DataType': 'S3Prefix',
                        'S3Uri': input_path
                    }
                },
                'ContentType': 'text/csv',
                'SplitType': 'Line'
            },
            TransformOutput={
                'S3OutputPath': output_path,
                'Accept': 'text/csv'
            },
            TransformResources={
                'InstanceType': 'ml.m5.large',
                'InstanceCount': 1
            }
        )
        
        print(f"✅ Batch transform job started: {transform_job_name}")
        print(f"Monitor at: https://console.aws.amazon.com/sagemaker/home?region={region}#/transform-jobs/{transform_job_name}")
        
    except Exception as e:
        print(f"❌ Batch transform failed: {e}")

def main():
    print("=== Running Batch Inference ===")
    
    # Try MLflow inference first
    predictions = run_mlflow_inference()
    
    if predictions is not None:
        print("\n=== Setting up SageMaker Batch Transform ===")
        run_sagemaker_batch_transform()
    else:
        print("Skipping SageMaker batch transform due to MLflow error")

if __name__ == "__main__":
    main()

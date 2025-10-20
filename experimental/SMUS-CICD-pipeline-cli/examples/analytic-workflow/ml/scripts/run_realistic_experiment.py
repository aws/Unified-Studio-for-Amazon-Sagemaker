#!/usr/bin/env python3

import boto3
import json
import time
import os

import sagemaker
from sagemaker.sklearn.estimator import SKLearn
from sagemaker.inputs import TrainingInput

def run_realistic_model_experiment():
    """Run realistic model comparison experiment with challenging dataset"""
    
    print("=== Running Realistic Model Comparison Experiment ===")
    
    # MLflow configuration
    tracking_server_arn = "arn:aws:sagemaker:us-east-1:058264284947:mlflow-tracking-server/wine-classification-mlflow-v2"
    experiment_name = "realistic-model-comparison-experiment"
    
    print(f"MLflow Tracking Server ARN: {tracking_server_arn}")
    print(f"MLflow Experiment: {experiment_name}")
    
    # Get account info
    sts_client = boto3.client('sts')
    account_id = sts_client.get_caller_identity()['Account']
    region = boto3.Session().region_name or 'us-east-1'
    bucket_name = f"sagemaker-ml-workflow-{account_id}-{region}"
    
    # Get execution role
    role = "arn:aws:iam::058264284947:role/service-role/AmazonSageMaker-ExecutionRole-20241115T121975"
    print(f"Using execution role: {role}")
    
    # Create SageMaker session
    sagemaker_session = sagemaker.Session()
    
    # Hyperparameters for more realistic training
    hyperparameters = {
        'n-estimators': 100,
        'max-depth': 6,  # Reduced to prevent overfitting
        'random-state': 42
    }
    
    # Create SKLearn estimator
    sklearn_estimator = SKLearn(
        entry_point='sagemaker_train_realistic.py',
        source_dir='src',
        framework_version='1.2-1',
        py_version='py3',
        instance_type='ml.m5.large',
        instance_count=1,
        role=role,
        output_path=f"s3://{bucket_name}/realistic-models/",
        sagemaker_session=sagemaker_session,
        environment={"MLFLOW_TRACKING_SERVER_ARN": tracking_server_arn},
        hyperparameters=hyperparameters
    )
    
    # Start training job (no input data needed - synthetic dataset)
    job_name = f"realistic-model-comparison-{int(time.time())}"
    print(f"Starting realistic model comparison: {job_name}")
    
    sklearn_estimator.fit(job_name=job_name)
    
    print(f"✅ Realistic model comparison completed: {job_name}")
    print(f"Model artifacts: {sklearn_estimator.model_data}")
    
    # Save configuration
    config = {
        "job_name": job_name,
        "model_data": sklearn_estimator.model_data,
        "bucket_name": bucket_name,
        "mlflow_tracking_server_arn": tracking_server_arn,
        "mlflow_experiment": experiment_name,
        "region": region,
        "experiment_type": "realistic_model_comparison"
    }
    
    os.makedirs('config', exist_ok=True)
    with open('config/realistic_experiment.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Configuration saved to config/realistic_experiment.json")
    
    return sklearn_estimator, job_name

def main():
    try:
        estimator, job_name = run_realistic_model_experiment()
        print("✅ Realistic model comparison experiment completed successfully!")
        print(f"✅ Training Job: {job_name}")
        print("✅ Check your MLflow tracking server for:")
        print("   - 4 different models compared (RF, GB, LR, SVM)")
        print("   - Cross-validation results")
        print("   - Comprehensive performance plots")
        print("   - More realistic accuracy scores!")
        
    except Exception as e:
        print(f"❌ Experiment failed: {e}")
        raise e

if __name__ == "__main__":
    main()

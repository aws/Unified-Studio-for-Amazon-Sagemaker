#!/usr/bin/env python3
"""
Standalone deployment test - iterate fast locally
Try SKLearnModel approach instead of ModelBuilder
"""

import boto3
import sagemaker
from sagemaker.sklearn import SKLearnModel
import mlflow
from mlflow import MlflowClient
import numpy as np
import tempfile
import tarfile
import os

# Configuration from successful training
MLFLOW_ARN = "arn:aws:sagemaker:us-east-2:198737698272:mlflow-tracking-server/smus-integration-mlflow-use2"
MODEL_NAME = "realistic-classifier-v1"
REGION = "us-east-2"
INSTANCE_TYPE = "ml.m5.large"
SKLEARN_VERSION = "1.2-1"  # Match training version

def get_role():
    """Get IAM role from SageMaker session"""
    session = sagemaker.Session()
    return session.get_caller_identity_arn().replace('assumed-role', 'role').split('/')[0] + '/SMUSCICDTestRole'

def test_deployment():
    print("=" * 80)
    print("🔍 LOCAL DEPLOYMENT TEST - SKLearnModel Approach")
    print("=" * 80)
    
    # Get role and session
    session = sagemaker.Session()
    role = get_role()
    bucket = session.default_bucket()
    
    print(f"\n📋 Configuration:")
    print(f"   MLflow ARN: {MLFLOW_ARN}")
    print(f"   Model Name: {MODEL_NAME}")
    print(f"   Region: {REGION}")
    print(f"   Role: {role}")
    print(f"   Bucket: {bucket}")
    
    # 1. Connect to MLflow
    print(f"\n1️⃣ Connecting to MLflow...")
    mlflow.set_tracking_uri(MLFLOW_ARN)
    client = MlflowClient()
    print("   ✅ Connected")
    
    # 2. Get model
    print(f"\n2️⃣ Getting registered model...")
    registered_model = client.get_registered_model(name=MODEL_NAME)
    latest_version = registered_model.latest_versions[0]
    
    print(f"   Model version: {latest_version.version}")
    print(f"   Source: {latest_version.source}")
    
    # 3. Get S3 path from model source
    print(f"\n3️⃣ Getting model artifacts from S3...")
    # Source format: models:/m-<id>
    model_id = latest_version.source.split("/")[-1]
    
    # Get run to find S3 bucket
    run = client.get_run(latest_version.run_id)
    artifact_uri = run.info.artifact_uri
    bucket_and_prefix = artifact_uri.replace("s3://", "").split("/", 1)
    bucket_name = bucket_and_prefix[0]
    base_prefix = bucket_and_prefix[1] if len(bucket_and_prefix) > 1 else ""
    base_parts = base_prefix.split("/")
    mlflow_base = "/".join(base_parts[:2])  # mlflow/0
    
    model_s3_prefix = f"{mlflow_base}/models/{model_id}/artifacts/"
    print(f"   S3 location: s3://{bucket_name}/{model_s3_prefix}")
    
    # 4. Download and package model with inference script
    print(f"\n4️⃣ Downloading and packaging model...")
    s3_client = boto3.client('s3', region_name=REGION)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Download model.pkl
        model_pkl_key = f"{model_s3_prefix}model.pkl"
        local_model_path = os.path.join(tmpdir, "model.pkl")
        print(f"   Downloading model.pkl...")
        s3_client.download_file(bucket_name, model_pkl_key, local_model_path)
        
        # Create code directory with inference script
        code_dir = os.path.join(tmpdir, "code")
        os.makedirs(code_dir)
        
        # Write inference.py
        inference_script = '''import joblib
import os

def model_fn(model_dir):
    """Load model from model_dir"""
    model_path = os.path.join(model_dir, "model.pkl")
    model = joblib.load(model_path)
    return model
'''
        with open(os.path.join(code_dir, "inference.py"), 'w') as f:
            f.write(inference_script)
        
        print(f"   Created inference.py")
        
        # Package into model.tar.gz
        tar_path = os.path.join(tmpdir, "model.tar.gz")
        print(f"   Creating model.tar.gz...")
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(local_model_path, arcname="model.pkl")
            tar.add(code_dir, arcname="code")
        
        # Upload to S3
        model_artifact_key = f"mlflow-models/{MODEL_NAME}/model.tar.gz"
        model_s3_uri = f"s3://{bucket}/{model_artifact_key}"
        print(f"   Uploading to {model_s3_uri}...")
        s3_client.upload_file(tar_path, bucket, model_artifact_key)
    
    print(f"   ✅ Model packaged at: {model_s3_uri}")
    
    # 5. Create SKLearnModel
    print(f"\n5️⃣ Creating SKLearnModel...")
    sklearn_model = SKLearnModel(
        model_data=model_s3_uri,
        role=role,
        framework_version=SKLEARN_VERSION,
        py_version="py3",
        sagemaker_session=session
    )
    print("   ✅ SKLearnModel created")
    
    # 6. Deploy (skip for now - test packaging first)
    print(f"\n6️⃣ Deploying to endpoint (SKIPPED - test packaging)")
    print("   Model packaged with inference.py")
    print("   Ready for deployment")
    
    print("\n" + "=" * 80)
    print("✅ ALL STEPS COMPLETED SUCCESSFULLY")
    print("=" * 80)
    return True

if __name__ == "__main__":
    import sys
    success = test_deployment()
    sys.exit(0 if success else 1)

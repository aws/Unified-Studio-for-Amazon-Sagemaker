#!/usr/bin/env python3

import boto3
import joblib
import pandas as pd
import numpy as np
import tempfile
import tarfile
import os
import json
from sklearn.datasets import make_classification
from sklearn.preprocessing import StandardScaler

def create_test_data():
    """Create test data matching training format"""
    print("Creating test data...")
    X, _ = make_classification(
        n_samples=50, n_features=20, n_classes=3, 
        n_informative=12, random_state=123  # Different seed for variety
    )
    
    feature_names = [f'feature_{i:02d}' for i in range(20)]
    df = pd.DataFrame(X, columns=feature_names)
    
    print(f"Test data shape: {df.shape}")
    return df

def download_model_from_s3(s3_uri):
    """Download and extract model from S3"""
    
    print(f"Downloading model from: {s3_uri}")
    
    # Parse S3 URI
    parts = s3_uri.replace('s3://', '').split('/')
    bucket = parts[0]
    key = '/'.join(parts[1:])
    
    s3_client = boto3.client('s3')
    
    # Download to temporary file
    with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp_file:
        s3_client.download_file(bucket, key, tmp_file.name)
        
        # Extract tar.gz
        extract_dir = tempfile.mkdtemp()
        with tarfile.open(tmp_file.name, 'r:gz') as tar:
            tar.extractall(extract_dir)
        
        print(f"Model extracted to: {extract_dir}")
        
        # List contents
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                file_path = os.path.join(root, file)
                print(f"  📄 {file_path}")
        
        return extract_dir

def load_and_predict(model_dir, test_data):
    """Load model and run predictions"""
    
    model_path = os.path.join(model_dir, 'model.joblib')
    scaler_path = os.path.join(model_dir, 'scaler.joblib')
    metadata_path = os.path.join(model_dir, 'metadata.json')
    
    if not os.path.exists(model_path):
        print(f"❌ Model file not found: {model_path}")
        return None
    
    print(f"Loading model from: {model_path}")
    model = joblib.load(model_path)
    
    # Load metadata if available
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        print(f"Model metadata: {metadata.get('best_model', 'unknown')}")
    
    # Apply scaling if scaler exists (for SVM/LogisticRegression)
    X_test = test_data.values
    if os.path.exists(scaler_path):
        print("Applying feature scaling...")
        scaler = joblib.load(scaler_path)
        X_test = scaler.transform(X_test)
    
    # Run predictions
    print("Running predictions...")
    predictions = model.predict(X_test)
    
    # Get probabilities if available
    try:
        probabilities = model.predict_proba(X_test)
        print(f"Predictions shape: {predictions.shape}")
        print(f"Probabilities shape: {probabilities.shape}")
    except:
        probabilities = None
        print(f"Predictions shape: {predictions.shape}")
    
    print(f"Unique predictions: {np.unique(predictions)}")
    print(f"Sample predictions: {predictions[:10]}")
    
    if probabilities is not None:
        print(f"Sample probabilities:")
        for i in range(min(5, len(probabilities))):
            print(f"  Sample {i}: {probabilities[i]}")
    
    return predictions, probabilities

def run_s3_inference():
    """Main function to run S3-based inference"""
    
    print("=== S3 Model Inference ===")
    
    # Get model URI from config
    config_file = 'config/realistic_experiment.json'
    if not os.path.exists(config_file):
        print(f"❌ Config file not found: {config_file}")
        print("Run the realistic experiment first!")
        return
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    model_uri = config.get('model_data')
    if not model_uri:
        print("❌ No model_data found in config")
        return
    
    print(f"Using model: {model_uri}")
    
    try:
        # Download and extract model
        model_dir = download_model_from_s3(model_uri)
        
        # Create test data
        test_data = create_test_data()
        
        # Load model and predict
        results = load_and_predict(model_dir, test_data)
        
        if results:
            predictions, probabilities = results
            print("✅ S3 inference completed successfully!")
            
            # Save results
            results_df = test_data.copy()
            results_df['prediction'] = predictions
            
            if probabilities is not None:
                for i in range(probabilities.shape[1]):
                    results_df[f'prob_class_{i}'] = probabilities[:, i]
            
            output_file = 'inference_results.csv'
            results_df.to_csv(output_file, index=False)
            print(f"Results saved to: {output_file}")
            
        else:
            print("❌ Inference failed")
            
    except Exception as e:
        print(f"❌ Error during S3 inference: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_s3_inference()

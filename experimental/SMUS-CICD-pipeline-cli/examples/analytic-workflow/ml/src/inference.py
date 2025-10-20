#!/usr/bin/env python3

import joblib
import numpy as np
import pandas as pd
import argparse
import os

def load_model(model_dir):
    """Load trained model and feature names"""
    model_path = os.path.join(model_dir, "wine_classifier.joblib")
    feature_names_path = os.path.join(model_dir, "feature_names.txt")
    
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found at {model_path}")
    
    model = joblib.load(model_path)
    
    # Load feature names
    feature_names = []
    if os.path.exists(feature_names_path):
        with open(feature_names_path, 'r') as f:
            feature_names = [line.strip() for line in f.readlines()]
    
    return model, feature_names

def predict(model, features):
    """Make predictions"""
    if len(features.shape) == 1:
        features = features.reshape(1, -1)
    
    predictions = model.predict(features)
    probabilities = model.predict_proba(features)
    
    return predictions, probabilities

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-dir', type=str, default='./models', help='Directory containing the model')
    parser.add_argument('--input-data', type=str, help='Input data for prediction (comma-separated values)')
    args = parser.parse_args()
    
    print("Loading model...")
    model, feature_names = load_model(args.model_dir)
    
    print(f"Model loaded successfully!")
    print(f"Expected features: {len(feature_names)}")
    if feature_names:
        print("Feature names:", feature_names[:5], "..." if len(feature_names) > 5 else "")
    
    if args.input_data:
        # Parse input data
        try:
            features = np.array([float(x) for x in args.input_data.split(',')])
            print(f"Input features shape: {features.shape}")
            
            predictions, probabilities = predict(model, features)
            
            print(f"Prediction: {predictions[0]}")
            print(f"Probabilities: {probabilities[0]}")
            
            # Wine class names
            class_names = ['class_0', 'class_1', 'class_2']
            print(f"Predicted class: {class_names[predictions[0]]}")
            
        except Exception as e:
            print(f"Error making prediction: {e}")
    else:
        print("No input data provided. Use --input-data with comma-separated values.")
        print("Example: --input-data '13.2,2.3,2.6,20.0,116.0,2.96,2.78,0.2,2.45,6.15,1.03,3.58,1050.0'")

if __name__ == "__main__":
    main()

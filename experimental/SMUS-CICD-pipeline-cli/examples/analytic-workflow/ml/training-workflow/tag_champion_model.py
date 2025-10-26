#!/usr/bin/env python3

import mlflow
import os

def tag_champion_model():
    """Tag the best model version as 'champion'"""
    
    # MLflow setup
    tracking_server_arn = "arn:aws:sagemaker:us-east-1:058264284947:mlflow-tracking-server/wine-classification-mlflow-v2"
    mlflow.set_tracking_uri(tracking_server_arn)
    
    model_name = "realistic-classifier-v1"
    
    print(f"Finding best model version for: {model_name}")
    
    # Get all versions of the model
    client = mlflow.MlflowClient()
    versions = client.search_model_versions(f"name='{model_name}'")
    
    if not versions:
        print(f"No versions found for model: {model_name}")
        return
    
    # Find the latest version (assuming it's the best from our experiment)
    latest_version = max(versions, key=lambda x: int(x.version))
    
    print(f"Latest version: {latest_version.version}")
    print(f"Current stage: {latest_version.current_stage}")
    
    # Set alias to "champion"
    client.set_registered_model_alias(
        name=model_name,
        alias="champion",
        version=latest_version.version
    )
    
    print(f"✅ Tagged version {latest_version.version} as 'champion'")
    print(f"Model URI: models:/{model_name}@champion")

if __name__ == "__main__":
    tag_champion_model()

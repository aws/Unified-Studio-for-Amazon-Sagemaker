#!/usr/bin/env python3

import boto3
import json
import os

def find_model_files():
    """Find model files on S3"""
    
    print("=== Finding Model Files on S3 ===")
    
    # Get account info
    sts_client = boto3.client('sts')
    account_id = sts_client.get_caller_identity()['Account']
    region = 'us-east-1'
    bucket_name = f"sagemaker-ml-workflow-{account_id}-{region}"
    
    s3_client = boto3.client('s3')
    
    print(f"Searching in bucket: {bucket_name}")
    
    # Look for model artifacts
    prefixes = ['realistic-models/', 'model-comparison/']
    
    all_models = []
    
    for prefix in prefixes:
        try:
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' in response:
                print(f"\n📁 Found objects under {prefix}:")
                for obj in response['Contents']:
                    key = obj['Key']
                    size = obj['Size']
                    modified = obj['LastModified']
                    
                    print(f"  📄 {key}")
                    print(f"      Size: {size:,} bytes")
                    print(f"      Modified: {modified}")
                    
                    if key.endswith('model.tar.gz'):
                        s3_uri = f"s3://{bucket_name}/{key}"
                        all_models.append({
                            'key': key,
                            'uri': s3_uri,
                            'size': size,
                            'modified': str(modified)
                        })
                        print(f"      🎯 Model URI: {s3_uri}")
                    print()
            else:
                print(f"No objects found under {prefix}")
                
        except Exception as e:
            print(f"Error searching {prefix}: {e}")
    
    # Check config files for model locations
    config_files = ['config/realistic_experiment.json', 'config/model_comparison_experiment.json']
    
    print("\n📋 Checking config files:")
    for config_file in config_files:
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            print(f"\n📄 {config_file}:")
            if 'model_data' in config:
                print(f"  Model Data: {config['model_data']}")
                all_models.append({
                    'source': config_file,
                    'uri': config['model_data'],
                    'job_name': config.get('job_name', 'unknown')
                })
            
            if 'job_name' in config:
                print(f"  Job Name: {config['job_name']}")
        else:
            print(f"❌ {config_file} not found")
    
    # Summary
    print(f"\n🎯 SUMMARY: Found {len(all_models)} model artifacts")
    for i, model in enumerate(all_models, 1):
        print(f"{i}. {model['uri']}")
        if 'job_name' in model:
            print(f"   Job: {model['job_name']}")
    
    return all_models

if __name__ == "__main__":
    models = find_model_files()

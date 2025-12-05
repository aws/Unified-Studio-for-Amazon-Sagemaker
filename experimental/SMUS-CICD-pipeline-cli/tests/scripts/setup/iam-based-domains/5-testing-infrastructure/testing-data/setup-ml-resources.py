#!/usr/bin/env python3
"""
Setup ML workflow testing resources in specified region.
Creates S3 bucket, uploads training data, inference data, and training code.
"""

import argparse
import boto3
import pandas as pd
import numpy as np
import subprocess
import sys
from pathlib import Path


def create_bucket_if_not_exists(bucket_name, region):
    """Create S3 bucket if it doesn't exist."""
    s3 = boto3.client('s3', region_name=region)
    
    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f"✅ Bucket {bucket_name} already exists")
        return True
    except:
        pass
    
    try:
        if region == 'us-east-1':
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )
        print(f"✅ Created bucket: {bucket_name}")
        return True
    except Exception as e:
        print(f"❌ Failed to create bucket: {e}")
        return False


def create_training_data(bucket_name, region):
    """Generate and upload synthetic training data."""
    print("📝 Creating training data...")
    
    np.random.seed(42)
    X = np.random.randn(1000, 20)
    y = np.random.choice([0, 1, 2], 1000)
    df = pd.DataFrame(X, columns=[f'feature_{i}' for i in range(20)])
    df['target'] = y
    
    local_file = '/tmp/training_data.csv'
    df.to_csv(local_file, index=False)
    
    s3 = boto3.client('s3', region_name=region)
    s3.upload_file(local_file, bucket_name, 'training-data/training_data.csv')
    print(f"✅ Uploaded training data to s3://{bucket_name}/training-data/")


def create_inference_data(bucket_name, region):
    """Generate and upload synthetic inference data."""
    print("📝 Creating inference data...")
    
    np.random.seed(123)
    X = np.random.randn(100, 20)
    df = pd.DataFrame(X, columns=[f'feature_{i}' for i in range(20)])
    
    local_file = '/tmp/inference_data.csv'
    df.to_csv(local_file, index=False)
    
    s3 = boto3.client('s3', region_name=region)
    s3.upload_file(local_file, bucket_name, 'inference-data/inference_data.csv')
    print(f"✅ Uploaded inference data to s3://{bucket_name}/inference-data/")


def upload_training_code(bucket_name, region):
    """Package and upload training code."""
    print("📦 Packaging training code...")
    
    # Find the training code directory
    script_dir = Path(__file__).parent
    training_code_dir = script_dir.parent.parent.parent.parent.parent.parent / 'examples' / 'analytic-workflow' / 'ml' / 'training' / 'workflows'
    
    if not training_code_dir.exists():
        print(f"❌ Training code directory not found: {training_code_dir}")
        return False
    
    # Run package script
    package_script = training_code_dir / 'package_training_code.sh'
    if package_script.exists():
        try:
            subprocess.run([str(package_script), region], check=True, cwd=training_code_dir)
            print(f"✅ Uploaded training code to s3://{bucket_name}/training_code.tar.gz")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to package training code: {e}")
            return False
    else:
        print(f"❌ Package script not found: {package_script}")
        return False


def verify_resources(bucket_name, region):
    """Verify all resources exist."""
    print("\n🔍 Verifying resources...")
    
    s3 = boto3.client('s3', region_name=region)
    
    resources = [
        'training-data/training_data.csv',
        'inference-data/inference_data.csv',
        'training_code.tar.gz'
    ]
    
    all_exist = True
    for key in resources:
        try:
            s3.head_object(Bucket=bucket_name, Key=key)
            print(f"✅ {key}")
        except:
            print(f"❌ {key} (MISSING)")
            all_exist = False
    
    return all_exist


def main():
    parser = argparse.ArgumentParser(description='Setup ML workflow testing resources')
    parser.add_argument('--region', default='us-east-1', help='AWS region (default: us-east-1)')
    parser.add_argument('--bucket', help='S3 bucket name (default: demo-bucket-smus-ml-{account_id}-{region})')
    args = parser.parse_args()
    
    region = args.region
    
    # Get AWS account ID from caller identity
    if not args.bucket:
        try:
            sts = boto3.client('sts', region_name=region)
            account_id = sts.get_caller_identity()['Account']
            bucket_name = f'demo-bucket-smus-ml-{account_id}-{region}'
        except Exception as e:
            print(f"❌ Failed to get AWS account ID: {e}")
            sys.exit(1)
    else:
        bucket_name = args.bucket
    
    print(f"🚀 Setting up ML resources in {region}")
    print(f"📦 Bucket: {bucket_name}\n")
    
    # Create bucket
    if not create_bucket_if_not_exists(bucket_name, region):
        sys.exit(1)
    
    # Create and upload data
    create_training_data(bucket_name, region)
    create_inference_data(bucket_name, region)
    upload_training_code(bucket_name, region)
    
    # Verify
    if verify_resources(bucket_name, region):
        print("\n✅ All ML resources setup complete!")
        
        # Save outputs
        output_file = f'/tmp/ml_bucket_{region}.txt'
        with open(output_file, 'w') as f:
            f.write(bucket_name)
        print(f"📝 Bucket name saved to {output_file}")
    else:
        print("\n❌ Some resources are missing")
        sys.exit(1)


if __name__ == '__main__':
    main()

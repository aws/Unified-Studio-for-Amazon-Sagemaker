#!/usr/bin/env python3

import subprocess
import sys
import argparse
import os
import json

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-dir', type=str, default=os.environ.get('SM_MODEL_DIR'))
    args = parser.parse_args()
    
    print("🔍 Debugging Package Installation Issues")
    
    # Check Python version and environment
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print(f"Current working directory: {os.getcwd()}")
    
    # Check what packages are already installed
    print("\n📦 Currently installed packages:")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "list"], 
                              capture_output=True, text=True, timeout=60)
        print("STDOUT:", result.stdout[:1000])  # First 1000 chars
        if result.stderr:
            print("STDERR:", result.stderr[:1000])
    except Exception as e:
        print(f"Error listing packages: {e}")
    
    # Check pip version
    print("\n🔧 Pip version:")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "--version"], 
                              capture_output=True, text=True, timeout=30)
        print("STDOUT:", result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
    except Exception as e:
        print(f"Error checking pip version: {e}")
    
    # Try installing sagemaker with verbose output
    print("\n📦 Attempting to install sagemaker...")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "install", "sagemaker", "-v"], 
                              capture_output=True, text=True, timeout=300)
        print("STDOUT:", result.stdout[-2000:])  # Last 2000 chars
        if result.stderr:
            print("STDERR:", result.stderr[-2000:])
        print(f"Return code: {result.returncode}")
    except subprocess.TimeoutExpired:
        print("❌ Installation timed out after 5 minutes")
    except Exception as e:
        print(f"❌ Installation error: {e}")
    
    # Try installing mlflow
    print("\n📦 Attempting to install mlflow...")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "install", "mlflow", "-v"], 
                              capture_output=True, text=True, timeout=300)
        print("STDOUT:", result.stdout[-2000:])  # Last 2000 chars
        if result.stderr:
            print("STDERR:", result.stderr[-2000:])
        print(f"Return code: {result.returncode}")
    except subprocess.TimeoutExpired:
        print("❌ Installation timed out after 5 minutes")
    except Exception as e:
        print(f"❌ Installation error: {e}")
    
    # Check if packages are now available
    print("\n🧪 Testing package imports:")
    try:
        import sagemaker
        print(f"✅ SageMaker SDK imported successfully: {sagemaker.__version__}")
    except ImportError as e:
        print(f"❌ SageMaker SDK import failed: {e}")
    
    try:
        import mlflow
        print(f"✅ MLflow imported successfully: {mlflow.__version__}")
    except ImportError as e:
        print(f"❌ MLflow import failed: {e}")
    
    # Save diagnostic results
    results = {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "working_directory": os.getcwd(),
        "diagnostic_completed": True
    }
    
    with open(os.path.join(args.model_dir, "diagnostic_results.json"), 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n✅ Diagnostic completed!")

if __name__ == "__main__":
    main()

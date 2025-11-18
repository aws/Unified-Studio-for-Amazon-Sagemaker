#!/bin/bash
set -e

echo "🔧 Setting up deployment test environment..."

# Create isolated venv
VENV_PATH="/tmp/deploy_test_env"
rm -rf "$VENV_PATH"
python3 -m venv "$VENV_PATH"
source "$VENV_PATH/bin/activate"

# Upgrade pip
pip install --upgrade pip --quiet

# Install required packages
echo "📦 Installing packages..."
pip install --quiet \
    sagemaker>=2.215.0 \
    mlflow==2.13.2 \
    sagemaker-mlflow==0.1.0 \
    boto3 \
    numpy

echo "✅ Environment ready"
echo ""
echo "Activate with: source $VENV_PATH/bin/activate"

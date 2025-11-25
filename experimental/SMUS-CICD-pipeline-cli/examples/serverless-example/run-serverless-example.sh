#!/bin/bash
# Airflow Serverless Example Pipeline Runner

set -e

echo "🚀 Running Serverless Marketing Pipeline Example"
echo "==============================================="

# Set environment variables
export DEV_DOMAIN_REGION="us-east-1"
export PROD_DOMAIN_REGION="us-east-1"

# Pipeline operations
echo "📋 1. Parsing pipeline manifest..."
python -m smus_cicd.cli parse --bundle DemoMarketingPipeline-Serverless.yaml

echo "📦 2. Creating bundle..."
python -m smus_cicd.cli bundle --bundle DemoMarketingPipeline-Serverless.yaml

echo "🚀 3. Deploying to dev (with environment variables)..."
python -m smus_cicd.cli deploy --bundle DemoMarketingPipeline-Serverless.yaml dev

echo "🚀 4. Deploying to test..."
python -m smus_cicd.cli deploy --bundle DemoMarketingPipeline-Serverless.yaml test

echo "📊 5. Monitoring pipeline..."
python -m smus_cicd.cli monitor --bundle DemoMarketingPipeline-Serverless.yaml

echo "✅ Serverless pipeline example completed!"

#!/bin/bash
# MWAA Example Pipeline Runner

set -e

echo "🚀 Running MWAA Marketing Pipeline Example"
echo "=========================================="

# Set environment variables
export DEV_DOMAIN_REGION="us-east-1"
export PROD_DOMAIN_REGION="us-east-1"

# Pipeline operations
echo "📋 1. Parsing pipeline manifest..."
python -m smus_cicd.cli parse --bundle DemoMarketingPipeline-MWAA.yaml

echo "📦 2. Creating bundle..."
python -m smus_cicd.cli bundle --bundle DemoMarketingPipeline-MWAA.yaml

echo "🚀 3. Deploying to dev..."
python -m smus_cicd.cli deploy --bundle DemoMarketingPipeline-MWAA.yaml dev

echo "📊 4. Describing pipeline..."
python -m smus_cicd.cli describe --bundle DemoMarketingPipeline-MWAA.yaml

echo "✅ MWAA pipeline example completed!"

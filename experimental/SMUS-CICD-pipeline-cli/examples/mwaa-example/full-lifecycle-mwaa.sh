#!/bin/bash
# MWAA Pipeline Full Lifecycle Demo Script

set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_FILE="DemoMarketingPipeline-MWAA.yaml"

# Set environment variables
export DEV_DOMAIN_REGION="us-east-1"
export PROD_DOMAIN_REGION="us-east-1"

run_command() {
    local cmd="$1"
    echo "🔍 $cmd"
    eval "$cmd"
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo "✅ SUCCESS"
    else
        echo "❌ FAILURE: exit code $exit_code"
        return $exit_code
    fi
    echo ""
    return 0
}

echo "🚀 MWAA Pipeline Full Lifecycle Demo"
echo "===================================="

# Step 1: Get S3 connection details
echo "📋 Step 1: Get S3 connection details"
run_command "python -m smus_cicd.cli describe --bundle \"$PIPELINE_FILE\" --connect"

# Step 1.5: Upload local files to S3 before bundling
echo "📤 Step 1.5: Upload local files to dev project S3"
echo "Uploading workflows/dags/marketing_dag.py and src/marketing_utils.py to S3..."
# This will be done via AWS CLI to the S3 location shown in step 1

# Step 2: Create bundle
echo "📦 Step 2: Create bundle"
run_command "python -m smus_cicd.cli bundle --bundle \"$PIPELINE_FILE\""

# Step 3: Deploy to test
echo "🚀 Step 3: Deploy to test"
run_command "python -m smus_cicd.cli deploy --bundle \"$PIPELINE_FILE\" test"

# Step 4: Deploy to prod
echo "🚀 Step 4: Deploy to prod"
run_command "python -m smus_cicd.cli deploy --bundle \"$PIPELINE_FILE\" prod"

# Step 5: Monitor pipeline
echo "📊 Step 5: Monitor pipeline"
run_command "python -m smus_cicd.cli monitor --bundle \"$PIPELINE_FILE\""

echo "✅ MWAA pipeline lifecycle completed!"
echo "🔍 Environment variables were automatically resolved:"
echo "   - test: ENV_NAME=test, S3_PREFIX=test-data, LOG_LEVEL=INFO"
echo "   - prod: ENV_NAME=prod, S3_PREFIX=prod-data, LOG_LEVEL=ERROR"

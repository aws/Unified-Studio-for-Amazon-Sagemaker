#!/bin/bash
# ML Dev Workflow Test Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKFLOW_FILE="ml_dev_workflow.yaml"

# Default configuration
DEFAULT_REGION="us-west-2"
DEFAULT_BUCKET="demo-bucket-smus-ml-us-west-2"
DEFAULT_ENDPOINT="https://overdrive-gamma.us-west-2.api.aws"

# Override with parameter if provided
REGION="${1:-$DEFAULT_REGION}"

# Set region-specific configuration
if [[ "$REGION" == "us-east-1" ]]; then
    BUCKET_NAME="demo-bucket-smus-ml-us-east-1"
    ENDPOINT_URL="https://overdrive-gamma.us-east-1.api.aws"
else
    BUCKET_NAME="$DEFAULT_BUCKET"
    ENDPOINT_URL="$DEFAULT_ENDPOINT"
fi

ROLE_ARN="arn:aws:iam::058264284947:role/OverdriveExecutionRole"

echo "🌍 Using region: $REGION"
echo "🪣 Using bucket: $BUCKET_NAME"
echo "🔗 Using endpoint: $ENDPOINT_URL"
echo ""

run_command() {
    local cmd="$1"
    echo "🔍 $cmd"
    eval "$cmd"
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo "✅ SUCCESS"
    else
        echo "❌ FAILURE: exit code $exit_code"
        exit $exit_code
    fi
    echo ""
    return 0
}

# Step 0: Cleanup previous resources
echo "🧹 Step 0: Cleanup previous ML dev resources"
OLD_WORKFLOWS=$(aws awsoverdriveservice list-workflows --region $REGION --endpoint-url $ENDPOINT_URL --query 'Workflows[?starts_with(Name, `ml-dev-test`)].WorkflowArn' --output text)
for workflow_arn in $OLD_WORKFLOWS; do
    if [ ! -z "$workflow_arn" ]; then
        echo "Deleting workflow: $workflow_arn"
        aws awsoverdriveservice delete-workflow --workflow-arn "$workflow_arn" --region $REGION --endpoint-url $ENDPOINT_URL 2>/dev/null || true
    fi
done

aws s3 rm "s3://$BUCKET_NAME/scripts/" --recursive --region $REGION 2>/dev/null || true
aws s3 rm "s3://$BUCKET_NAME/ml-workflows/" --recursive --region $REGION 2>/dev/null || true
echo "✅ Cleanup completed"
echo ""

echo "🚀 ML Dev Workflow Test"
echo "======================="

# Step 1: Package and upload training code
echo "📦 Step 1: Package and upload training code"
run_command "./package_training_code.sh $REGION"

# Step 1b: Package and upload orchestrator code
echo "📦 Step 1b: Package and upload orchestrator code"
run_command "./package_orchestrator_code.sh $REGION"

# Step 2: Create test training data
echo "📝 Step 2: Create test training data"
python3 -c "
import pandas as pd
import numpy as np
np.random.seed(42)
X = np.random.randn(1000, 20)
y = np.random.choice([0, 1, 2], 1000)
df = pd.DataFrame(X, columns=[f'feature_{i}' for i in range(20)])
df['target'] = y
df.to_csv('/tmp/training_data.csv', index=False)
"
run_command "aws s3 cp \"/tmp/training_data.csv\" \"s3://$BUCKET_NAME/training-data/training_data.csv\" --region $REGION"

# Step 3: Generate workflow YAML and upload
echo "📤 Step 3: Generate workflow YAML and upload to S3"
TEMP_WORKFLOW_FILE="/tmp/temp_$WORKFLOW_FILE"
sed "s/demo-bucket-smus-ml-us-west-2/$BUCKET_NAME/g" "$WORKFLOW_FILE" > "$TEMP_WORKFLOW_FILE"

WORKFLOW_S3_KEY="ml-workflows/$(date +%s)-$WORKFLOW_FILE"
run_command "aws s3 cp \"$TEMP_WORKFLOW_FILE\" \"s3://$BUCKET_NAME/$WORKFLOW_S3_KEY\" --region $REGION"
rm -f "$TEMP_WORKFLOW_FILE"

# Step 4: Create Airflow workflow
echo "🏗️  Step 4: Create ML Dev workflow"
WORKFLOW_NAME="ml-dev-test-$(date +%s)"

WORKFLOW_OUTPUT=$(aws awsoverdriveservice create-workflow --name "$WORKFLOW_NAME" --definition-s3-location Bucket=$BUCKET_NAME,ObjectKey=$WORKFLOW_S3_KEY --role-arn "$ROLE_ARN" --region $REGION --endpoint-url $ENDPOINT_URL)
WORKFLOW_ARN=$(echo "$WORKFLOW_OUTPUT" | grep -o '"WorkflowArn": "[^"]*"' | cut -d'"' -f4)
echo "✅ SUCCESS - Workflow ARN: $WORKFLOW_ARN"
echo ""

# Step 5: Start workflow run
echo "▶️  Step 5: Start ML dev workflow run"
run_command "aws awsoverdriveservice start-workflow-run --workflow-arn \"$WORKFLOW_ARN\" --region $REGION --endpoint-url $ENDPOINT_URL"

# Step 6: Monitor workflow
echo "👀 Step 6: Monitor ML dev workflow (15-minute timeout)"
START_TIME=$(date +%s)
RUN_ID=""

for i in {1..15}; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    
    WORKFLOW_RUNS=$(aws awsoverdriveservice list-workflow-runs --workflow-arn "$WORKFLOW_ARN" --region $REGION --endpoint-url $ENDPOINT_URL)
    STATUS=$(echo "$WORKFLOW_RUNS" | jq -r '.WorkflowRuns[0].RunDetailSummary.Status')
    RUN_ID=$(echo "$WORKFLOW_RUNS" | jq -r '.WorkflowRuns[0].RunId')
    
    echo "[$i] $(date '+%H:%M:%S') - Elapsed: ${ELAPSED}s - Status: $STATUS"
    
    if [[ "$STATUS" == "SUCCEEDED" || "$STATUS" == "SUCCESS" ]]; then
        echo "✅ ML Dev workflow completed successfully after ${ELAPSED} seconds!"
        break
    elif [[ "$STATUS" == "FAILED" || "$STATUS" == "CANCELLED" ]]; then
        echo "❌ ML Dev workflow failed with status: $STATUS"
        break
    fi
    
    sleep 60
done

# Step 7: Get detailed workflow run information
echo "📊 Step 7: Get detailed workflow run information"
if [ ! -z "$RUN_ID" ]; then
    run_command "aws awsoverdriveservice get-workflow-run --workflow-arn \"$WORKFLOW_ARN\" --run-id \"$RUN_ID\" --region $REGION --endpoint-url $ENDPOINT_URL"
fi

echo "✅ ML Dev workflow test completed!"

#!/bin/bash
# ML Deploy Workflow Test Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKFLOW_FILE="ml_deploy_workflow.yaml"

# Default configuration
DEFAULT_REGION="us-west-2"
DEFAULT_BUCKET="demo-bucket-smus-ml-us-west-2"
DEFAULT_ENDPOINT="https://overdrive-gamma.us-west-2.api.aws"
DEFAULT_STAGE="test"

# Override with parameters
REGION="${1:-$DEFAULT_REGION}"
STAGE="${2:-$DEFAULT_STAGE}"

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
echo "🏷️  Using stage: $STAGE"
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
echo "🧹 Step 0: Cleanup previous ML deploy resources"
OLD_WORKFLOWS=$(aws awsoverdriveservice list-workflows --region $REGION --endpoint-url $ENDPOINT_URL --query 'Workflows[?starts_with(Name, `ml-deploy-test`)].WorkflowArn' --output text)
for workflow_arn in $OLD_WORKFLOWS; do
    if [ ! -z "$workflow_arn" ]; then
        echo "Deleting workflow: $workflow_arn"
        aws awsoverdriveservice delete-workflow --workflow-arn "$workflow_arn" --region $REGION --endpoint-url $ENDPOINT_URL 2>/dev/null || true
    fi
done

aws s3 rm "s3://$BUCKET_NAME/scripts/" --recursive --region $REGION 2>/dev/null || true
aws s3 rm "s3://$BUCKET_NAME/ml-deploy-workflows/" --recursive --region $REGION 2>/dev/null || true
echo "✅ Cleanup completed"
echo ""

echo "🚀 ML Deploy Workflow Test - Stage: $STAGE"
echo "=========================================="

# Step 1: Upload scripts to S3
echo "📤 Step 1: Upload ML deploy scripts to S3"
run_command "aws s3 cp \"get_champion_model.py\" \"s3://$BUCKET_NAME/scripts/get_champion_model.py\" --region $REGION"

# Step 2: Create test data for endpoint testing
echo "📝 Step 2: Create test data for endpoint testing"
python3 -c "
import pandas as pd
import numpy as np
np.random.seed(42)
X = np.random.randn(50, 20)
df = pd.DataFrame(X, columns=[f'feature_{i}' for i in range(20)])
df.to_csv('/tmp/test_data.csv', index=False)
"
run_command "aws s3 cp \"/tmp/test_data.csv\" \"s3://$BUCKET_NAME/test-data/test_data.csv\" --region $REGION"

# Step 3: Generate stage-specific workflow YAML and upload
echo "📤 Step 3: Generate stage-specific workflow YAML and upload to S3"
TEMP_WORKFLOW_FILE="/tmp/temp_$WORKFLOW_FILE"

# Replace placeholders with actual values
sed -e "s/demo-bucket-smus-ml-us-west-2/$BUCKET_NAME/g" \
    -e "s/{{ var.value.stage }}/$STAGE/g" \
    -e "s/{{ var.value.account_id }}/058264284947/g" \
    -e "s/{{ var.value.s3_bucket }}/$BUCKET_NAME/g" \
    -e "s/{{ var.value.mlflow_tracking_uri }}/http:\/\/mlflow-server.example.com/g" \
    "$WORKFLOW_FILE" > "$TEMP_WORKFLOW_FILE"

WORKFLOW_S3_KEY="ml-deploy-workflows/$(date +%s)-$STAGE-$WORKFLOW_FILE"
run_command "aws s3 cp \"$TEMP_WORKFLOW_FILE\" \"s3://$BUCKET_NAME/$WORKFLOW_S3_KEY\" --region $REGION"
rm -f "$TEMP_WORKFLOW_FILE"

# Step 4: Create Airflow workflow
echo "🏗️  Step 4: Create ML Deploy workflow for $STAGE"
WORKFLOW_NAME="ml-deploy-test-$STAGE-$(date +%s)"

WORKFLOW_OUTPUT=$(aws awsoverdriveservice create-workflow --name "$WORKFLOW_NAME" --definition-s3-location Bucket=$BUCKET_NAME,ObjectKey=$WORKFLOW_S3_KEY --role-arn "$ROLE_ARN" --region $REGION --endpoint-url $ENDPOINT_URL)
WORKFLOW_ARN=$(echo "$WORKFLOW_OUTPUT" | grep -o '"WorkflowArn": "[^"]*"' | cut -d'"' -f4)
echo "✅ SUCCESS - Workflow ARN: $WORKFLOW_ARN"
echo ""

# Step 5: Start workflow run
echo "▶️  Step 5: Start ML deploy workflow run"
run_command "aws awsoverdriveservice start-workflow-run --workflow-arn \"$WORKFLOW_ARN\" --region $REGION --endpoint-url $ENDPOINT_URL"

# Step 6: Monitor workflow
echo "👀 Step 6: Monitor ML deploy workflow (20-minute timeout)"
START_TIME=$(date +%s)

for i in {1..20}; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    
    STATUS=$(aws awsoverdriveservice list-workflow-runs --workflow-arn "$WORKFLOW_ARN" --region $REGION --endpoint-url $ENDPOINT_URL --query 'WorkflowRuns[0].RunDetailSummary.Status' --output text)
    
    echo "[$i] $(date '+%H:%M:%S') - Elapsed: ${ELAPSED}s - Status: $STATUS"
    
    if [[ "$STATUS" == "SUCCEEDED" || "$STATUS" == "SUCCESS" ]]; then
        echo "✅ ML Deploy workflow for $STAGE completed successfully after ${ELAPSED} seconds!"
        break
    elif [[ "$STATUS" == "FAILED" || "$STATUS" == "CANCELLED" ]]; then
        echo "❌ ML Deploy workflow failed with status: $STATUS"
        break
    fi
    
    sleep 60
done

echo "✅ ML Deploy workflow test for $STAGE completed!"

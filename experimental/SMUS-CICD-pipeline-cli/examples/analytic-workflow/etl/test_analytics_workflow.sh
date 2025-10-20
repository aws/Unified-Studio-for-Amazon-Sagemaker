#!/bin/bash
# Analytics Workflow Full Lifecycle Test Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKFLOW_FILE="s3_analytics_workflow.yaml"
GLUE_SCRIPT="glue_s3_list_job.py"

# Default configuration for us-west-2 (works better)
DEFAULT_REGION="us-west-2"
DEFAULT_BUCKET="demo-bucket-smus-cicd-us-west-2-4947"
DEFAULT_ENDPOINT="https://overdrive-gamma.us-west-2.api.aws"

# Override with parameter if provided
REGION="${1:-$DEFAULT_REGION}"

# Set region-specific configuration
if [[ "$REGION" == "us-east-1" ]]; then
    BUCKET_NAME="demo-bucket-smus-cicd-us-east-1-4947"
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
        echo "❌ Script stopping due to failure"
        exit $exit_code
    fi
    echo ""
    return 0
}

# Step 0: Cleanup previous resources
echo "🧹 Step 0: Cleanup previous resources"
echo "Cleaning up old workflows..."
OLD_WORKFLOWS=$(aws awsoverdriveservice list-workflows --region $REGION --endpoint-url $ENDPOINT_URL --query 'Workflows[?starts_with(Name, `analytics-test`)].WorkflowArn' --output text)
for workflow_arn in $OLD_WORKFLOWS; do
    if [ ! -z "$workflow_arn" ]; then
        echo "Deleting workflow: $workflow_arn"
        aws awsoverdriveservice delete-workflow --workflow-arn "$workflow_arn" --region $REGION --endpoint-url $ENDPOINT_URL 2>/dev/null || true
    fi
done

echo "Cleaning up S3 files..."
aws s3 rm "s3://$BUCKET_NAME/glue-scripts/" --recursive --region $REGION 2>/dev/null || true
aws s3 rm "s3://$BUCKET_NAME/analytics-workflows/" --recursive --region $REGION 2>/dev/null || true
aws s3 rm "s3://$BUCKET_NAME/shared/" --recursive --region $REGION 2>/dev/null || true

echo "✅ Cleanup completed"
echo ""

echo "🚀 Analytics Workflow Full Lifecycle Test"
echo "========================================"

# Step 1: Upload Glue script to S3
echo "📤 Step 1: Upload Glue script to S3"
run_command "aws s3 cp \"$GLUE_SCRIPT\" \"s3://$BUCKET_NAME/glue-scripts/glue_s3_list_job.py\" --region $REGION"
run_command "aws s3 cp \"glue_covid_summary_job.py\" \"s3://$BUCKET_NAME/glue-scripts/glue_covid_summary_job.py\" --region $REGION"

# Step 2: Create test file in S3
echo "📝 Step 2: Create test file in S3"
run_command "echo 'This is a test file for the workflow' | aws s3 cp - \"s3://$BUCKET_NAME/shared/test-file.txt\" --region $REGION"

# Step 3: Generate region-specific workflow YAML and upload to S3
echo "📤 Step 3: Generate region-specific workflow YAML and upload to S3"
TEMP_WORKFLOW_FILE="/tmp/temp_$WORKFLOW_FILE"

# Read the original YAML and replace bucket placeholders
sed "s/demo-bucket-smus-cicd-us-west-2-4947/$BUCKET_NAME/g" "$WORKFLOW_FILE" > "$TEMP_WORKFLOW_FILE"

WORKFLOW_S3_KEY="analytics-workflows/$(date +%s)-$WORKFLOW_FILE"
run_command "aws s3 cp \"$TEMP_WORKFLOW_FILE\" \"s3://$BUCKET_NAME/$WORKFLOW_S3_KEY\" --region $REGION"

# Cleanup temp file
rm -f "$TEMP_WORKFLOW_FILE"

# Step 4: Setup Lake Formation permissions
echo "🔐 Step 4: Setup Lake Formation permissions for COVID database"
run_command "aws lakeformation grant-permissions --region us-east-1 --permissions DESCRIBE --resource '{\"Database\":{\"Name\":\"covid19_db\"}}' --principal '{\"DataLakePrincipalIdentifier\":\"arn:aws:iam::058264284947:role/OverdriveExecutionRole\"}'"
run_command "aws lakeformation grant-permissions --region us-east-1 --permissions CREATE_TABLE --resource '{\"Database\":{\"Name\":\"covid19_db\"}}' --principal '{\"DataLakePrincipalIdentifier\":\"arn:aws:iam::058264284947:role/OverdriveExecutionRole\"}'"
run_command "aws lakeformation grant-permissions --region us-east-1 --permissions DESCRIBE --resource '{\"Table\":{\"DatabaseName\":\"covid19_db\",\"Name\":\"worldwide_aggregate\"}}' --principal '{\"DataLakePrincipalIdentifier\":\"arn:aws:iam::058264284947:role/OverdriveExecutionRole\"}'"
run_command "aws lakeformation grant-permissions --region us-east-1 --permissions SELECT --resource '{\"Table\":{\"DatabaseName\":\"covid19_db\",\"Name\":\"worldwide_aggregate\"}}' --principal '{\"DataLakePrincipalIdentifier\":\"arn:aws:iam::058264284947:role/OverdriveExecutionRole\"}'"
run_command "aws lakeformation grant-permissions --region us-east-1 --permissions DESCRIBE --resource '{\"Table\":{\"DatabaseName\":\"covid19_db\",\"Name\":\"us_simplified\"}}' --principal '{\"DataLakePrincipalIdentifier\":\"arn:aws:iam::058264284947:role/OverdriveExecutionRole\"}'"
run_command "aws lakeformation grant-permissions --region us-east-1 --permissions SELECT --resource '{\"Table\":{\"DatabaseName\":\"covid19_db\",\"Name\":\"us_simplified\"}}' --principal '{\"DataLakePrincipalIdentifier\":\"arn:aws:iam::058264284947:role/OverdriveExecutionRole\"}'"


# Step 5: List existing workflows
echo "📋 Step 5: List existing workflows"
run_command "aws awsoverdriveservice list-workflows --region $REGION --endpoint-url $ENDPOINT_URL"

# Step 6: Create Airflow Serverless workflow using Overdrive API
echo "🏗️  Step 6: Create Airflow Serverless workflow using Overdrive API"
WORKFLOW_NAME="analytics-test-$(date +%s)"

WORKFLOW_OUTPUT=$(aws awsoverdriveservice create-workflow --name "$WORKFLOW_NAME" --definition-s3-location Bucket=$BUCKET_NAME,ObjectKey=$WORKFLOW_S3_KEY --role-arn "$ROLE_ARN" --region $REGION --endpoint-url $ENDPOINT_URL)
echo "$WORKFLOW_OUTPUT"
WORKFLOW_ARN=$(echo "$WORKFLOW_OUTPUT" | grep -o '"WorkflowArn": "[^"]*"' | cut -d'"' -f4)
echo "✅ SUCCESS - Workflow ARN: $WORKFLOW_ARN"
echo ""

# Step 7: Get workflow status
echo "📊 Step 7: Get workflow status"
run_command "aws awsoverdriveservice get-workflow --workflow-arn \"$WORKFLOW_ARN\" --region $REGION --endpoint-url $ENDPOINT_URL"

# Step 8: Start workflow run
echo "▶️  Step 8: Start workflow run"
run_command "aws awsoverdriveservice start-workflow-run --workflow-arn \"$WORKFLOW_ARN\" --region $REGION --endpoint-url $ENDPOINT_URL"

# Step 9: Monitor workflow run with 10-minute timeout
echo "👀 Step 9: Monitor workflow run (10-minute timeout)"
START_TIME=$(date +%s)

for i in {1..10}; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    
    STATUS=$(aws awsoverdriveservice list-workflow-runs --workflow-arn "$WORKFLOW_ARN" --region $REGION --endpoint-url $ENDPOINT_URL --query 'WorkflowRuns[0].RunDetailSummary.Status' --output text)
    
    echo "[$i] $(date '+%H:%M:%S') - Elapsed: ${ELAPSED}s - Status: $STATUS"
    
    if [[ "$STATUS" == "SUCCEEDED" || "$STATUS" == "SUCCESS" ]]; then
        echo "✅ Workflow completed successfully after ${ELAPSED} seconds!"
        break
    elif [[ "$STATUS" == "FAILED" || "$STATUS" == "CANCELLED" || "$STATUS" == "STOPPED" ]]; then
        echo "❌ Workflow failed with status: $STATUS after ${ELAPSED} seconds"
        break
    elif [[ "$STATUS" == "RUNNING" ]]; then
        echo "🏃 Workflow is now running! Took ${ELAPSED} seconds to start"
    fi
    
    sleep 60
done

# Step 9: Check CloudWatch logs for S3 paths
echo "📋 Step 9: Check CloudWatch logs for S3 paths"
WORKFLOW_LOG_NAME=$(echo "$WORKFLOW_ARN" | sed 's/.*workflow\///')
LOG_GROUP="/aws/mwaa-serverless/$WORKFLOW_LOG_NAME/"

echo "Checking for log streams..."
aws logs describe-log-streams --log-group-name "$LOG_GROUP" --region $REGION --order-by LastEventTime --descending --max-items 5

echo "✅ Analytics workflow lifecycle test completed!"

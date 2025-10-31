#!/bin/bash

REGION=${1:-us-west-2}
BUCKET="demo-bucket-smus-ml-us-west-2"
ENDPOINT_URL="https://overdrive-gamma.$REGION.api.aws"
ROLE_ARN="arn:aws:iam::058264284947:role/OverdriveExecutionRole"

echo "🚀 Running ML Dev Workflow with Notebook Orchestrator"
echo "Region: $REGION"

# Upload workflow to S3
WORKFLOW_S3_KEY="ml-workflows/$(date +%s)-ml_dev_workflow.yaml"
aws s3 cp ml_dev_workflow.yaml s3://$BUCKET/$WORKFLOW_S3_KEY --region $REGION

# Upload notebook to S3
aws s3 cp ml_orchestrator_notebook.ipynb s3://$BUCKET/notebooks/ml_orchestrator_notebook.ipynb --region $REGION

# Create workflow
WORKFLOW_NAME="ml-dev-notebook-$(date +%s)"
WORKFLOW_OUTPUT=$(aws awsoverdriveservice create-workflow \
    --name "$WORKFLOW_NAME" \
    --definition-s3-location Bucket=$BUCKET,ObjectKey=$WORKFLOW_S3_KEY \
    --role-arn "$ROLE_ARN" \
    --region $REGION \
    --endpoint-url $ENDPOINT_URL)

WORKFLOW_ARN=$(echo "$WORKFLOW_OUTPUT" | grep -o '"WorkflowArn": "[^"]*"' | cut -d'"' -f4)

if [ ! -z "$WORKFLOW_ARN" ]; then
    echo "✅ Workflow created: $WORKFLOW_ARN"
    
    # Start workflow run
    aws awsoverdriveservice start-workflow-run \
        --workflow-arn "$WORKFLOW_ARN" \
        --region $REGION \
        --endpoint-url $ENDPOINT_URL
    
    echo "✅ Workflow started successfully"
    
    # Monitor workflow for 10 minutes
    echo "👀 Monitoring workflow (10-minute timeout)"
    START_TIME=$(date +%s)
    RUN_ID=""
    
    for i in {1..10}; do
        CURRENT_TIME=$(date +%s)
        ELAPSED=$((CURRENT_TIME - START_TIME))
        
        WORKFLOW_RUNS=$(aws awsoverdriveservice list-workflow-runs --workflow-arn "$WORKFLOW_ARN" --region $REGION --endpoint-url $ENDPOINT_URL)
        STATUS=$(echo "$WORKFLOW_RUNS" | jq -r '.WorkflowRuns[0].RunDetailSummary.Status')
        RUN_ID=$(echo "$WORKFLOW_RUNS" | jq -r '.WorkflowRuns[0].RunId')
        
        echo "[$i] $(date '+%H:%M:%S') - Elapsed: ${ELAPSED}s - Status: $STATUS"
        
        if [[ "$STATUS" == "SUCCEEDED" || "$STATUS" == "SUCCESS" ]]; then
            echo "✅ Workflow completed successfully after ${ELAPSED} seconds!"
            break
        elif [[ "$STATUS" == "FAILED" || "$STATUS" == "CANCELLED" ]]; then
            echo "❌ Workflow failed with status: $STATUS"
            break
        fi
        
        sleep 60
    done
    
    # Get detailed workflow run information
    echo "📊 Getting detailed workflow run information"
    if [ ! -z "$RUN_ID" ]; then
        aws awsoverdriveservice get-workflow-run --workflow-arn "$WORKFLOW_ARN" --run-id "$RUN_ID" --region $REGION --endpoint-url $ENDPOINT_URL
    fi
    
    echo "📊 Monitor at: https://overdrive-gamma.$REGION.console.aws/workflows"
else
    echo "❌ Workflow creation failed"
    exit 1
fi

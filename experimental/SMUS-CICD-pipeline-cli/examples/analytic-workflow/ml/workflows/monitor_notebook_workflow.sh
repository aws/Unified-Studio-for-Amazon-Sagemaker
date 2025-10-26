#!/bin/bash

WORKFLOW_ARN="arn:aws:airflow-serverless:us-west-2:058264284947:workflow/ml-dev-notebook-1761082103-TuftcZYYhO"
RUN_ID="li1uhllx591CSfw"
REGION="us-west-2"
ENDPOINT_URL="https://overdrive-gamma.us-west-2.api.aws"

echo "👀 Monitoring ML Notebook Workflow (15-minute timeout)"
START_TIME=$(date +%s)

for i in {1..15}; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    
    STATUS=$(aws awsoverdriveservice list-workflow-runs --workflow-arn "$WORKFLOW_ARN" --region $REGION --endpoint-url $ENDPOINT_URL --query 'WorkflowRuns[0].RunDetailSummary.Status' --output text)
    
    echo "[$i] $(date '+%H:%M:%S') - Elapsed: ${ELAPSED}s - Status: $STATUS"
    
    if [[ "$STATUS" == "SUCCEEDED" || "$STATUS" == "SUCCESS" ]]; then
        echo "✅ Notebook workflow completed successfully after ${ELAPSED} seconds!"
        
        # Get detailed workflow run results
        echo "📋 Getting detailed workflow run results..."
        aws awsoverdriveservice get-workflow-run --workflow-arn "$WORKFLOW_ARN" --run-id "$RUN_ID" --region $REGION --endpoint-url $ENDPOINT_URL
        
        # Check CloudWatch logs
        WORKFLOW_LOG_NAME=$(echo "$WORKFLOW_ARN" | sed 's/.*workflow\///')
        LOG_GROUP="/aws/mwaa-serverless/$WORKFLOW_LOG_NAME/"
        
        echo "📋 Checking CloudWatch logs..."
        aws logs describe-log-streams --log-group-name "$LOG_GROUP" --region $REGION --order-by LastEventTime --descending --max-items 5
        
        # Check for SageMaker jobs created by notebook
        echo "📋 Checking SageMaker jobs created by notebook..."
        echo "Training Jobs:"
        aws sagemaker list-training-jobs --region $REGION --sort-by CreationTime --sort-order Descending --max-results 3
        echo "Transform Jobs:"
        aws sagemaker list-transform-jobs --region $REGION --sort-by CreationTime --sort-order Descending --max-results 3
        
        # Check S3 outputs
        echo "📋 Checking S3 outputs..."
        aws s3 ls s3://demo-bucket-smus-ml-us-west-2/model-artifacts/ --region $REGION --recursive
        aws s3 ls s3://demo-bucket-smus-ml-us-west-2/inference-results/ --region $REGION --recursive
        
        break
    elif [[ "$STATUS" == "FAILED" || "$STATUS" == "CANCELLED" || "$STATUS" == "STOPPED" ]]; then
        echo "❌ Notebook workflow failed with status: $STATUS after ${ELAPSED} seconds"
        
        # Get detailed error information
        echo "📋 Getting detailed error information..."
        aws awsoverdriveservice get-workflow-run --workflow-arn "$WORKFLOW_ARN" --run-id "$RUN_ID" --region $REGION --endpoint-url $ENDPOINT_URL
        
        # Check logs for errors
        WORKFLOW_LOG_NAME=$(echo "$WORKFLOW_ARN" | sed 's/.*workflow\///')
        LOG_GROUP="/aws/mwaa-serverless/$WORKFLOW_LOG_NAME/"
        
        echo "📋 Checking error logs..."
        aws logs describe-log-streams --log-group-name "$LOG_GROUP" --region $REGION --order-by LastEventTime --descending --max-items 5
        
        break
    elif [[ "$STATUS" == "RUNNING" ]]; then
        echo "🏃 Notebook workflow is running! Took ${ELAPSED} seconds to start"
    fi
    
    sleep 60
done

echo "✅ Notebook workflow monitoring completed!"

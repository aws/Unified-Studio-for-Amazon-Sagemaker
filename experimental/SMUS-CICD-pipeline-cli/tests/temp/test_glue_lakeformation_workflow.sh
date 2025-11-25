#!/bin/bash

# Test Analytics Workflow with Lake Formation and Glue
# This script tests the complete workflow from Lake Formation setup to Glue job execution

set -e

echo "=== Starting Analytics Workflow Test ==="

# Configuration
BUCKET_NAME="amazon-datazone-v2-058264284947-us-east-1-285314902"
DATABASE_NAME="covid19_db"
ROLE_NAME="OverdriveExecutionRole"
LF_ROLE_NAME="LakeFormationDataAccessRole"

echo "Using bucket: $BUCKET_NAME"
echo "Using database: $DATABASE_NAME"

# Step 1: Upload Glue scripts to S3
echo "Step 1: Uploading Glue scripts to S3..."
aws s3 cp glue_s3_list_job.py s3://$BUCKET_NAME/scripts/glue_s3_list_job.py
aws s3 cp glue_covid_summary_job.py s3://$BUCKET_NAME/scripts/glue_covid_summary_job.py
echo "✓ Scripts uploaded successfully"

# Step 2: Grant Lake Formation permissions for table creation
echo "Step 2: Granting Lake Formation permissions..."

# Grant CREATE_TABLE permission to OverdriveExecutionRole
aws lakeformation grant-permissions \
    --principal DataLakePrincipalIdentifier=arn:aws:iam::058264284947:role/$ROLE_NAME \
    --permissions CREATE_TABLE \
    --resource Database={Name=$DATABASE_NAME}

echo "✓ CREATE_TABLE permission granted to $ROLE_NAME"

# Step 3: Run the COVID summary job
echo "Step 3: Running COVID summary Glue job..."
JOB_RUN_ID=$(aws glue start-job-run \
    --job-name covid-summary-job \
    --query 'JobRunId' \
    --output text)

echo "✓ Job started with run ID: $JOB_RUN_ID"

# Step 4: Wait for job completion and check status
echo "Step 4: Monitoring job execution..."
while true; do
    JOB_STATUS=$(aws glue get-job-run \
        --job-name covid-summary-job \
        --run-id $JOB_RUN_ID \
        --query 'JobRun.JobRunState' \
        --output text)
    
    echo "Current job status: $JOB_STATUS"
    
    if [ "$JOB_STATUS" = "SUCCEEDED" ]; then
        echo "✓ Job completed successfully!"
        break
    elif [ "$JOB_STATUS" = "FAILED" ] || [ "$JOB_STATUS" = "ERROR" ] || [ "$JOB_STATUS" = "STOPPED" ]; then
        echo "✗ Job failed with status: $JOB_STATUS"
        
        # Get error details
        echo "Fetching error details..."
        aws glue get-job-run \
            --job-name covid-summary-job \
            --run-id $JOB_RUN_ID \
            --query 'JobRun.ErrorMessage' \
            --output text
        
        exit 1
    fi
    
    sleep 30
done

# Step 5: Verify table creation
echo "Step 5: Verifying table creation..."
TABLE_EXISTS=$(aws glue get-table \
    --database-name $DATABASE_NAME \
    --name covid_summary_results \
    --query 'Table.Name' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$TABLE_EXISTS" = "covid_summary_results" ]; then
    echo "✓ Table 'covid_summary_results' created successfully!"
    
    # Show table details
    echo "Table details:"
    aws glue get-table \
        --database-name $DATABASE_NAME \
        --name covid_summary_results \
        --query 'Table.{Name:Name,Location:StorageDescriptor.Location,InputFormat:StorageDescriptor.InputFormat}' \
        --output table
else
    echo "✗ Table 'covid_summary_results' was not created"
    exit 1
fi

# Step 6: List all tables in database
echo "Step 6: Listing all tables in database..."
aws glue get-tables \
    --database-name $DATABASE_NAME \
    --query 'TableList[].Name' \
    --output table

echo "=== Analytics Workflow Test Completed Successfully ==="

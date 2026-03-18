#!/bin/bash
# Deploy updated 07-glue-lf-test-data.yaml stackset with IAMPrincipals grants
# Run from org admin account (amirbo+1)
set -e

REGION="us-east-2"
STACKSET="SMUS-AccountPoolFactory-GlueLfTestData"
BUCKET="accountpoolfactory-templates-495869084367"
ADMIN_ROLE="arn:aws:iam::495869084367:role/SMUS-AccountPoolFactory-StackSetAdmin"
EXEC_ROLE="SMUS-AccountPoolFactory-StackSetExecution"
TEMPLATE_SRC="experimental/AccountPoolFactory/approved-stacksets/cloudformation/idc/07-glue-lf-test-data.yaml"
S3_KEY="stacksets/common/07-glue-lf-test-data.yaml"

echo "============================================================================="
echo "  Deploy updated StackSet: $STACKSET"
echo "  Timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================================="
echo ""

echo ">>> Switching to org admin account..."
eval $(isengardcli credentials amirbo+1@amazon.com)
aws sts get-caller-identity --region $REGION --output json
echo ""

echo ">>> Uploading template to S3..."
aws s3 cp "$TEMPLATE_SRC" "s3://${BUCKET}/${S3_KEY}" --region "$REGION"
echo ""

echo ">>> Listing current StackSet instances..."
aws cloudformation list-stack-instances \
    --stack-set-name "$STACKSET" \
    --region "$REGION" \
    --query 'Summaries[*].[Account,Region,Status,StackInstanceStatus.DetailedStatus]' \
    --output table
echo ""

echo ">>> Updating StackSet template..."
OP_ID=$(aws cloudformation update-stack-set \
    --stack-set-name "$STACKSET" \
    --template-url "https://${BUCKET}.s3.${REGION}.amazonaws.com/${S3_KEY}" \
    --administration-role-arn "$ADMIN_ROLE" \
    --execution-role-name "$EXEC_ROLE" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameters ParameterKey=DomainAccountId,ParameterValue=994753223772 ParameterKey=DomainId,ParameterValue=dzd-4h7jbz76qckoh5 \
    --region "$REGION" \
    --query 'OperationId' --output text)
echo "  Operation ID: $OP_ID"
echo ""

echo ">>> Waiting for StackSet update to complete..."
for i in $(seq 1 30); do
    sleep 10
    STATUS=$(aws cloudformation describe-stack-set-operation \
        --stack-set-name "$STACKSET" \
        --operation-id "$OP_ID" \
        --region "$REGION" \
        --query 'StackSetOperation.Status' --output text)
    echo "  [$((i*10))s] Status: $STATUS"
    if [ "$STATUS" = "SUCCEEDED" ] || [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "STOPPED" ]; then
        break
    fi
done
echo ""

if [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "STOPPED" ]; then
    echo ">>> StackSet update failed. Checking results..."
    aws cloudformation list-stack-set-operation-results \
        --stack-set-name "$STACKSET" \
        --operation-id "$OP_ID" \
        --region "$REGION" \
        --output json
    echo ""
fi

echo ">>> Final StackSet instance status..."
aws cloudformation list-stack-instances \
    --stack-set-name "$STACKSET" \
    --region "$REGION" \
    --query 'Summaries[*].[Account,Region,Status,StackInstanceStatus.DetailedStatus]' \
    --output table
echo ""

echo "============================================================================="
echo "  Done: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================================="

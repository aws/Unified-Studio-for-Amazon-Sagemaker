#!/bin/bash
eval $(isengardcli credentials amirbo+1@amazon.com)
STACKSET="SMUS-AccountPoolFactory-GlueLfTestData"
REGION="us-east-2"
BUCKET="accountpoolfactory-templates-495869084367"
TEMPLATE="experimental/AccountPoolFactory/templates/cloudformation/stacksets/idc/07-glue-lf-test-data.yaml"
ACCOUNT_ID="108750422936"

echo "Uploading fixed template..."
aws s3 cp "$TEMPLATE" "s3://${BUCKET}/stacksets/common/07-glue-lf-test-data.yaml" --region "$REGION"

echo "Updating StackSet with new template..."
aws cloudformation update-stack-set \
    --stack-set-name "$STACKSET" \
    --template-url "https://${BUCKET}.s3.${REGION}.amazonaws.com/stacksets/common/07-glue-lf-test-data.yaml" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameters ParameterKey=DomainAccountId,ParameterValue=994753223772 ParameterKey=DomainId,ParameterValue=dzd-4h7jbz76qckoh5 \
    --region "$REGION"

echo "Waiting 10s for update..."
sleep 10

echo "Deleting failed instance first..."
aws cloudformation delete-stack-instances \
    --stack-set-name "$STACKSET" \
    --accounts "$ACCOUNT_ID" \
    --regions "$REGION" \
    --no-retain-stacks \
    --region "$REGION" 2>&1 || true

echo "Waiting 30s for delete..."
sleep 30

echo "Creating fresh StackSet instance..."
OP_ID=$(aws cloudformation create-stack-instances \
    --stack-set-name "$STACKSET" \
    --accounts "$ACCOUNT_ID" \
    --regions "$REGION" \
    --operation-preferences MaxConcurrentCount=1 \
    --region "$REGION" \
    --query 'OperationId' --output text 2>&1)
echo "Operation ID: $OP_ID"

for i in $(seq 1 20); do
    sleep 15
    STATUS=$(aws cloudformation describe-stack-set-operation \
        --stack-set-name "$STACKSET" \
        --operation-id "$OP_ID" \
        --region "$REGION" \
        --query 'StackSetOperation.Status' --output text 2>&1)
    echo "[$((i*15))s] Status: $STATUS"
    if [ "$STATUS" = "SUCCEEDED" ] || [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "STOPPED" ]; then
        break
    fi
done
echo "Done: $STATUS"

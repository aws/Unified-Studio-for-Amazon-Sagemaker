#!/bin/bash
eval $(isengardcli credentials amirbo+1@amazon.com)
STACKSET="SMUS-AccountPoolFactory-GlueLfTestData"
REGION="us-east-2"
BUCKET="accountpoolfactory-templates-495869084367"
ADMIN_ROLE="arn:aws:iam::495869084367:role/SMUS-AccountPoolFactory-StackSetAdmin"
EXEC_ROLE="SMUS-AccountPoolFactory-StackSetExecution"
ACCOUNT_ID="108750422936"
TEMPLATE_URL="https://${BUCKET}.s3.${REGION}.amazonaws.com/stacksets/common/07-glue-lf-test-data.yaml"

echo "Step 1: Updating StackSet with fixed template..."
OP_ID=$(aws cloudformation update-stack-set \
    --stack-set-name "$STACKSET" \
    --template-url "$TEMPLATE_URL" \
    --administration-role-arn "$ADMIN_ROLE" \
    --execution-role-name "$EXEC_ROLE" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameters ParameterKey=DomainAccountId,ParameterValue=994753223772 ParameterKey=DomainId,ParameterValue=dzd-4h7jbz76qckoh5 \
    --region "$REGION" \
    --query 'OperationId' --output text 2>&1)
echo "Update OP: $OP_ID"

for i in $(seq 1 10); do
    sleep 10
    STATUS=$(aws cloudformation describe-stack-set-operation \
        --stack-set-name "$STACKSET" --operation-id "$OP_ID" \
        --region "$REGION" --query 'StackSetOperation.Status' --output text 2>&1)
    echo "[$((i*10))s] Update: $STATUS"
    if [ "$STATUS" = "SUCCEEDED" ] || [ "$STATUS" = "FAILED" ]; then break; fi
done

echo ""
echo "Step 2: Creating StackSet instance for $ACCOUNT_ID..."
OP_ID=$(aws cloudformation create-stack-instances \
    --stack-set-name "$STACKSET" \
    --accounts "$ACCOUNT_ID" \
    --regions "$REGION" \
    --operation-preferences MaxConcurrentCount=1 \
    --region "$REGION" \
    --query 'OperationId' --output text 2>&1)
echo "Create OP: $OP_ID"

for i in $(seq 1 20); do
    sleep 15
    STATUS=$(aws cloudformation describe-stack-set-operation \
        --stack-set-name "$STACKSET" --operation-id "$OP_ID" \
        --region "$REGION" --query 'StackSetOperation.Status' --output text 2>&1)
    echo "[$((i*15))s] Instance: $STATUS"
    if [ "$STATUS" = "SUCCEEDED" ] || [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "STOPPED" ]; then break; fi
done
echo "Done: $STATUS"

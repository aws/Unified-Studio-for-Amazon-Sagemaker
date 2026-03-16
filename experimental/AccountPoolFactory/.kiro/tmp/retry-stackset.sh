#!/bin/bash
eval $(isengardcli credentials amirbo+1@amazon.com)
STACKSET="SMUS-AccountPoolFactory-GlueLfTestData"
REGION="us-east-2"
BUCKET="accountpoolfactory-templates-495869084367"
ADMIN_ROLE="arn:aws:iam::495869084367:role/SMUS-AccountPoolFactory-StackSetAdmin"
EXEC_ROLE="SMUS-AccountPoolFactory-StackSetExecution"
ACCOUNT_ID="108750422936"
TEMPLATE="experimental/AccountPoolFactory/templates/cloudformation/stacksets/idc/07-glue-lf-test-data.yaml"
TEMPLATE_URL="https://${BUCKET}.s3.${REGION}.amazonaws.com/stacksets/common/07-glue-lf-test-data.yaml"

echo "Uploading fixed template..."
aws s3 cp "$TEMPLATE" "s3://${BUCKET}/stacksets/common/07-glue-lf-test-data.yaml" --region "$REGION"

echo "Deleting old instance..."
aws cloudformation delete-stack-instances --stack-set-name "$STACKSET" --accounts "$ACCOUNT_ID" --regions "$REGION" --no-retain-stacks --region "$REGION" 2>&1
echo "Waiting 30s..."
sleep 30

echo "Updating StackSet..."
aws cloudformation update-stack-set --stack-set-name "$STACKSET" --template-url "$TEMPLATE_URL" --administration-role-arn "$ADMIN_ROLE" --execution-role-name "$EXEC_ROLE" --capabilities CAPABILITY_NAMED_IAM --parameters ParameterKey=DomainAccountId,ParameterValue=994753223772 ParameterKey=DomainId,ParameterValue=dzd-4h7jbz76qckoh5 --region "$REGION" 2>&1
echo "Waiting 15s..."
sleep 15

echo "Creating instance..."
OP_ID=$(aws cloudformation create-stack-instances --stack-set-name "$STACKSET" --accounts "$ACCOUNT_ID" --regions "$REGION" --operation-preferences MaxConcurrentCount=1 --region "$REGION" --query 'OperationId' --output text 2>&1)
echo "OP: $OP_ID"
for i in $(seq 1 20); do
    sleep 15
    STATUS=$(aws cloudformation describe-stack-set-operation --stack-set-name "$STACKSET" --operation-id "$OP_ID" --region "$REGION" --query 'StackSetOperation.Status' --output text 2>&1)
    echo "[$((i*15))s] $STATUS"
    if [ "$STATUS" = "SUCCEEDED" ] || [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "STOPPED" ]; then break; fi
done
echo "Result: $STATUS"

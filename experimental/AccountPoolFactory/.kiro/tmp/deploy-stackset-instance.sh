#!/bin/bash
# Deploy StackSet 07 instance to one test account
eval $(isengardcli credentials amirbo+1@amazon.com)
ACCOUNT_ID="108750422936"
STACKSET="SMUS-AccountPoolFactory-GlueLfTestData"
REGION="us-east-2"

echo "Creating StackSet instance for $ACCOUNT_ID..."
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

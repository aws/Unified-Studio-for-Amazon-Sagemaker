#!/bin/bash
ACCOUNT_ID="242736648013"
STACKSET="SMUS-AccountPoolFactory-GlueLfTestData"
REGION="us-east-2"

# Step 1: Deploy StackSet instance (org admin)
eval $(isengardcli credentials amirbo+1@amazon.com)
echo "Deploying StackSet to $ACCOUNT_ID..."
OP_ID=$(aws cloudformation create-stack-instances --stack-set-name "$STACKSET" --accounts "$ACCOUNT_ID" --regions "$REGION" --operation-preferences MaxConcurrentCount=1 --region "$REGION" --query 'OperationId' --output text 2>&1)
echo "OP: $OP_ID"
for i in $(seq 1 20); do
    sleep 15
    STATUS=$(aws cloudformation describe-stack-set-operation --stack-set-name "$STACKSET" --operation-id "$OP_ID" --region "$REGION" --query 'StackSetOperation.Status' --output text 2>&1)
    echo "[$((i*15))s] $STATUS"
    if [ "$STATUS" = "SUCCEEDED" ] || [ "$STATUS" = "FAILED" ]; then break; fi
done
echo "StackSet: $STATUS"

# Step 2: Grant LF permissions (domain account)
eval $(isengardcli credentials amirbo+3@amazon.com)
echo "Granting LF permissions..."
bash experimental/AccountPoolFactory/.kiro/tmp/grant-lf-to-account.sh "$ACCOUNT_ID"

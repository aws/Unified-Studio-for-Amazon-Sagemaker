#!/bin/bash
# Add Bedrock InvokeAgent permissions to SageMaker execution role
# This allows notebooks to invoke Bedrock agents

set -e

ROLE_NAME="AmazonSageMakerUserIAMExecutionRole"
POLICY_NAME="BedrockInvokeAgentPolicy"

echo "Adding Bedrock InvokeAgent policy to role: $ROLE_NAME"

# Create the policy document
POLICY_DOC='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeAgent",
        "bedrock:InvokeModel",
        "bedrock:GetAgent",
        "bedrock:ListAgents"
      ],
      "Resource": "*"
    }
  ]
}'

# Add the inline policy
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "$POLICY_NAME" \
  --policy-document "$POLICY_DOC"

echo "✅ Successfully added $POLICY_NAME to $ROLE_NAME"
echo ""
echo "Policy allows:"
echo "  - bedrock:InvokeAgent"
echo "  - bedrock:InvokeModel"
echo "  - bedrock:GetAgent"
echo "  - bedrock:ListAgents"

#!/bin/bash

# Add inline policy to allow passing DEFAULT_AgentExecutionRole to Bedrock

ROLE_NAME="AmazonSageMakerUserIAMExecutionRole"
POLICY_NAME="BedrockAgentPassRolePolicy"

echo "Adding inline policy to ${ROLE_NAME}..."

aws iam put-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-name "${POLICY_NAME}" \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": "iam:PassRole",
        "Resource": "arn:aws:iam::*:role/DEFAULT_AgentExecutionRole",
        "Condition": {
          "StringEquals": {
            "iam:PassedToService": "bedrock.amazonaws.com"
          }
        }
      }
    ]
  }'

echo "Policy added successfully!"

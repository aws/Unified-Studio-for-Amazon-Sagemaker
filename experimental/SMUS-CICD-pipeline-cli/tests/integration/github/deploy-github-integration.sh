#!/bin/bash

set -e

STACK_NAME="smus-cli-github-integration"
TEMPLATE_FILE="github-oidc-role.yaml"
REGION="${AWS_REGION:-us-east-1}"

echo "Deploying GitHub OIDC integration stack..."

aws cloudformation deploy \
    --template-file "$TEMPLATE_FILE" \
    --stack-name "$STACK_NAME" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    --parameter-overrides \
        GitHubOrg="${GITHUB_ORG:-aws}" \
        GitHubRepo="${GITHUB_REPO:-Unified-Studio-for-Amazon-Sagemaker}"

echo "Stack deployed successfully!"

# Get the role ARN
ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`RoleArn`].OutputValue' \
    --output text)

echo "GitHub Actions Role ARN: $ROLE_ARN"
echo "Add this to your GitHub repository secrets as AWS_ROLE_ARN"

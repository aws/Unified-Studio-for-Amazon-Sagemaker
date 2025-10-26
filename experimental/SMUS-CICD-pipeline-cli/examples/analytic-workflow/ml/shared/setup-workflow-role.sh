#!/bin/bash

# Setup script to configure OverdriveExecutionRole with SageMaker and MLflow permissions

set -e

ROLE_NAME="OverdriveExecutionRole"
POLICY_NAME="SageMakerMLflowPolicy"

echo "=== Setting up OverdriveExecutionRole for SageMaker and MLflow ==="

# Check if role exists
if aws iam get-role --role-name $ROLE_NAME >/dev/null 2>&1; then
    echo "✓ Role $ROLE_NAME exists"
else
    echo "Creating role $ROLE_NAME..."
    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file://workflow-trust-policy.json
    echo "✓ Role created"
fi

# Update trust policy
echo "Updating trust policy..."
aws iam update-assume-role-policy \
    --role-name $ROLE_NAME \
    --policy-document file://workflow-trust-policy.json
echo "✓ Trust policy updated"

# Create/update inline policy
echo "Creating/updating SageMaker MLflow policy..."
aws iam put-role-policy \
    --role-name $ROLE_NAME \
    --policy-name $POLICY_NAME \
    --policy-document file://workflow-sagemaker-policy.json
echo "✓ Policy attached"

# Attach AWS managed policies
echo "Attaching AWS managed policies..."
aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonSageMakerServiceRolePolicy || true

aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --policy-arn arn:aws:iam::aws:policy/service-role/GlueServiceRole || true

echo "✓ AWS managed policies attached"

# Get role ARN
ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text)
echo ""
echo "=== Setup Complete ==="
echo "Role ARN: $ROLE_ARN"
echo ""
echo "The OverdriveExecutionRole now has permissions for:"
echo "- SageMaker training jobs, models, endpoints, transform jobs"
echo "- S3 access for SageMaker and MLflow buckets"
echo "- ECR access for SageMaker containers"
echo "- CloudWatch logs for SageMaker"
echo "- MLflow database and secrets access"
echo "- Glue job execution"

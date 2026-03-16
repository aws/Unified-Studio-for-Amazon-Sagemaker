#!/bin/bash
# Deploy Control Tower Account Factory Setup (CF1)
# This script deploys the CF1 CloudFormation template to the Organization Admin account

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Load configuration
CONFIG_FILE="${PROJECT_ROOT}/config.yaml"

if [ ! -f "${CONFIG_FILE}" ]; then
    echo "Error: Configuration file not found: ${CONFIG_FILE}"
    echo "Please copy config.yaml.template to config.yaml and configure it."
    exit 1
fi

# Parse configuration using yq (preferred) or fallback to grep/sed
if command -v yq &> /dev/null; then
    AWS_REGION=$(yq eval '.aws.region' "${CONFIG_FILE}")
    AWS_ACCOUNT_ID=$(yq eval '.aws.account_id' "${CONFIG_FILE}")
    REQUESTING_ACCOUNT_ID=$(yq eval '.aws.account_id' "${CONFIG_FILE}")  # Same account for testing
    PROJECT_TAG=$(yq eval '.tags.Project' "${CONFIG_FILE}")
    ENVIRONMENT_TAG=$(yq eval '.tags.Environment' "${CONFIG_FILE}")
    OWNER_TAG=$(yq eval '.tags.Owner' "${CONFIG_FILE}")
else
    echo "Warning: yq not found, using grep/sed fallback"
    AWS_REGION=$(grep 'region:' "${CONFIG_FILE}" | head -1 | sed 's/.*region: *//' | tr -d '"')
    AWS_ACCOUNT_ID=$(grep 'account_id:' "${CONFIG_FILE}" | head -1 | sed 's/.*account_id: *//' | tr -d '"')
    REQUESTING_ACCOUNT_ID="${AWS_ACCOUNT_ID}"  # Same account for testing
    PROJECT_TAG=$(grep 'Project:' "${CONFIG_FILE}" | head -1 | sed 's/.*Project: *//' | tr -d '"')
    ENVIRONMENT_TAG=$(grep 'Environment:' "${CONFIG_FILE}" | head -1 | sed 's/.*Environment: *//' | tr -d '"')
    OWNER_TAG=$(grep 'Owner:' "${CONFIG_FILE}" | head -1 | sed 's/.*Owner: *//' | tr -d '"')
fi

# Stack name
STACK_NAME="AccountPoolFactory-ControlTower-${ENVIRONMENT_TAG}"

# Template path
TEMPLATE_PATH="${PROJECT_ROOT}/01-org-account/templates/cloudformation/SMUS-AccountPoolFactory-OrgAdmin.yaml"

if [ ! -f "${TEMPLATE_PATH}" ]; then
    echo "Error: CloudFormation template not found: ${TEMPLATE_PATH}"
    exit 1
fi

echo "=========================================="
echo "Control Tower Account Factory Setup (CF1)"
echo "=========================================="
echo "Region: ${AWS_REGION}"
echo "Org Admin Account: ${AWS_ACCOUNT_ID}"
echo "Requesting Account: ${REQUESTING_ACCOUNT_ID}"
echo "Stack Name: ${STACK_NAME}"
echo "Template: ${TEMPLATE_PATH}"
echo "=========================================="
echo ""

# Check if stack exists
if aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" &> /dev/null; then
    
    echo "Stack ${STACK_NAME} already exists. Updating..."
    
    # Update stack
    aws cloudformation update-stack \
        --stack-name "${STACK_NAME}" \
        --template-body "file://${TEMPLATE_PATH}" \
        --parameters \
            ParameterKey=RequestingAccountId,ParameterValue="${REQUESTING_ACCOUNT_ID}" \
            ParameterKey=RequestingAccountRoleName,ParameterValue="AccountPoolFactoryAccountCreatorRole" \
            ParameterKey=EventBusName,ParameterValue="AccountPoolFactoryEventBus" \
            ParameterKey=EnableEventForwarding,ParameterValue="true" \
            ParameterKey=ProjectTag,ParameterValue="${PROJECT_TAG}" \
            ParameterKey=EnvironmentTag,ParameterValue="${ENVIRONMENT_TAG}" \
            ParameterKey=OwnerTag,ParameterValue="${OWNER_TAG}" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "${AWS_REGION}"
    
    echo ""
    echo "Waiting for stack update to complete..."
    aws cloudformation wait stack-update-complete \
        --stack-name "${STACK_NAME}" \
        --region "${AWS_REGION}"
    
    echo "✓ Stack updated successfully"
else
    echo "Creating new stack ${STACK_NAME}..."
    
    # Create stack
    aws cloudformation create-stack \
        --stack-name "${STACK_NAME}" \
        --template-body "file://${TEMPLATE_PATH}" \
        --parameters \
            ParameterKey=RequestingAccountId,ParameterValue="${REQUESTING_ACCOUNT_ID}" \
            ParameterKey=RequestingAccountRoleName,ParameterValue="AccountPoolFactoryAccountCreatorRole" \
            ParameterKey=EventBusName,ParameterValue="AccountPoolFactoryEventBus" \
            ParameterKey=EnableEventForwarding,ParameterValue="true" \
            ParameterKey=ProjectTag,ParameterValue="${PROJECT_TAG}" \
            ParameterKey=EnvironmentTag,ParameterValue="${ENVIRONMENT_TAG}" \
            ParameterKey=OwnerTag,ParameterValue="${OWNER_TAG}" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "${AWS_REGION}"
    
    echo ""
    echo "Waiting for stack creation to complete..."
    aws cloudformation wait stack-create-complete \
        --stack-name "${STACK_NAME}" \
        --region "${AWS_REGION}"
    
    echo "✓ Stack created successfully"
fi

echo ""
echo "=========================================="
echo "Stack Outputs"
echo "=========================================="

# Get stack outputs
aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

# Save outputs to file
OUTPUT_FILE="${PROJECT_ROOT}/cf1-outputs.json"
aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query 'Stacks[0].Outputs' \
    --output json > "${OUTPUT_FILE}"

echo ""
echo "✓ Stack outputs saved to: ${OUTPUT_FILE}"

# Update config.yaml with CF1 stack name
if command -v yq &> /dev/null; then
    yq eval ".stacks.control_tower = \"${STACK_NAME}\"" -i "${CONFIG_FILE}"
    echo "✓ Updated config.yaml with CF1 stack name"
fi

echo ""
echo "=========================================="
echo "Deployment Complete"
echo "=========================================="
echo ""
echo "Next Steps:"
echo "1. Review the stack outputs in ${OUTPUT_FILE}"
echo "2. Note the AccountCreationRoleArn for CF2 deployment"
echo "3. Proceed to Step 3: Deploy CF2 (Domain Account Setup)"
echo ""

#!/bin/bash
set -e

if [ $# -ne 1 ]; then
    echo "Usage: $0 <project-role-name>"
    echo "Example: $0 test-marketing-role"
    exit 1
fi

PROJECT_ROLE_NAME=$1
STACK_NAME="SMUS-Stage-Roles-${PROJECT_ROLE_NAME}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_PATH="$SCRIPT_DIR/stage-roles.yaml"

echo "Creating/updating CloudFormation stack: $STACK_NAME"
echo "Project Role: $PROJECT_ROLE_NAME"

aws cloudformation deploy \
    --template-file "$TEMPLATE_PATH" \
    --stack-name "$STACK_NAME" \
    --parameter-overrides ProjectRoleName="$PROJECT_ROLE_NAME" \
    --capabilities CAPABILITY_NAMED_IAM \
    --no-fail-on-empty-changeset

echo ""
echo "Stack outputs:"
aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs' \
    --output table

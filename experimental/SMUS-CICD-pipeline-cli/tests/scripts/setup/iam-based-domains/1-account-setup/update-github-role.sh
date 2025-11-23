#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_NAME="smus-cli-github-integration"
TEMPLATE_FILE="$SCRIPT_DIR/github-oidc-role.yaml"
REGION="${AWS_REGION:-us-east-1}"

echo "=== Updating GitHub OIDC Role Stack ==="
echo "Stack: $STACK_NAME"
echo "Region: $REGION"
echo "Template: $TEMPLATE_FILE"
echo

# Verify we're in the right account
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Current Account: $ACCOUNT_ID"

if [ "$ACCOUNT_ID" != "198737698272" ]; then
    echo "⚠️  WARNING: Expected account 198737698272 but got $ACCOUNT_ID"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "Updating stack with new IAM permissions..."
aws cloudformation deploy \
    --template-file "$TEMPLATE_FILE" \
    --stack-name "$STACK_NAME" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION"

echo
echo "✅ Stack update complete!"
echo
echo "Added permissions:"
echo "  - iam:ListAttachedRolePolicies"
echo "  - iam:DeleteRole"
echo "  - iam:DetachRolePolicy"
echo "  - iam:DeleteRolePolicy"
echo
echo "These permissions allow integration tests to:"
echo "  - Create and configure project IAM roles"
echo "  - Clean up roles after tests complete"

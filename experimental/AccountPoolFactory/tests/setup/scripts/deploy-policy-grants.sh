#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

CONFIG_FILE="$PROJECT_ROOT/config.yaml"

# Parse configuration
read -r DOMAIN_ID REGION ROOT_DOMAIN_UNIT < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['region'], config['datazone']['root_domain_unit_id'])
EOF
)

TARGET_ACCOUNT="004878717744"
STACK_NAME="DataZone-PolicyGrants-Account-$TARGET_ACCOUNT"

echo "=== Deploying Policy Grants for Account $TARGET_ACCOUNT ==="
echo "Domain ID: $DOMAIN_ID"
echo "Root Domain Unit: $ROOT_DOMAIN_UNIT"
echo "Region: $REGION"
echo ""

# Get blueprint IDs from target account
echo "Step 1: Getting blueprint IDs from account $TARGET_ACCOUNT..."

# Get org admin credentials
eval "$(isengardcli creds amirbo+1 --role Admin)"

# Assume role in target account
CREDS=$(aws sts assume-role \
  --role-arn "arn:aws:iam::$TARGET_ACCOUNT:role/OrganizationAccountAccessRole" \
  --role-session-name "GetBlueprints" \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text)

export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | awk '{print $1}')
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | awk '{print $2}')
export AWS_SESSION_TOKEN=$(echo "$CREDS" | awk '{print $3}')

# Get all blueprints
BLUEPRINTS=$(aws datazone list-environment-blueprint-configurations \
  --domain-identifier "$DOMAIN_ID" \
  --region "$REGION" \
  --output json | jq -r '.items[] | .environmentBlueprintId')

echo "Found $(echo "$BLUEPRINTS" | wc -l | tr -d ' ') blueprints"
echo ""

# Switch to domain account
echo "Step 2: Deploying policy grants in domain account..."
eval "$(isengardcli creds amirbo+3 --role Admin)"

# Create CloudFormation template dynamically
TEMPLATE=$(cat <<'TEMPLATE_EOF'
AWSTemplateFormatVersion: 2010-09-09
Description: Policy grants for account blueprints
Transform: AWS::LanguageExtensions

Parameters:
  DomainId:
    Type: String
  AccountId:
    Type: String
  DomainUnitId:
    Type: String
  BlueprintIds:
    Type: CommaDelimitedList

Resources:
  'Fn::ForEach::PolicyGrants':
    - BlueprintId
    - !Ref BlueprintIds
    - 'PolicyGrant${BlueprintId}':
        Type: AWS::DataZone::PolicyGrant
        Properties:
          DomainIdentifier: !Ref DomainId
          EntityType: ENVIRONMENT_BLUEPRINT_CONFIGURATION
          EntityIdentifier: !Sub '${AccountId}:${BlueprintId}'
          PolicyType: CREATE_ENVIRONMENT_FROM_BLUEPRINT
          Detail:
            CreateEnvironmentFromBlueprint: {}
          Principal:
            Project:
              ProjectDesignation: CONTRIBUTOR
              ProjectGrantFilter:
                DomainUnitFilter:
                  DomainUnit: !Ref DomainUnitId
                  IncludeChildDomainUnits: true
TEMPLATE_EOF
)

# Convert blueprint IDs to comma-separated list
BLUEPRINT_LIST=$(echo "$BLUEPRINTS" | tr '\n' ',' | sed 's/,$//')

echo "$TEMPLATE" > /tmp/policy-grants-template.yaml

# Deploy stack
aws cloudformation create-stack \
  --stack-name "$STACK_NAME" \
  --template-body file:///tmp/policy-grants-template.yaml \
  --parameters \
    "ParameterKey=DomainId,ParameterValue=$DOMAIN_ID" \
    "ParameterKey=AccountId,ParameterValue=$TARGET_ACCOUNT" \
    "ParameterKey=DomainUnitId,ParameterValue=$ROOT_DOMAIN_UNIT" \
    "ParameterKey=BlueprintIds,ParameterValue=\"$BLUEPRINT_LIST\"" \
  --region "$REGION" \
  --capabilities CAPABILITY_AUTO_EXPAND

echo "Waiting for stack creation..."
aws cloudformation wait stack-create-complete \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

echo ""
echo "✅ Policy grants deployed successfully!"
echo ""
echo "Projects can now create environments from all blueprints in account $TARGET_ACCOUNT"

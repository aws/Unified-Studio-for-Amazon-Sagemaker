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

PROJECT_ACCOUNT="004878717744"
STACK_NAME="DataZone-PolicyGrants"

echo "=== Deploying Policy Grants in Project Account $PROJECT_ACCOUNT ==="
echo "Domain ID: $DOMAIN_ID"
echo "Root Domain Unit: $ROOT_DOMAIN_UNIT"
echo "Region: $REGION"
echo ""

# Step 1: Get blueprint IDs from project account
echo "Step 1: Getting blueprint IDs from project account..."

eval "$(isengardcli creds amirbo+1 --role Admin)"
CREDS=$(aws sts assume-role \
  --role-arn "arn:aws:iam::$PROJECT_ACCOUNT:role/OrganizationAccountAccessRole" \
  --role-session-name "DeployPolicyGrants" \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text)

export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | awk '{print $1}')
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | awk '{print $2}')
export AWS_SESSION_TOKEN=$(echo "$CREDS" | awk '{print $3}')

BLUEPRINTS=$(aws datazone list-environment-blueprint-configurations \
  --domain-identifier "$DOMAIN_ID" \
  --region "$REGION" \
  --output json | jq -r '.items[].environmentBlueprintId')

BLUEPRINT_COUNT=$(echo "$BLUEPRINTS" | wc -l | tr -d ' ')
echo "Found $BLUEPRINT_COUNT blueprints"
echo ""

# Step 2: Create CloudFormation template with policy grants
echo "Step 2: Creating policy grants template..."

# Build parameter declarations and resource list
PARAM_DECLARATIONS=""
BLUEPRINT_REFS=""
COUNTER=1

while IFS= read -r blueprint_id; do
  PARAM_DECLARATIONS="${PARAM_DECLARATIONS}  Blueprint${COUNTER}Id:
    Type: String
    Default: \"${blueprint_id}\"
"
  if [ -z "$BLUEPRINT_REFS" ]; then
    BLUEPRINT_REFS="!Ref Blueprint${COUNTER}Id"
  else
    BLUEPRINT_REFS="${BLUEPRINT_REFS}
            - !Ref Blueprint${COUNTER}Id"
  fi
  COUNTER=$((COUNTER + 1))
done <<< "$BLUEPRINTS"

cat > /tmp/policy-grants-project.yaml <<TEMPLATE_START
AWSTemplateFormatVersion: 2010-09-09
Description: Policy grants for project account blueprints
Transform: AWS::LanguageExtensions

Parameters:
  DomainId:
    Type: String
  AccountId:
    Type: String
  DomainUnitId:
    Type: String
${PARAM_DECLARATIONS}

Resources:
  'Fn::ForEach::PolicyGrants':
    - BlueprintId
    -
            - ${BLUEPRINT_REFS}
    - 'PolicyGrant\${BlueprintId}':
        Type: AWS::DataZone::PolicyGrant
        Properties:
          DomainIdentifier: !Ref DomainId
          EntityType: ENVIRONMENT_BLUEPRINT_CONFIGURATION
          EntityIdentifier: !Sub '\${AccountId}:\${BlueprintId}'
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
TEMPLATE_START

echo "Template created at /tmp/policy-grants-project.yaml"
echo ""

# Step 3: Deploy stack in project account (already authenticated)
echo "Step 3: Deploying policy grants stack in project account..."

aws cloudformation create-stack \
  --stack-name "$STACK_NAME" \
  --template-body file:///tmp/policy-grants-project.yaml \
  --parameters \
    "ParameterKey=DomainId,ParameterValue=$DOMAIN_ID" \
    "ParameterKey=AccountId,ParameterValue=$PROJECT_ACCOUNT" \
    "ParameterKey=DomainUnitId,ParameterValue=$ROOT_DOMAIN_UNIT" \
  --region "$REGION" \
  --capabilities CAPABILITY_AUTO_EXPAND

echo "Waiting for stack creation..."
aws cloudformation wait stack-create-complete \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

echo ""
echo "✅ Policy grants deployed successfully in project account!"
echo ""

# Step 4: Verify policy grants were created
echo "Step 4: Verifying policy grants..."
SAMPLE_BLUEPRINT=$(echo "$BLUEPRINTS" | head -1)

GRANT_COUNT=$(aws datazone list-policy-grants \
  --domain-identifier "$DOMAIN_ID" \
  --entity-type ENVIRONMENT_BLUEPRINT_CONFIGURATION \
  --entity-identifier "$PROJECT_ACCOUNT:$SAMPLE_BLUEPRINT" \
  --policy-type CREATE_ENVIRONMENT_FROM_BLUEPRINT \
  --region "$REGION" \
  --output json | jq '.grantList | length')

echo "Sample blueprint $SAMPLE_BLUEPRINT has $GRANT_COUNT grant(s)"

# Step 5: Check if provisioningConfigurationDomainUnitId is now set
echo ""
echo "Step 5: Checking provisioningConfigurationDomainUnitId..."
DOMAIN_UNIT_ID=$(aws datazone get-environment-blueprint-configuration \
  --domain-identifier "$DOMAIN_ID" \
  --environment-blueprint-identifier "$SAMPLE_BLUEPRINT" \
  --region "$REGION" \
  --output json | jq -r '.provisioningConfigurationDomainUnitId // "null"')

echo "provisioningConfigurationDomainUnitId: $DOMAIN_UNIT_ID"

if [ "$DOMAIN_UNIT_ID" = "null" ]; then
  echo "⚠️  WARNING: provisioningConfigurationDomainUnitId is still null"
  echo "This may indicate the grants were not applied correctly"
else
  echo "✅ provisioningConfigurationDomainUnitId is set correctly!"
fi

echo ""
echo "Projects in domain unit $ROOT_DOMAIN_UNIT can now create environments from all blueprints in account $PROJECT_ACCOUNT"

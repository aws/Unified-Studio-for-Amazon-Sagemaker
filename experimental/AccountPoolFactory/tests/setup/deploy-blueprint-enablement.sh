#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

CONFIG_FILE="$PROJECT_ROOT/config.yaml"

# Parse configuration
read -r DOMAIN_ID REGION < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['region'])
EOF
)

TARGET_ACCOUNT="004878717744"
STACK_NAME="DataZone-Blueprint-Enablement"

echo "=== Deploying Blueprint Enablement to account $TARGET_ACCOUNT ==="
echo "Domain ID: $DOMAIN_ID"
echo "Region: $REGION"
echo ""

# Get VPC and IAM role outputs
echo "Step 1: Getting VPC and IAM outputs..."

# Assume role in target account
CREDS=$(aws sts assume-role \
  --role-arn "arn:aws:iam::$TARGET_ACCOUNT:role/OrganizationAccountAccessRole" \
  --role-session-name "DeployBlueprints" \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text)

export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | awk '{print $1}')
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | awk '{print $2}')
export AWS_SESSION_TOKEN=$(echo "$CREDS" | awk '{print $3}')

# Get VPC outputs
VPC_STACK=$(aws cloudformation list-stacks \
  --region "$REGION" \
  --query 'StackSummaries[?contains(StackName, `VPCSetup`) && StackStatus==`CREATE_COMPLETE`].StackName' \
  --output text | head -1)

VPC_OUTPUTS=$(aws cloudformation describe-stacks \
  --stack-name "$VPC_STACK" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs' \
  --output json)

VPC_ID=$(echo "$VPC_OUTPUTS" | jq -r '.[] | select(.OutputKey=="VpcId") | .OutputValue')
PRIVATE_SUBNETS=$(echo "$VPC_OUTPUTS" | jq -r '.[] | select(.OutputKey=="PrivateSubnets") | .OutputValue')
S3_BUCKET=$(echo "$VPC_OUTPUTS" | jq -r '.[] | select(.OutputKey=="S3BucketName") | .OutputValue // empty')

# Ensure S3_BUCKET has a default value if empty
if [ -z "$S3_BUCKET" ]; then
  S3_BUCKET="s3://datazone-blueprints-$TARGET_ACCOUNT-$REGION"
fi

# Get IAM outputs
IAM_OUTPUTS=$(aws cloudformation describe-stacks \
  --stack-name "DataZone-IAM-Roles" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs' \
  --output json)

MANAGE_ROLE=$(echo "$IAM_OUTPUTS" | jq -r '.[] | select(.OutputKey=="ManageAccessRoleArn") | .OutputValue')
PROVISIONING_ROLE=$(echo "$IAM_OUTPUTS" | jq -r '.[] | select(.OutputKey=="ProvisioningRoleArn") | .OutputValue')

echo "  VPC ID: $VPC_ID"
echo "  Subnets: $PRIVATE_SUBNETS"
echo "  S3 Bucket: $S3_BUCKET"
echo "  Manage Role: $MANAGE_ROLE"
echo "  Provisioning Role: $PROVISIONING_ROLE"
echo ""

# Deploy blueprint enablement
echo "Step 2: Deploying Blueprint Enablement..."
aws cloudformation create-stack \
  --stack-name "$STACK_NAME" \
  --template-body file://"$PROJECT_ROOT/approved-stacksets/cloudformation/idc/06-blueprint-enablement.yaml" \
  --parameters \
    "ParameterKey=DomainId,ParameterValue=$DOMAIN_ID" \
    "ParameterKey=ManageAccessRoleArn,ParameterValue=$MANAGE_ROLE" \
    "ParameterKey=ProvisioningRoleArn,ParameterValue=$PROVISIONING_ROLE" \
    "ParameterKey=S3Location,ParameterValue=$S3_BUCKET" \
    "ParameterKey=Subnets,ParameterValue=\"$PRIVATE_SUBNETS\"" \
    "ParameterKey=VpcId,ParameterValue=$VPC_ID" \
  --region "$REGION"

echo "Waiting for stack creation (this may take 5-10 minutes)..."
aws cloudformation wait stack-create-complete \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

echo ""
echo "✅ Blueprint Enablement deployed successfully!"
echo ""
echo "Account $TARGET_ACCOUNT is now ready for DataZone project creation!"

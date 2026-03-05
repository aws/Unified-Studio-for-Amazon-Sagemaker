#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

CONFIG_FILE="$PROJECT_ROOT/config.yaml"

# Parse configuration
read -r DOMAIN_ID REGION DOMAIN_ACCOUNT < <(python3 - <<EOF
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
print(config['datazone']['domain_id'], config['aws']['region'], config['aws']['domain_account_id'])
EOF
)

TARGET_ACCOUNT="004878717744"
STACKSET_IAM="AccountPoolFactory-ControlTower-Test-IAMRoles"
STACKSET_BLUEPRINT="AccountPoolFactory-ControlTower-Test-BlueprintEnablement"

echo "=== Deploying Account Setup to $TARGET_ACCOUNT ==="
echo "Domain ID: $DOMAIN_ID"
echo "Domain Account: $DOMAIN_ACCOUNT"
echo "Region: $REGION"
echo ""

# Step 1: Get VPC outputs from existing VPC StackSet
echo "Step 1: Getting VPC outputs..."

# Assume role in target account to get stack outputs
CREDS=$(aws sts assume-role \
  --role-arn "arn:aws:iam::$TARGET_ACCOUNT:role/OrganizationAccountAccessRole" \
  --role-session-name "GetVPCOutputs" \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text)

export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | awk '{print $1}')
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | awk '{print $2}')
export AWS_SESSION_TOKEN=$(echo "$CREDS" | awk '{print $3}')

VPC_STACK_NAME=$(aws cloudformation list-stacks \
  --region "$REGION" \
  --query 'StackSummaries[?contains(StackName, `AccountPoolFactory-ControlTower-Test-VPCSetup`) && StackStatus==`CREATE_COMPLETE`].StackName' \
  --output text | head -1)

echo "VPC Stack Name: $VPC_STACK_NAME"

VPC_OUTPUTS=$(aws cloudformation describe-stacks \
  --stack-name "$VPC_STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs' \
  --output json)

VPC_ID=$(echo "$VPC_OUTPUTS" | jq -r '.[] | select(.OutputKey=="VpcId") | .OutputValue')
PRIVATE_SUBNETS=$(echo "$VPC_OUTPUTS" | jq -r '.[] | select(.OutputKey=="PrivateSubnets") | .OutputValue')
S3_LOCATION=$(echo "$VPC_OUTPUTS" | jq -r '.[] | select(.OutputKey=="S3BucketName") | .OutputValue')

# Switch back to org admin credentials
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
eval "$(isengardcli creds amirbo+1 --role Admin)"

echo "  VPC ID: $VPC_ID"
echo "  Private Subnets: $PRIVATE_SUBNETS"
echo "  S3 Location: $S3_LOCATION"
echo ""

# Step 2: Deploy IAM Roles StackSet
echo "Step 2: Deploying IAM Roles StackSet..."
aws cloudformation create-stack-instances \
  --stack-set-name "$STACKSET_IAM" \
  --accounts "$TARGET_ACCOUNT" \
  --regions "$REGION" \
  --operation-preferences FailureToleranceCount=0,MaxConcurrentCount=1 \
  --region "$REGION"

echo "  Waiting for IAM Roles deployment..."
aws cloudformation wait stack-create-complete \
  --stack-name "StackSet-$STACKSET_IAM-*" \
  --region "$REGION" 2>/dev/null || true

# Wait and check status
for i in {1..60}; do
  STATUS=$(aws cloudformation describe-stack-instance \
    --stack-set-name "$STACKSET_IAM" \
    --stack-instance-account "$TARGET_ACCOUNT" \
    --stack-instance-region "$REGION" \
    --region "$REGION" \
    --query 'StackInstance.Status' \
    --output text 2>/dev/null || echo "PENDING")
  
  echo "  Attempt $i/60: Status = $STATUS"
  
  if [ "$STATUS" = "CURRENT" ]; then
    echo "✅ IAM Roles deployed successfully!"
    break
  elif [ "$STATUS" = "FAILED" ]; then
    echo "❌ IAM Roles deployment failed!"
    exit 1
  fi
  
  sleep 5
done

echo ""

# Step 3: Get IAM Role outputs
echo "Step 3: Getting IAM Role outputs..."

# Assume role in target account to get IAM outputs
CREDS=$(aws sts assume-role \
  --role-arn "arn:aws:iam::$TARGET_ACCOUNT:role/OrganizationAccountAccessRole" \
  --role-session-name "GetIAMOutputs" \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text)

export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | awk '{print $1}')
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | awk '{print $2}')
export AWS_SESSION_TOKEN=$(echo "$CREDS" | awk '{print $3}')

IAM_STACK_NAME=$(aws cloudformation list-stacks \
  --region "$REGION" \
  --query 'StackSummaries[?contains(StackName, `AccountPoolFactory-ControlTower-Test-IAMRoles`) && StackStatus==`CREATE_COMPLETE`].StackName' \
  --output text | head -1)

IAM_OUTPUTS=$(aws cloudformation describe-stacks \
  --stack-name "$IAM_STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs' \
  --output json)

MANAGE_ROLE=$(echo "$IAM_OUTPUTS" | jq -r '.[] | select(.OutputKey=="ManageAccessRoleArn") | .OutputValue')
PROVISIONING_ROLE=$(echo "$IAM_OUTPUTS" | jq -r '.[] | select(.OutputKey=="ProvisioningRoleArn") | .OutputValue')

# Switch back to org admin credentials
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
eval "$(isengardcli creds amirbo+1 --role Admin)"

echo "  Manage Access Role: $MANAGE_ROLE"
echo "  Provisioning Role: $PROVISIONING_ROLE"
echo ""

# Step 4: Deploy Blueprint Enablement StackSet
echo "Step 4: Deploying Blueprint Enablement StackSet..."
aws cloudformation create-stack-instances \
  --stack-set-name "$STACKSET_BLUEPRINT" \
  --accounts "$TARGET_ACCOUNT" \
  --regions "$REGION" \
  --parameter-overrides \
    ParameterKey=DomainId,ParameterValue="$DOMAIN_ID" \
    ParameterKey=ManageAccessRoleArn,ParameterValue="$MANAGE_ROLE" \
    ParameterKey=ProvisioningRoleArn,ParameterValue="$PROVISIONING_ROLE" \
    ParameterKey=S3Location,ParameterValue="$S3_LOCATION" \
    ParameterKey=Subnets,ParameterValue="$PRIVATE_SUBNETS" \
    ParameterKey=VpcId,ParameterValue="$VPC_ID" \
  --operation-preferences FailureToleranceCount=0,MaxConcurrentCount=1 \
  --region "$REGION"

echo "  Waiting for Blueprint Enablement deployment..."

# Wait and check status
for i in {1..120}; do
  STATUS=$(aws cloudformation describe-stack-instance \
    --stack-set-name "$STACKSET_BLUEPRINT" \
    --stack-instance-account "$TARGET_ACCOUNT" \
    --stack-instance-region "$REGION" \
    --region "$REGION" \
    --query 'StackInstance.Status' \
    --output text 2>/dev/null || echo "PENDING")
  
  echo "  Attempt $i/120: Status = $STATUS"
  
  if [ "$STATUS" = "CURRENT" ]; then
    echo "✅ Blueprint Enablement deployed successfully!"
    break
  elif [ "$STATUS" = "FAILED" ]; then
    echo "❌ Blueprint Enablement deployment failed!"
    
    # Get failure reason
    aws cloudformation describe-stack-instance \
      --stack-set-name "$STACKSET_BLUEPRINT" \
      --stack-instance-account "$TARGET_ACCOUNT" \
      --stack-instance-region "$REGION" \
      --region "$REGION" \
      --query 'StackInstance.StatusReason' \
      --output text
    
    exit 1
  fi
  
  sleep 10
done

echo ""
echo "=== Account Setup Complete ==="
echo "Account: $TARGET_ACCOUNT"
echo "IAM Roles: ✅"
echo "Blueprint Enablement: ✅"
echo ""
echo "Account is now ready for DataZone project creation!"

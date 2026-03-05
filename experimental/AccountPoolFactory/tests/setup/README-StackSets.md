# StackSet Deployment Scripts

This directory contains scripts for deploying approved CloudFormation StackSets independently or in parallel.

## Overview

The Account Pool Factory uses CloudFormation StackSets to deploy approved templates to project accounts. Each StackSet can be deployed independently, allowing for flexible deployment strategies.

## Available Scripts

### Individual StackSet Deployment

Deploy each StackSet independently:

```bash
# Deploy VPC StackSet only
./deploy-vpc-stackset.sh

# Deploy IAM Roles StackSet only
./deploy-iam-roles-stackset.sh

# Deploy Blueprint Enablement StackSet only
./deploy-blueprint-stackset.sh
```

### Parallel Deployment

Deploy all StackSets concurrently for faster setup:

```bash
# Deploy all 3 StackSets in parallel
./deploy-all-stacksets-parallel.sh
```

### Legacy Script

The original script that deploys all StackSets sequentially:

```bash
# Deploy all StackSets sequentially (legacy)
./deploy-approved-stacksets.sh
```

## StackSet Details

### 1. VPC StackSet
- **Name**: `AccountPoolFactory-ControlTower-Test-VPCSetup`
- **Purpose**: Creates VPC and networking for SageMaker Unified Studio
- **Dependencies**: None
- **Resources**:
  - VPC (10.38.0.0/16)
  - 3 private subnets across 3 AZs
  - NAT Gateway, Internet Gateway
  - Route tables, S3 VPC endpoint
- **Parameters**:
  - `useVpcEndpoints`: false (default)

### 2. IAM Roles StackSet
- **Name**: `AccountPoolFactory-ControlTower-Test-IAMRoles`
- **Purpose**: Creates IAM roles for DataZone blueprint management
- **Dependencies**: None
- **Resources**:
  - ManageAccessRole (manages DataZone environments)
  - ProvisioningRole (provisions DataZone environments)
- **Parameters**:
  - `ProjectTag`: From config.yaml
  - `EnvironmentTag`: From config.yaml

### 3. Blueprint Enablement StackSet
- **Name**: `AccountPoolFactory-ControlTower-Test-BlueprintEnablement`
- **Purpose**: Enables all 17 DataZone environment blueprints
- **Dependencies**: IAM Roles, VPC (requires outputs from both)
- **Resources**:
  - 17 DataZone Environment Blueprint Configurations
- **Parameters** (required when deploying instances):
  - `DomainId`: DataZone domain ID
  - `ManageAccessRoleArn`: From IAM Roles stack
  - `ProvisioningRoleArn`: From IAM Roles stack
  - `S3Location`: S3 bucket for DataZone
  - `Subnets`: From VPC stack (comma-separated)
  - `VpcId`: From VPC stack

## Deployment Workflow

### Step 1: Deploy StackSets (One-Time Setup)

Choose one approach:

**Option A: Deploy Independently**
```bash
# Deploy in any order (VPC and IAM Roles have no dependencies)
./deploy-vpc-stackset.sh
./deploy-iam-roles-stackset.sh
./deploy-blueprint-stackset.sh
```

**Option B: Deploy in Parallel**
```bash
# Fastest - all 3 deploy concurrently
./deploy-all-stacksets-parallel.sh
```

**Option C: Deploy Sequentially (Legacy)**
```bash
# Original approach - one at a time
./deploy-approved-stacksets.sh
```

### Step 2: Deploy StackSet Instances to Accounts

After StackSets are created, deploy instances to target accounts:

#### VPC Instance
```bash
aws cloudformation create-stack-instances \
  --stack-set-name AccountPoolFactory-ControlTower-Test-VPCSetup \
  --accounts 004878717744 \
  --regions us-east-2
```

#### IAM Roles Instance
```bash
aws cloudformation create-stack-instances \
  --stack-set-name AccountPoolFactory-ControlTower-Test-IAMRoles \
  --accounts 004878717744 \
  --regions us-east-2
```

#### Blueprint Enablement Instance
```bash
# First, get outputs from VPC and IAM Roles stacks
VPC_ID=$(aws cloudformation describe-stack-instance \
  --stack-set-name AccountPoolFactory-ControlTower-Test-VPCSetup \
  --stack-instance-account 004878717744 \
  --stack-instance-region us-east-2 \
  --query 'StackInstance.Outputs[?OutputKey==`VpcId`].OutputValue' \
  --output text)

SUBNETS=$(aws cloudformation describe-stack-instance \
  --stack-set-name AccountPoolFactory-ControlTower-Test-VPCSetup \
  --stack-instance-account 004878717744 \
  --stack-instance-region us-east-2 \
  --query 'StackInstance.Outputs[?OutputKey==`PrivateSubnets`].OutputValue' \
  --output text)

MANAGE_ROLE=$(aws cloudformation describe-stack-instance \
  --stack-set-name AccountPoolFactory-ControlTower-Test-IAMRoles \
  --stack-instance-account 004878717744 \
  --stack-instance-region us-east-2 \
  --query 'StackInstance.Outputs[?OutputKey==`ManageAccessRoleArn`].OutputValue' \
  --output text)

PROVISIONING_ROLE=$(aws cloudformation describe-stack-instance \
  --stack-set-name AccountPoolFactory-ControlTower-Test-IAMRoles \
  --stack-instance-account 004878717744 \
  --stack-instance-region us-east-2 \
  --query 'StackInstance.Outputs[?OutputKey==`ProvisioningRoleArn`].OutputValue' \
  --output text)

# Then deploy Blueprint Enablement
aws cloudformation create-stack-instances \
  --stack-set-name AccountPoolFactory-ControlTower-Test-BlueprintEnablement \
  --accounts 004878717744 \
  --regions us-east-2 \
  --parameter-overrides \
    ParameterKey=DomainId,ParameterValue=dzd-bda44pkz3crp7t \
    ParameterKey=ManageAccessRoleArn,ParameterValue=$MANAGE_ROLE \
    ParameterKey=ProvisioningRoleArn,ParameterValue=$PROVISIONING_ROLE \
    ParameterKey=S3Location,ParameterValue=s3://your-datazone-bucket \
    ParameterKey=Subnets,ParameterValue=$SUBNETS \
    ParameterKey=VpcId,ParameterValue=$VPC_ID
```

## Deployment Order

### StackSet Creation (No Dependencies)
All StackSets can be created in parallel:
- VPC StackSet ✓
- IAM Roles StackSet ✓
- Blueprint Enablement StackSet ✓

### Instance Deployment (Has Dependencies)
Must follow this order:
1. VPC Instance (no dependencies)
2. IAM Roles Instance (no dependencies)
3. Blueprint Enablement Instance (requires VPC + IAM Roles outputs)

## Advantages of Independent Deployment

1. **Flexibility**: Deploy only what you need
2. **Speed**: Parallel deployment is 3x faster
3. **Testing**: Test each StackSet independently
4. **Updates**: Update one StackSet without affecting others
5. **Debugging**: Easier to isolate issues

## Common Use Cases

### Deploy Only VPC for Testing
```bash
./deploy-vpc-stackset.sh
# Then deploy instance to test account
```

### Update VPC Template
```bash
# Edit templates/cloudformation/03-project-account/vpc-setup.yaml
./deploy-vpc-stackset.sh  # Updates existing StackSet
```

### Deploy All for Production
```bash
./deploy-all-stacksets-parallel.sh  # Fastest approach
```

## Monitoring Deployment

### Check StackSet Status
```bash
aws cloudformation list-stack-sets \
  --region us-east-2 \
  --query "Summaries[?starts_with(StackSetName, 'AccountPoolFactory-ControlTower-Test-')].{Name:StackSetName,Status:Status}" \
  --output table
```

### Check Instance Status
```bash
aws cloudformation list-stack-instances \
  --stack-set-name AccountPoolFactory-ControlTower-Test-VPCSetup \
  --region us-east-2 \
  --output table
```

### View Logs (Parallel Deployment)
```bash
# Logs are saved to temporary directory
# Path is shown during deployment
cat /tmp/tmp.XXXXXX/vpc.log
cat /tmp/tmp.XXXXXX/iam-roles.log
cat /tmp/tmp.XXXXXX/blueprint.log
```

## Troubleshooting

### StackSet Already Exists
Scripts automatically update existing StackSets. No action needed.

### S3 Bucket Creation Failed
Bucket name must be unique. Check if bucket already exists:
```bash
aws s3 ls s3://apf-stacksets-495869084367 --region us-east-2
```

### Permission Denied
Verify CF1 stack is deployed and StackSetAdministrationRole exists:
```bash
aws cloudformation describe-stacks \
  --stack-name AccountPoolFactory-ControlTower-Test \
  --region us-east-2
```

### Parallel Deployment Failed
Check individual logs in the temporary directory shown during deployment.

## Configuration

All scripts read from `config.yaml`:
- `aws.region`: AWS region
- `aws.account_id`: AWS account ID
- `tags.Project`: Project tag value
- `tags.Environment`: Environment tag value

## S3 Bucket

Templates are uploaded to:
- **Bucket**: `apf-stacksets-{ACCOUNT_ID}`
- **Region**: From config.yaml
- **Versioning**: Enabled
- **Encryption**: AES256

## Security

- StackSets use `SELF_MANAGED` permission model
- Administration role: From CF1 stack
- Execution role: `AWSControlTowerExecution` (must exist in target accounts)
- Templates stored in encrypted S3 bucket

## See Also

- `APPROVED_TEMPLATES_SUMMARY.md` - Detailed template documentation
- `TEST_RESULTS.md` - Test results and verification
- `docs/TestingGuide.md` - Complete testing guide

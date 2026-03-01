# Approved CloudFormation Templates - Summary

## Overview

This document summarizes the approved CloudFormation templates that will be deployed to new project accounts after they are created by Control Tower Account Factory.

## Security Model

The Account Pool Factory implements a secure template deployment model:

1. **Organization Admin Controls Templates**: Org Admin creates and maintains approved StackSets
2. **Requesting Account Deploys Instances**: Requesting account can ONLY deploy instances of pre-approved StackSets
3. **No StackSet Modification**: Requesting account CANNOT create, update, or delete StackSets themselves
4. **Explicit Deny Policy**: IAM policy explicitly denies StackSet modification operations

## Approved Templates

### 1. VPC Setup (`vpc-setup.yaml`)

**Purpose**: Creates a VPC with private subnets for SageMaker Unified Studio and DataZone environments.

**Location**: `templates/cloudformation/03-project-account/vpc-setup.yaml`

**Resources Created**:
- VPC with CIDR 10.38.0.0/16
- 3-4 private subnets (depending on region availability zones)
- 1 public subnet for NAT gateway
- Internet Gateway (IGW)
- NAT Gateway with Elastic IP
- Route tables and associations
- Security group for VPC endpoints
- S3 VPC endpoint (Gateway type)

**Parameters**:
- `useVpcEndpoints`: Enable VPC endpoints for AWS services (default: false)

**Outputs**:
- `VpcId`: VPC ID for use in other templates
- `PrivateSubnets`: Comma-separated list of private subnet IDs
- `AvailabilityZones`: Comma-separated list of availability zones

**Tags**:
- `CreatedForUseWithSageMakerUnifiedStudio: true`
- `for-use-with-amazon-emr-managed-policies: true`

**Source**: Copied from `experimental/SMUS-CICD-pipeline-cli/tests/scripts/setup/iam-based-domains/1-account-setup/vpc-template.yaml`

---

### 2. Blueprint Enablement (`blueprint-enablement.yaml`)

**Purpose**: Enables all DataZone environment blueprints for the project account.

**Location**: `templates/cloudformation/03-project-account/blueprint-enablement.yaml`

**Resources Created**:
- 17 DataZone Environment Blueprint Configurations:
  1. LakehouseCatalog
  2. AmazonBedrockGuardrail
  3. MLExperiments
  4. Tooling
  5. RedshiftServerless
  6. EmrServerless
  7. Workflows
  8. AmazonBedrockPrompt
  9. DataLake
  10. AmazonBedrockEvaluation
  11. AmazonBedrockKnowledgeBase
  12. PartnerApps
  13. AmazonBedrockChatAgent
  14. AmazonBedrockFunction
  15. QuickSight
  16. AmazonBedrockFlow
  17. EmrOnEc2

**Parameters**:
- `DomainId`: DataZone Domain ID (REQUIRED)
- `ManageAccessRoleArn`: IAM role ARN to manage access to environments (REQUIRED)
- `ProvisioningRoleArn`: IAM role ARN to provision environments (REQUIRED)
- `S3Location`: S3 location for environment artifacts (REQUIRED)
- `Subnets`: Comma-separated list of subnet IDs (REQUIRED)
- `VpcId`: VPC ID for environments (REQUIRED)

**Outputs**:
- Blueprint IDs for each enabled blueprint (17 outputs)

**Dependencies**:
- Requires VPC setup to be completed first (for VpcId and Subnets parameters)
- Requires IAM roles to be created first (for ManageAccessRoleArn and ProvisioningRoleArn)

**Source**: Based on `cloudformation/domain/enable_all_blueprints.yaml`

---

### 3. IAM Roles (`iam-roles.yaml`)

**Purpose**: Creates IAM roles required for DataZone blueprint management and environment provisioning.

**Location**: `templates/cloudformation/03-project-account/iam-roles.yaml`

**Resources Created**:

#### ManageAccessRole
- **Purpose**: Manages access to DataZone environments
- **Trust Policy**: Allows `datazone.amazonaws.com` to assume
- **Managed Policies**:
  - `AmazonDataZoneEnvironmentRolePermissionsBoundary`
- **Inline Policies**:
  - Lake Formation permissions (grant/revoke, data access, settings)
  - IAM role management (get, list, pass role)
  - Glue catalog permissions (database and table operations)
  - S3 data access (get, put, delete, list)

#### ProvisioningRole
- **Purpose**: Provisions DataZone environments
- **Trust Policy**: Allows `datazone.amazonaws.com` to assume
- **Managed Policies**:
  - `AmazonSageMakerStudioProjectProvisioningRolePolicy` (default)
  - OR custom policy ARN (if specified)
  - `AmazonDataZoneEnvironmentRolePermissionsBoundary`

**Parameters**:
- `ProjectTag`: Value for Project tag (default: AccountPoolFactory)
- `EnvironmentTag`: Value for Environment tag (default: Production)
- `UseCustomProvisioningPolicy`: Use custom policy instead of AWS managed (default: false)
- `CustomProvisioningPolicyArn`: ARN of custom policy (optional)

**Outputs**:
- `ManageAccessRoleArn`: ARN of the ManageAccessRole
- `ManageAccessRoleName`: Name of the ManageAccessRole
- `ProvisioningRoleArn`: ARN of the ProvisioningRole
- `ProvisioningRoleName`: Name of the ProvisioningRole

**Flexibility**:
- Customers can choose between AWS managed policy or custom policy for provisioning
- AWS managed policy: `AmazonSageMakerStudioProjectProvisioningRolePolicy`
- Custom policy: Provide ARN via `CustomProvisioningPolicyArn` parameter

**Reference**: 
- AWS Managed Policy: https://docs.aws.amazon.com/aws-managed-policy/latest/reference/SageMakerStudioProjectProvisioningRolePolicy.html

---

## Deployment Order

The templates must be deployed in this order due to dependencies:

1. **IAM Roles** (`iam-roles.yaml`)
   - No dependencies
   - Outputs: ManageAccessRoleArn, ProvisioningRoleArn

2. **VPC Setup** (`vpc-setup.yaml`)
   - No dependencies
   - Outputs: VpcId, PrivateSubnets

3. **Blueprint Enablement** (`blueprint-enablement.yaml`)
   - Requires: ManageAccessRoleArn, ProvisioningRoleArn (from step 1)
   - Requires: VpcId, Subnets (from step 2)
   - Requires: S3Location (customer provides)

## StackSet Configuration

The approved templates are deployed as CloudFormation StackSets in the Organization Admin account:

### StackSet Names
- `${CF1StackName}-IAMRoles`
- `${CF1StackName}-VPCSetup`
- `${CF1StackName}-BlueprintEnablement`

### StackSet Properties
- **Permission Model**: SELF_MANAGED
- **Administration Role**: `${CF1StackName}-StackSetAdminRole` (created by CF1)
- **Execution Role**: `AWSControlTowerExecution` (exists in new accounts)
- **Capabilities**: CAPABILITY_NAMED_IAM (for IAM resource creation)

### Template Storage
- **S3 Bucket**: `${CF1StackName}-stackset-templates-${AccountId}`
- **Bucket Properties**:
  - Encryption: AES256
  - Versioning: Enabled
  - Public Access: Blocked
  - Access: CloudFormation service only

## Requesting Account Permissions

The requesting account (account pool management system) has these permissions:

### Allowed Operations
- `cloudformation:CreateStackInstances` - Deploy template to new account
- `cloudformation:DeleteStackInstances` - Remove template from account
- `cloudformation:UpdateStackInstances` - Update deployed template
- `cloudformation:DescribeStackInstance` - Get instance details
- `cloudformation:ListStackInstances` - List deployed instances
- `cloudformation:DescribeStackSet` - View StackSet details
- `cloudformation:DescribeStackSetOperation` - View operation status
- `cloudformation:ListStackSetOperations` - List operations
- `cloudformation:ListStackSetOperationResults` - View operation results
- `cloudformation:ListStackSets` - List available StackSets

### Denied Operations (Explicit Deny)
- `cloudformation:CreateStackSet` - Cannot create new StackSets
- `cloudformation:UpdateStackSet` - Cannot modify StackSet templates
- `cloudformation:DeleteStackSet` - Cannot delete StackSets

### Resource Restrictions
- Can only operate on StackSets with name prefix: `${CF1StackName}-*`
- Cannot access StackSets outside this naming convention

## Integration with CF1

The CF1 template (`templates/cloudformation/01-org-admin/account-factory-setup.yaml`) creates:

1. **StackSetAdministrationRole**: Allows CloudFormation service to deploy StackSets
2. **StackSetDeploymentRole**: Allows requesting account to deploy instances (with restrictions)
3. **StackSetDeploymentPolicy**: Enforces security model (allow instances, deny StackSet modification)

## Usage Example

After a new account is created by Control Tower:

```bash
# 1. Assume the StackSet deployment role in Org Admin account
aws sts assume-role \
  --role-arn arn:aws:iam::ORG_ADMIN_ACCOUNT:role/AccountPoolFactory-ControlTower-Test-StackSetDeploymentRole \
  --role-session-name account-setup \
  --external-id AccountPoolFactory-ControlTower-Test-StackSet-REQUESTING_ACCOUNT

# 2. Deploy IAM roles to new account
aws cloudformation create-stack-instances \
  --stack-set-name AccountPoolFactory-ControlTower-Test-IAMRoles \
  --accounts NEW_ACCOUNT_ID \
  --regions us-east-2 \
  --parameter-overrides \
    ParameterKey=ProjectTag,ParameterValue=MyProject \
    ParameterKey=EnvironmentTag,ParameterValue=Production

# 3. Deploy VPC setup to new account
aws cloudformation create-stack-instances \
  --stack-set-name AccountPoolFactory-ControlTower-Test-VPCSetup \
  --accounts NEW_ACCOUNT_ID \
  --regions us-east-2 \
  --parameter-overrides \
    ParameterKey=useVpcEndpoints,ParameterValue=false

# 4. Get VPC outputs from new account
VPC_ID=$(aws cloudformation describe-stack-instance \
  --stack-set-name AccountPoolFactory-ControlTower-Test-VPCSetup \
  --stack-instance-account NEW_ACCOUNT_ID \
  --stack-instance-region us-east-2 \
  --query 'StackInstance.Outputs[?OutputKey==`VpcId`].OutputValue' \
  --output text)

SUBNETS=$(aws cloudformation describe-stack-instance \
  --stack-set-name AccountPoolFactory-ControlTower-Test-VPCSetup \
  --stack-instance-account NEW_ACCOUNT_ID \
  --stack-instance-region us-east-2 \
  --query 'StackInstance.Outputs[?OutputKey==`PrivateSubnets`].OutputValue' \
  --output text)

# 5. Deploy blueprint enablement to new account
aws cloudformation create-stack-instances \
  --stack-set-name AccountPoolFactory-ControlTower-Test-BlueprintEnablement \
  --accounts NEW_ACCOUNT_ID \
  --regions us-east-2 \
  --parameter-overrides \
    ParameterKey=DomainId,ParameterValue=dzd-xxxxxxxxxxxxx \
    ParameterKey=ManageAccessRoleArn,ParameterValue=arn:aws:iam::NEW_ACCOUNT_ID:role/...-ManageAccessRole \
    ParameterKey=ProvisioningRoleArn,ParameterValue=arn:aws:iam::NEW_ACCOUNT_ID:role/...-ProvisioningRole \
    ParameterKey=S3Location,ParameterValue=s3://my-datazone-bucket \
    ParameterKey=Subnets,ParameterValue=$SUBNETS \
    ParameterKey=VpcId,ParameterValue=$VPC_ID
```

## Customization

Customers can customize the templates by:

1. **Modifying Templates**: Edit templates in `templates/cloudformation/03-project-account/`
2. **Uploading to S3**: Upload modified templates to the StackSet templates bucket
3. **Updating StackSets**: Org Admin updates StackSets with new template versions
4. **Deploying Updates**: Requesting account deploys updated instances to accounts

## Next Steps

1. Create deployment script for approved StackSets (`tests/setup/scripts/deploy-approved-stacksets.sh`)
2. Create script to upload templates to S3 bucket
3. Test StackSet deployment to new account
4. Document parameter values for each template
5. Create automation for post-account-creation setup

## References

- CF1 Template: `templates/cloudformation/01-org-admin/account-factory-setup.yaml`
- Approved StackSets Template: `templates/cloudformation/01-org-admin/approved-stacksets.yaml`
- VPC Setup: `templates/cloudformation/03-project-account/vpc-setup.yaml`
- Blueprint Enablement: `templates/cloudformation/03-project-account/blueprint-enablement.yaml`
- IAM Roles: `templates/cloudformation/03-project-account/iam-roles.yaml`
- Testing Guide: `docs/TestingGuide.md`

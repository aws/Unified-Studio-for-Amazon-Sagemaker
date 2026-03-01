# Account Pool Factory - Testing Guide

Complete step-by-step guide for testing the Account Pool Factory.

## Overview

This guide provides detailed instructions for testing the Account Pool Factory in a single AWS account environment. We will simulate the multi-account architecture within a single account before deploying to a full multi-account setup.

## Testing Strategy

### Single Account Testing Mode
For initial testing, we will:
1. Use a single AWS account
2. Simulate multiple accounts using DynamoDB records
3. Mock Control Tower account creation
4. Test the Lambda functions and workflows
5. Validate DataZone integration

### Prerequisites Checklist
- [ ] AWS Account with Organizations enabled
- [ ] AWS Region selected (recommended: us-east-2)
- [ ] DataZone Domain created
- [ ] IAM Permissions configured (Admin or equivalent)
- [ ] AWS CLI installed and configured
- [ ] Python 3.12+ installed
- [ ] Git repository initialized
- [ ] Configuration file created (config.yaml)

## Configuration

Before starting, you must configure your environment:

1. **Copy the template**:
   ```bash
   cd experimental/AccountPoolFactory
   cp config.yaml.template config.yaml
   ```

2. **Edit config.yaml** with your values:
   - aws.region (e.g., us-east-2)
   - aws.account_id (your account number)
   - datazone.domain_id (your DataZone domain ID)
   - Other configuration parameters

3. **Configure AWS credentials** using one of these methods:
   - AWS CLI: `aws configure`
   - Environment variables: `export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...`
   - AWS SSO: `aws sso login --profile your-profile`
   - Isengard (Amazon internal): `eval $(isengardcli creds YOUR_PROFILE --role Admin)`

**Note**: The config.yaml file is in .gitignore and will not be committed to version control.

## Configuration File

All configuration is stored in `config.yaml`:
- **config.yaml.template**: Template with placeholder values (committed to git)
- **config.yaml**: Your actual configuration (NOT committed, in .gitignore)

**Location**: `experimental/AccountPoolFactory/config.yaml`

---

## Phase 1: Environment Setup and Verification

### Step 1.1: Verify DataZone Domain ✅

**Objective**: Confirm the DataZone domain exists and is accessible.

**Commands**:
```bash
# Configure AWS credentials first (choose one method)
# Then verify domain exists

aws datazone get-domain \
  --identifier $(yq eval '.datazone.domain_id' config.yaml) \
  --region $(yq eval '.aws.region' config.yaml)
```

**Note**: If you don't have `yq` installed, you can read values directly from config.yaml and use them:
```bash
# Read your domain_id and region from config.yaml, then:
aws datazone get-domain \
  --identifier YOUR_DOMAIN_ID \
  --region YOUR_REGION
```

**Expected Output**:
```json
{
    "id": "dzd-xxxxxxxxxxxxx",
    "name": "YourDomainName",
    "status": "AVAILABLE",
    "portalUrl": "https://dzd-xxxxxxxxxxxxx.sagemaker.REGION.on.aws",
    "provisionStatus": "PROVISION_COMPLETE"
}
```

**Verification Checklist**:
- [ ] Domain ID matches your config.yaml datazone.domain_id
- [ ] Status is AVAILABLE
- [ ] Provision status is PROVISION_COMPLETE
- [ ] Portal URL is accessible
- [ ] Region matches your config.yaml aws.region

**Status**: ⏳ PENDING

**Notes**:
- Update config.yaml with your domain ID before starting
- Save the root domain unit ID for later use

---

### Step 1.2: Verify IAM Permissions

**Objective**: Ensure the current IAM role has necessary permissions.

**Commands**:
```bash
# Get current identity (region from config.yaml)
aws sts get-caller-identity --region $(yq eval '.aws.region' config.yaml)

# Or without yq, use your region directly:
aws sts get-caller-identity --region us-east-2

# Test other permissions
aws datazone list-domains --region us-east-2
aws lambda list-functions --region us-east-2 --max-items 1
aws dynamodb list-tables --region us-east-2 --max-items 1
aws cloudformation list-stacks --region us-east-2 --max-items 1
aws organizations describe-organization --region us-east-2
```

**Expected Output**:
- Current account ID matches your config.yaml aws.account_id
- All commands execute without AccessDenied errors

**Verification Checklist**:
- [ ] Can access DataZone APIs
- [ ] Can access Lambda APIs
- [ ] Can access DynamoDB APIs
- [ ] Can access CloudFormation APIs
- [ ] Can access IAM APIs
- [ ] Can access CloudWatch APIs

**Status**: ⏳ PENDING

---

### Step 1.3: Setup AWS Organization Structure

**Objective**: Create Organizational Units (OUs) using banking business terminology.

**Background**: 
The Account Pool Factory will create project accounts in a dedicated OU under a business unit. We're setting up a realistic organization structure for a bank with Retail Banking and Commercial Banking divisions.

**Organization Structure**:
```
Root
├── RetailBanking (Retail Banking Operations)
│   ├── CustomerAnalytics ⭐ (Account Pool Target)
│   └── RiskAnalytics ⭐ (Account Pool Target)
└── CommercialBanking (Commercial Banking & Business Lending)

Total: 4 OUs
⭐ = Analytics workload OUs where project accounts will be created
```

**Implementation**:
- CloudFormation template: `tests/setup/templates/organization-structure.yaml`
- Deployment script: `tests/setup/scripts/deploy-organization.sh`

**Commands**:
```bash
# Navigate to project directory
cd experimental/AccountPoolFactory

# Deploy the CloudFormation stack
./tests/setup/scripts/deploy-organization.sh

# View stack outputs
cat ou-ids.json
```

**CloudFormation Resources Created**:
1. `RetailBankingOU` - Retail banking business unit
2. `CommercialBankingOU` - Commercial banking business unit  
3. `RetailBankingCustomerAnalyticsOU` - Customer analytics OU (Account Pool Target)
4. `RetailBankingRiskAnalyticsOU` - Risk analytics OU (Account Pool Target)

**Expected Output**:
- CloudFormation stack: Value from config.yaml stacks.organization (default: AccountPoolFactory-Organization-Test)
- 4 OUs created across 2 levels
- Target OUs: `RetailBanking/CustomerAnalytics` and `RetailBanking/RiskAnalytics`
- Stack outputs saved to `ou-ids.json`
- `config.yaml` updated with organization details

**Verification Checklist**:
- [ ] CloudFormation stack deployed successfully
- [ ] All OUs created (check stack outputs)
- [ ] ou-ids.json file generated
- [ ] config.yaml updated with target OU
- [ ] Can view OUs in AWS Console

**AWS Console Verification**:
1. CloudFormation: https://console.aws.amazon.com/cloudformation (select your region)
   - Stack name: Check config.yaml stacks.organization value
   - Status should be: `CREATE_COMPLETE` or `UPDATE_COMPLETE`
2. Organizations: https://console.aws.amazon.com/organizations
   - Navigate to: Root → RetailBanking → CustomerAnalytics
   - Navigate to: Root → RetailBanking → RiskAnalytics
   - Verify both OUs exist and are empty (no accounts yet)

**Status**: ✅ COMPLETED

**Notes**:
- Uses CloudFormation for infrastructure as code
- Script handles stack creation and updates (idempotent)
- Target OU paths: `/RetailBanking/CustomerAnalytics` and `/RetailBanking/RiskAnalytics`
- These OUs will contain analytics project accounts for Retail Banking
- Stack can be deleted with: `aws cloudformation delete-stack --stack-name <stack-name> --region <region>`

---

### Step 1.4: Deploy Control Tower Account Factory Setup (CF1)

**Objective**: Configure the Organization Admin account with Control Tower Account Factory integration.

**Background**:
The CF1 template sets up the Organization Admin account to work with any account pool management system. It creates:
- IAM role for requesting account to trigger account creation via Control Tower
- Service Catalog permissions for Control Tower Account Factory
- EventBridge rules to capture account lifecycle events
- Cross-account event forwarding to requesting account

This template is completely independent of DataZone and can be used by any system that needs to create AWS accounts programmatically.

**Implementation**:
- CloudFormation template: `templates/cloudformation/01-org-admin/account-factory-setup.yaml`
- Deployment script: `tests/setup/scripts/deploy-account-factory.sh`

**Commands**:
```bash
# Navigate to project directory
cd experimental/AccountPoolFactory

# Deploy the CF1 CloudFormation stack
./tests/setup/scripts/deploy-account-factory.sh

# View stack outputs
cat cf1-outputs.json
```

**CloudFormation Resources Created**:
1. `AccountCreationRole` - IAM role for requesting account to assume
2. `AccountCreationPolicy` - Managed policy with Service Catalog and Organizations permissions
3. `AccountLifecycleEventBus` - EventBridge event bus for account events
4. `ControlTowerAccountCreationRule` - EventBridge rule to capture Control Tower events
5. `EventBridgeForwardingRole` - IAM role for EventBridge to forward events
6. `ForwardToRequestingAccountRule` - EventBridge rule to forward to requesting account
7. `CrossAccountEventForwardingRole` - IAM role for cross-account event forwarding
8. `ControlTowerProductIdParameter` - SSM parameter for Control Tower Product ID

**Expected Output**:
- CloudFormation stack: `AccountPoolFactory-ControlTower-Test` (or value from config.yaml)
- Stack status: `CREATE_COMPLETE` or `UPDATE_COMPLETE`
- Stack outputs saved to `cf1-outputs.json`
- Key outputs:
  - `AccountCreationRoleArn`: ARN to use in CF2 deployment
  - `ExternalId`: External ID for cross-account role assumption
  - `EventBusArn`: EventBridge event bus ARN
  - `EventBusName`: EventBridge event bus name

**Verification Checklist**:
- [ ] CloudFormation stack deployed successfully
- [ ] AccountCreationRole created with correct trust policy
- [ ] EventBridge rules created and enabled
- [ ] cf1-outputs.json file generated
- [ ] config.yaml updated with CF1 stack name
- [ ] Can view stack in AWS Console

**AWS Console Verification**:
1. CloudFormation: https://console.aws.amazon.com/cloudformation (select your region)
   - Stack name: Check config.yaml stacks.control_tower value
   - Status should be: `CREATE_COMPLETE` or `UPDATE_COMPLETE`
   - Review Outputs tab for role ARNs and event bus details
2. IAM Roles: https://console.aws.amazon.com/iam/home#/roles
   - Find role: `AccountPoolFactory-ControlTower-Test-AccountCreationRole`
   - Verify trust policy allows requesting account to assume
3. EventBridge: https://console.aws.amazon.com/events (select your region)
   - Event buses: Find `AccountPoolFactoryEventBus`
   - Rules: Find rules for Control Tower events

**Status**: ✅ COMPLETED

**Notes**:
- This is a one-time setup in the Organization Admin account
- The role created here will be used by CF2 (the account pool management system)
- EventBridge rules capture Control Tower account creation events
- CF1 is completely independent of DataZone - it's a generic account factory
- For testing, requesting account and Org Admin account are the same
- In production multi-account setup, these would be separate accounts
- Stack can be deleted with: `aws cloudformation delete-stack --stack-name AccountPoolFactory-ControlTower-Test --region <region>`

---

### Step 1.5: Test Account Creation via Control Tower

**Objective**: Verify the Control Tower Account Factory integration works by creating a test account.

**Background**:
Now that CF1 is deployed, we can test the account creation workflow. This validates:
- Control Tower Account Factory is accessible
- IAM roles have correct permissions
- EventBridge rules capture account lifecycle events
- Account creation completes successfully

**Test Scripts**:
We've created four scripts for async account creation and management:

1. **test-create-account.sh** - Creates new AWS account via Control Tower
2. **test-check-status.sh** - Checks provisioning status (can be run repeatedly)
3. **test-verify-account.sh** - Verifies account was created correctly
4. **test-delete-account.sh** - Deletes test account when done

**Email Format**: Test accounts use `amirbo+NNN@amazon.com` format (starting at 100, auto-increments)

**Implementation**:
- Test scripts: `tests/setup/scripts/test-*.sh`
- Provision files: `test-account-provision-NNN.json` (tracks status)
- Async operation: Can disconnect and reconnect without losing progress

**Commands**:
```bash
# Navigate to project directory
cd experimental/AccountPoolFactory

# Step 1: Create a test account
./tests/setup/scripts/test-create-account.sh

# The script will:
# - Find next available email number (100, 101, 102, etc.)
# - Provision account via Service Catalog
# - Save details to test-account-provision-NNN.json
# - Optionally monitor provisioning (or you can exit and check later)

# Step 2: Check status (if you exited during provisioning)
./tests/setup/scripts/test-check-status.sh 100

# Or check latest:
./tests/setup/scripts/test-check-status.sh

# Step 3: Verify account setup
./tests/setup/scripts/test-verify-account.sh 100

# Step 4: Delete account when done testing
./tests/setup/scripts/test-delete-account.sh 100
```

**Async Workflow**:
```bash
# Start account creation
./tests/setup/scripts/test-create-account.sh
# Choose "no" when asked to monitor
# Script saves state to test-account-provision-100.json

# Later (even after disconnect/reconnect):
./tests/setup/scripts/test-check-status.sh 100
# Shows current status: PROVISIONING, SUCCEEDED, or FAILED

# When SUCCEEDED:
./tests/setup/scripts/test-verify-account.sh 100
# Runs 6 verification checks

# When done testing:
./tests/setup/scripts/test-delete-account.sh 100
# Terminates provisioned product and optionally closes account
```

**Account Creation Details**:
- **Name**: `test-account-NNN` (e.g., test-account-100)
- **Email**: `amirbo+NNN@amazon.com` (e.g., amirbo+100@amazon.com)
- **SSO User**: `amirbo+NNN-admin@amazon.com`
- **Target OU**: Value from config.yaml (e.g., RetailBanking/CustomerAnalytics)
- **Provisioning Time**: 5-10 minutes
- **Status Tracking**: Saved in `test-account-provision-NNN.json`

**Provision File Structure**:
```json
{
  "emailNumber": 100,
  "timestamp": "20260301-123456",
  "accountName": "test-account-100",
  "accountEmail": "amirbo+100@amazon.com",
  "recordId": "rec-xxxxxxxxxxxxx",
  "productId": "prod-xxxxxxxxxxxxx",
  "artifactId": "pa-xxxxxxxxxxxxx",
  "targetOuId": "ou-xxxx-xxxxxxxx",
  "region": "us-east-2",
  "status": "PROVISIONING",
  "accountId": "123456789012"
}
```

**Expected Output - Create Account**:
```
========================================
Test: Create Account via Control Tower
========================================

Configuration:
  Region: us-east-2
  Account ID: 495869084367
  Target OU: ou-n5om-otvkrtx2
  CF1 Stack: AccountPoolFactory-ControlTower-Test

✓ CF1 stack exists
✓ Found Product ID: prod-xxxxxxxxxxxxx
✓ Found Artifact ID: pa-xxxxxxxxxxxxx
✓ Using email number: 100

Account Details:
  Name: test-account-100
  Email: amirbo+100@amazon.com
  SSO User: amirbo+100-admin@amazon.com
  Target OU: ou-n5om-otvkrtx2

Create this account? (yes/no): yes

✓ Provisioning started
  Record ID: rec-xxxxxxxxxxxxx

✓ Provisioning details saved to: test-account-provision-100.json

Monitor provisioning now? (yes/no): yes

[1] Status: IN_PROGRESS
[2] Status: IN_PROGRESS
...
[15] Status: SUCCEEDED

✓ Account provisioning completed successfully!
✓ New Account ID: 123456789012
✓ Account found in Organizations
```

**Expected Output - Check Status**:
```
========================================
Check Account Provisioning Status
========================================

Account Details:
  Email Number: 100
  Name: test-account-100
  Email: amirbo+100@amazon.com
  Account ID: 123456789012
  Saved Status: SUCCEEDED

Checking current status from AWS...
  Current Status: SUCCEEDED

✓ Provisioning completed successfully!

Next Steps:
1. Verify account: ./tests/setup/scripts/test-verify-account.sh 100
2. Test deploying StackSets to this account
3. When done: ./tests/setup/scripts/test-delete-account.sh 100
```

**Expected Output - Verify Account**:
```
========================================
Test: Verify Account Setup
========================================

Test Account Details:
  Email Number: 100
  Name: test-account-100
  Email: amirbo+100@amazon.com
  Account ID: 123456789012
  Target OU: ou-n5om-otvkrtx2
  Region: us-east-2

[1/6] Checking provisioning record status...
✓ Provisioning record status: SUCCEEDED

[2/6] Checking account in Organizations...
✓ Account exists and is ACTIVE

[3/6] Checking account OU placement...
✓ Account is in correct OU: ou-n5om-otvkrtx2

[4/6] Checking EventBridge events...
✓ EventBridge event bus exists and has archives

[5/6] Checking Control Tower enrollment...
✓ Account is managed by Control Tower

[6/6] Checking AWSControlTowerExecution role...
⊘ Manual verification required

========================================
Verification Summary
========================================

Checks Passed: 5
Checks Failed: 0

✓ All automated checks passed!
```

**Verification Checklist**:
- [ ] test-create-account.sh runs without errors
- [ ] Account provisioning starts successfully
- [ ] Provision file created with correct email number
- [ ] Can monitor status or exit and check later
- [ ] test-check-status.sh shows current status
- [ ] Account reaches SUCCEEDED status (5-10 minutes)
- [ ] test-verify-account.sh passes all checks
- [ ] Account appears in AWS Organizations
- [ ] Account is in correct OU
- [ ] Account is enrolled in Control Tower

**AWS Console Verification**:
1. Service Catalog: https://console.aws.amazon.com/servicecatalog (select your region)
   - Provisioned Products: Find `test-account-100`
   - Status should be: `AVAILABLE`
   - View outputs for Account ID
2. Organizations: https://console.aws.amazon.com/organizations
   - Accounts: Find account with email `amirbo+100@amazon.com`
   - Status should be: `ACTIVE`
   - Parent OU should match target OU from config.yaml
3. Control Tower: https://console.aws.amazon.com/controltower (select your region)
   - Organization: View enrolled accounts
   - Find `test-account-100` in the list

**Troubleshooting**:

1. **Control Tower Product Not Found**:
   - Verify Control Tower is enabled in your account
   - Check you have Service Catalog access
   - For testing without Control Tower, the script will simulate account creation

2. **Email Already In Use**:
   - Script automatically finds next available number
   - Check existing provision files: `ls test-account-provision-*.json`
   - Check Organizations: `aws organizations list-accounts --query "Accounts[?Email=='amirbo+100@amazon.com']"`

3. **Provisioning Failed**:
   - Check error details: `./tests/setup/scripts/test-check-status.sh 100`
   - Review Service Catalog errors in AWS Console
   - Common issues: OU doesn't exist, SSO not configured, insufficient permissions

4. **Provisioning Stuck**:
   - Normal provisioning takes 5-10 minutes
   - Check status periodically: `./tests/setup/scripts/test-check-status.sh 100`
   - If stuck > 15 minutes, check Service Catalog console for errors

**Status**: ⏳ PENDING

**Notes**:
- Test accounts are real AWS accounts created via Control Tower
- Each account costs money - delete when done testing
- Email format allows creating multiple test accounts (100, 101, 102, etc.)
- Provision files track state - safe to disconnect during provisioning
- Scripts are idempotent - safe to run multiple times
- Account deletion terminates Service Catalog product but doesn't close AWS account
- To fully close account: Use `aws organizations close-account` or AWS Console
- Keep test accounts for StackSet deployment testing (next step)

---

### Step 1.6: Verify Project Directory Structure

**Objective**: Ensure all required directories exist.

**Commands**:
```bash
cd experimental/AccountPoolFactory

# Verify directory structure
ls -la

# Check for required directories
test -d templates/cloudformation && echo "✓ CloudFormation templates dir exists"
test -d src && echo "✓ Source code dir exists"
test -d tests && echo "✓ Tests dir exists"
test -d scripts && echo "✓ Scripts dir exists"
test -f config.yaml && echo "✓ Configuration file exists"
```

**Verification Checklist**:
- [ ] All directories exist
- [ ] config.yaml file exists
- [ ] README files are present
- [ ] Spec documents are complete

**Status**: ⏳ PENDING

---

### Step 1.7: Deploy Approved StackSets (After Account Creation)

**Objective**: Deploy approved CloudFormation templates to the newly created test account.

**Background**:
After creating a test account via Control Tower, we need to deploy the approved templates:
1. IAM Roles (for DataZone blueprint management)
2. VPC Setup (networking for SageMaker Unified Studio)
3. Blueprint Enablement (enable all 17 DataZone blueprints)

These templates are deployed as CloudFormation StackSets in the Org Admin account, and then instances are deployed to the test account.

**Security Model**:
- Org Admin creates and maintains StackSets (approved templates)
- Requesting account can ONLY deploy instances of approved StackSets
- Requesting account CANNOT create, update, or delete StackSets
- Explicit DENY policy prevents StackSet modification

**Prerequisites**:
- Step 1.5 completed (test account created and verified)
- Test account ID available from provision file
- CF1 stack deployed with StackSet roles

**Implementation**:
- Approved templates: `templates/cloudformation/03-project-account/*.yaml`
- StackSets template: `templates/cloudformation/01-org-admin/approved-stacksets.yaml`
- Deployment script: `tests/setup/scripts/deploy-approved-stacksets.sh`
- Documentation: `APPROVED_TEMPLATES_SUMMARY.md`

**Commands**:
```bash
# Navigate to project directory
cd experimental/AccountPoolFactory

# Step 1: Deploy approved StackSets (one-time setup in Org Admin account)
./tests/setup/scripts/deploy-approved-stacksets.sh

# This creates:
# - S3 bucket for StackSet templates
# - 3 StackSets: IAMRoles, VPCSetup, BlueprintEnablement
# - Uploads templates to S3

# Step 2: Deploy StackSet instances to test account
# Get test account ID from provision file
TEST_ACCOUNT_ID=$(jq -r '.accountId' test-account-provision-100.json)

# Deploy IAM Roles
aws cloudformation create-stack-instances \
  --stack-set-name AccountPoolFactory-ControlTower-Test-IAMRoles \
  --accounts $TEST_ACCOUNT_ID \
  --regions us-east-2 \
  --parameter-overrides \
    ParameterKey=ProjectTag,ParameterValue=AccountPoolFactory \
    ParameterKey=EnvironmentTag,ParameterValue=Test

# Wait for IAM roles deployment
aws cloudformation wait stack-instance-create-complete \
  --stack-set-name AccountPoolFactory-ControlTower-Test-IAMRoles \
  --stack-instance-account $TEST_ACCOUNT_ID \
  --stack-instance-region us-east-2

# Deploy VPC Setup
aws cloudformation create-stack-instances \
  --stack-set-name AccountPoolFactory-ControlTower-Test-VPCSetup \
  --accounts $TEST_ACCOUNT_ID \
  --regions us-east-2 \
  --parameter-overrides \
    ParameterKey=useVpcEndpoints,ParameterValue=false

# Wait for VPC deployment
aws cloudformation wait stack-instance-create-complete \
  --stack-set-name AccountPoolFactory-ControlTower-Test-VPCSetup \
  --stack-instance-account $TEST_ACCOUNT_ID \
  --stack-instance-region us-east-2

# Get VPC outputs
VPC_ID=$(aws cloudformation describe-stack-instance \
  --stack-set-name AccountPoolFactory-ControlTower-Test-VPCSetup \
  --stack-instance-account $TEST_ACCOUNT_ID \
  --stack-instance-region us-east-2 \
  --query 'StackInstance.Outputs[?OutputKey==`VpcId`].OutputValue' \
  --output text)

SUBNETS=$(aws cloudformation describe-stack-instance \
  --stack-set-name AccountPoolFactory-ControlTower-Test-VPCSetup \
  --stack-instance-account $TEST_ACCOUNT_ID \
  --stack-instance-region us-east-2 \
  --query 'StackInstance.Outputs[?OutputKey==`PrivateSubnets`].OutputValue' \
  --output text)

# Get IAM role ARNs
MANAGE_ACCESS_ROLE=$(aws cloudformation describe-stack-instance \
  --stack-set-name AccountPoolFactory-ControlTower-Test-IAMRoles \
  --stack-instance-account $TEST_ACCOUNT_ID \
  --stack-instance-region us-east-2 \
  --query 'StackInstance.Outputs[?OutputKey==`ManageAccessRoleArn`].OutputValue' \
  --output text)

PROVISIONING_ROLE=$(aws cloudformation describe-stack-instance \
  --stack-set-name AccountPoolFactory-ControlTower-Test-IAMRoles \
  --stack-instance-account $TEST_ACCOUNT_ID \
  --stack-instance-region us-east-2 \
  --query 'StackInstance.Outputs[?OutputKey==`ProvisioningRoleArn`].OutputValue' \
  --output text)

# Deploy Blueprint Enablement
aws cloudformation create-stack-instances \
  --stack-set-name AccountPoolFactory-ControlTower-Test-BlueprintEnablement \
  --accounts $TEST_ACCOUNT_ID \
  --regions us-east-2 \
  --parameter-overrides \
    ParameterKey=DomainId,ParameterValue=$(yq eval '.datazone.domain_id' config.yaml) \
    ParameterKey=ManageAccessRoleArn,ParameterValue=$MANAGE_ACCESS_ROLE \
    ParameterKey=ProvisioningRoleArn,ParameterValue=$PROVISIONING_ROLE \
    ParameterKey=S3Location,ParameterValue=s3://your-datazone-bucket \
    ParameterKey=Subnets,ParameterValue=$SUBNETS \
    ParameterKey=VpcId,ParameterValue=$VPC_ID

# Wait for blueprint enablement
aws cloudformation wait stack-instance-create-complete \
  --stack-set-name AccountPoolFactory-ControlTower-Test-BlueprintEnablement \
  --stack-instance-account $TEST_ACCOUNT_ID \
  --stack-instance-region us-east-2
```

**Deployment Order** (due to dependencies):
1. IAM Roles (no dependencies)
2. VPC Setup (no dependencies)
3. Blueprint Enablement (requires IAM roles and VPC)

**Expected Output - Deploy StackSets**:
```
========================================
Deploy Approved StackSets
========================================

Creating S3 bucket for StackSet templates...
✓ Bucket created: accountpoolfactory-controltower-test-stackset-templates-495869084367

Uploading templates to S3...
✓ Uploaded: iam-roles.yaml
✓ Uploaded: vpc-setup.yaml
✓ Uploaded: blueprint-enablement.yaml

Creating StackSet: IAMRoles...
✓ StackSet created: AccountPoolFactory-ControlTower-Test-IAMRoles

Creating StackSet: VPCSetup...
✓ StackSet created: AccountPoolFactory-ControlTower-Test-VPCSetup

Creating StackSet: BlueprintEnablement...
✓ StackSet created: AccountPoolFactory-ControlTower-Test-BlueprintEnablement

========================================
StackSets Deployment Complete
========================================

Next Steps:
1. Deploy instances to test account: See commands above
2. Verify deployments in CloudFormation console
3. Check resources created in test account
```

**Expected Output - Deploy Instances**:
```
# IAM Roles deployment
{
    "OperationId": "12345678-1234-1234-1234-123456789012"
}

# VPC Setup deployment
{
    "OperationId": "23456789-2345-2345-2345-234567890123"
}

# Blueprint Enablement deployment
{
    "OperationId": "34567890-3456-3456-3456-345678901234"
}
```

**Verification Checklist**:
- [ ] S3 bucket created for StackSet templates
- [ ] All 3 templates uploaded to S3
- [ ] All 3 StackSets created successfully
- [ ] IAM roles deployed to test account
- [ ] VPC deployed to test account
- [ ] Blueprints enabled in test account
- [ ] Can view StackSet instances in CloudFormation console
- [ ] Resources exist in test account

**AWS Console Verification**:
1. CloudFormation StackSets: https://console.aws.amazon.com/cloudformation (select your region)
   - StackSets: Find 3 StackSets with prefix `AccountPoolFactory-ControlTower-Test-`
   - Stack instances: Each should have 1 instance for test account
   - Status should be: `CURRENT`
2. S3 Buckets: https://s3.console.aws.amazon.com/s3/buckets
   - Find bucket: `accountpoolfactory-controltower-test-stackset-templates-*`
   - Verify 3 template files exist
3. Test Account (switch to test account):
   - CloudFormation Stacks: Should see 3 stacks
   - IAM Roles: Should see ManageAccessRole and ProvisioningRole
   - VPC: Should see VPC with private subnets
   - DataZone: Should see 17 enabled blueprints

**Resources Created in Test Account**:

1. **IAM Roles Stack**:
   - ManageAccessRole (manages access to DataZone environments)
   - ProvisioningRole (provisions DataZone environments)

2. **VPC Setup Stack**:
   - VPC (10.38.0.0/16)
   - 3-4 private subnets
   - 1 public subnet
   - NAT Gateway with Elastic IP
   - Internet Gateway
   - Route tables
   - S3 VPC endpoint

3. **Blueprint Enablement Stack**:
   - 17 DataZone Environment Blueprint Configurations:
     - LakehouseCatalog, AmazonBedrockGuardrail, MLExperiments
     - Tooling, RedshiftServerless, EmrServerless, Workflows
     - AmazonBedrockPrompt, DataLake, AmazonBedrockEvaluation
     - AmazonBedrockKnowledgeBase, PartnerApps
     - AmazonBedrockChatAgent, AmazonBedrockFunction
     - QuickSight, AmazonBedrockFlow, EmrOnEc2

**Troubleshooting**:

1. **StackSet Creation Failed**:
   - Verify CF1 stack deployed successfully
   - Check StackSetAdministrationRole exists
   - Verify S3 bucket permissions

2. **Instance Deployment Failed**:
   - Check AWSControlTowerExecution role exists in test account
   - Verify test account is enrolled in Control Tower
   - Review CloudFormation stack events in test account

3. **Blueprint Enablement Failed**:
   - Verify IAM roles deployed first
   - Verify VPC deployed first
   - Check DataZone domain ID is correct
   - Verify S3 location exists

4. **Permission Denied**:
   - Verify you're using StackSetDeploymentRole
   - Check external ID is correct
   - Verify StackSet name has correct prefix

**Status**: ⏳ PENDING

**Notes**:
- StackSets are created once in Org Admin account
- Instances are deployed per account
- Templates can be updated by Org Admin
- Requesting account can only deploy instances, not modify StackSets
- Each deployment takes 2-5 minutes per stack
- Total deployment time: ~10-15 minutes for all 3 stacks
- Resources in test account cost money - delete when done testing
- See `APPROVED_TEMPLATES_SUMMARY.md` for detailed template documentation

---

### Step 1.8: Install Dependencies

**Objective**: Install required Python packages and tools.

**Commands**:
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install AWS SDK and dependencies
pip install boto3 pyyaml pytest pytest-cov moto

# Verify installations
python -c "import boto3; print(f'boto3 version: {boto3.__version__}')"
python -c "import yaml; print('PyYAML installed')"
python -c "import pytest; print(f'pytest version: {pytest.__version__}')"
```

**Verification Checklist**:
- [ ] Virtual environment created
- [ ] boto3 installed
- [ ] PyYAML installed
- [ ] pytest installed
- [ ] All imports work

**Status**: ⏳ PENDING

---

## Phase 2: DynamoDB Setup

### Step 2.1: Create Account Pool Table

**Objective**: Create the DynamoDB table to store account pool state.

**CloudFormation Template**: Create `templates/cloudformation/test/dynamodb-tables.yaml`

**Commands**:
```bash
# Deploy DynamoDB tables
aws cloudformation create-stack \
  --stack-name AccountPoolFactory-DynamoDB-Test \
  --template-body file://templates/cloudformation/test/dynamodb-tables.yaml \
  --parameters \
    ParameterKey=DomainId,ParameterValue=dzd-bda44pkz3crp7t \
  --region us-east-2

# Wait for stack creation
aws cloudformation wait stack-create-complete \
  --stack-name AccountPoolFactory-DynamoDB-Test \
  --region us-east-2

# Verify table created
aws dynamodb describe-table \
  --table-name AccountPool-dzd-bda44pkz3crp7t \
  --region us-east-2
```

**Expected Output**:
- Stack status: CREATE_COMPLETE
- Table status: ACTIVE
- GSIs created: StateIndex, ProjectIndex

**Verification Checklist**:
- [ ] AccountPool table created
- [ ] AccountPoolConfig table created
- [ ] StateIndex GSI exists
- [ ] ProjectIndex GSI exists
- [ ] Point-in-time recovery enabled
- [ ] Encryption enabled

**Status**: ⏳ PENDING

---

### Step 2.2: Initialize Configuration Data

**Objective**: Populate the AccountPoolConfig table with initial settings.

**Commands**:
```bash
# Create configuration item
aws dynamodb put-item \
  --table-name AccountPoolConfig-dzd-bda44pkz3crp7t \
  --item file://tests/fixtures/initial-config.json \
  --region us-east-2

# Verify configuration
aws dynamodb get-item \
  --table-name AccountPoolConfig-dzd-bda44pkz3crp7t \
  --key '{"ConfigKey": {"S": "PoolSettings"}}' \
  --region us-east-2
```

**Configuration File**: `tests/fixtures/initial-config.json`
```json
{
  "ConfigKey": {"S": "PoolSettings"},
  "MinimumPoolSize": {"N": "3"},
  "MaximumPoolSize": {"N": "10"},
  "ReplenishmentThreshold": {"N": "5"},
  "AccountNamePrefix": {"S": "smus-test-project-"},
  "AccountEmailDomain": {"S": "aws-test@example.com"},
  "SupportedRegions": {"L": [
    {"S": "us-east-2"},
    {"S": "us-east-1"}
  ]},
  "UpdatedAt": {"S": "2026-02-27T00:00:00Z"}
}
```

**Verification Checklist**:
- [ ] Configuration item created
- [ ] All parameters set correctly
- [ ] Can retrieve configuration

**Status**: ⏳ PENDING

---

### Step 2.3: Create Mock Account Records

**Objective**: Create simulated account records for testing.

**Commands**:
```bash
# Create 3 mock accounts in AVAILABLE state
for i in {1..3}; do
  aws dynamodb put-item \
    --table-name AccountPool-dzd-bda44pkz3crp7t \
    --item file://tests/fixtures/mock-account-${i}.json \
    --region us-east-2
done

# Verify accounts created
aws dynamodb scan \
  --table-name AccountPool-dzd-bda44pkz3crp7t \
  --region us-east-2
```

**Mock Account Template**: `tests/fixtures/mock-account-1.json`
```json
{
  "AccountId": {"S": "111111111111"},
  "AccountName": {"S": "smus-test-project-001"},
  "AccountEmail": {"S": "smus-test-project-001@aws-test.example.com"},
  "State": {"S": "AVAILABLE"},
  "CreatedAt": {"S": "2026-02-27T00:00:00Z"},
  "UpdatedAt": {"S": "2026-02-27T00:00:00Z"},
  "Tags": {"M": {
    "Purpose": {"S": "DataZone"},
    "ManagedBy": {"S": "AccountPoolFactory"},
    "Environment": {"S": "Test"}
  }}
}
```

**Verification Checklist**:
- [ ] 3 mock accounts created
- [ ] All accounts in AVAILABLE state
- [ ] Account IDs are unique
- [ ] Can query by state using GSI

**Status**: ⏳ PENDING

---

## Phase 3: Lambda Function Development

### Step 3.1: Create Shared Utilities

**Objective**: Implement shared utilities for Lambda functions.

**Files to Create**:
- `src/shared/__init__.py`
- `src/shared/config.py`
- `src/shared/dynamodb_helper.py`
- `src/shared/logger.py`

**Commands**:
```bash
# Create shared module structure
mkdir -p src/shared
touch src/shared/__init__.py

# Run unit tests
cd src/shared
pytest tests/test_config.py -v
pytest tests/test_dynamodb_helper.py -v
```

**Verification Checklist**:
- [ ] Config loader implemented
- [ ] DynamoDB helper implemented
- [ ] Logger configured
- [ ] Unit tests pass
- [ ] Code coverage > 80%

**Status**: ⏳ PENDING

---

### Step 3.2: Implement Account Provider Lambda

**Objective**: Create the Lambda function that handles DataZone account pool requests.

**File**: `src/account-provider/handler.py`

**Key Functions**:
1. `lambda_handler(event, context)` - Main entry point
2. `list_authorized_accounts()` - Return available accounts
3. `validate_account_authorization(account_id)` - Validate account

**Commands**:
```bash
# Create Lambda package
cd src/account-provider
pip install -r requirements.txt -t package/
cp handler.py package/
cd package && zip -r ../account-provider.zip . && cd ..

# Run unit tests
pytest tests/test_handler.py -v

# Test locally with sample event
python -c "
import json
from handler import lambda_handler

event = {
    'operationRequest': {
        'listAuthorizedAccountsRequest': {}
    }
}
result = lambda_handler(event, None)
print(json.dumps(result, indent=2))
"
```

**Verification Checklist**:
- [ ] Handler implemented
- [ ] ListAuthorizedAccounts works
- [ ] ValidateAccountAuthorization works
- [ ] Unit tests pass
- [ ] Local testing successful

**Status**: ⏳ PENDING

---

### Step 3.3: Deploy Account Provider Lambda

**Objective**: Deploy the Lambda function to AWS.

**Commands**:
```bash
# Create IAM role for Lambda
aws iam create-role \
  --role-name AccountProviderRole-Test \
  --assume-role-policy-document file://templates/iam/lambda-trust-policy.json \
  --region us-east-2

# Attach policies
aws iam attach-role-policy \
  --role-name AccountProviderRole-Test \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
  --region us-east-2

aws iam put-role-policy \
  --role-name AccountProviderRole-Test \
  --policy-name DynamoDBAccess \
  --policy-document file://templates/iam/dynamodb-policy.json \
  --region us-east-2

# Deploy Lambda function
aws lambda create-function \
  --function-name AccountProvider-dzd-bda44pkz3crp7t \
  --runtime python3.12 \
  --role arn:aws:iam::495869084367:role/AccountProviderRole-Test \
  --handler handler.lambda_handler \
  --zip-file fileb://src/account-provider/account-provider.zip \
  --timeout 300 \
  --memory-size 512 \
  --environment Variables="{
    DOMAIN_ID=dzd-bda44pkz3crp7t,
    ACCOUNT_POOL_TABLE=AccountPool-dzd-bda44pkz3crp7t,
    CONFIG_TABLE=AccountPoolConfig-dzd-bda44pkz3crp7t,
    REGION=us-east-2
  }" \
  --region us-east-2

# Test Lambda function
aws lambda invoke \
  --function-name AccountProvider-dzd-bda44pkz3crp7t \
  --payload file://tests/fixtures/list-accounts-event.json \
  --region us-east-2 \
  response.json

cat response.json
```

**Verification Checklist**:
- [ ] IAM role created
- [ ] Lambda function deployed
- [ ] Environment variables set
- [ ] Test invocation successful
- [ ] Returns available accounts

**Status**: ⏳ PENDING

---

## Phase 4: DataZone Account Pool Integration

### Step 4.1: Create DataZone Account Pool

**Objective**: Register the Lambda function as a custom account pool handler.

**Commands**:
```bash
# Get Lambda function ARN
LAMBDA_ARN=$(aws lambda get-function \
  --function-name AccountProvider-dzd-bda44pkz3crp7t \
  --region us-east-2 \
  --query 'Configuration.FunctionArn' \
  --output text)

# Get Lambda execution role ARN
ROLE_ARN=$(aws lambda get-function \
  --function-name AccountProvider-dzd-bda44pkz3crp7t \
  --region us-east-2 \
  --query 'Configuration.Role' \
  --output text)

# Create account pool
aws datazone create-account-pool \
  --domain-identifier dzd-bda44pkz3crp7t \
  --name AccountPoolFactory-Test \
  --resolution-strategy MANUAL \
  --account-source "{
    \"customAccountPoolHandler\": {
      \"lambdaFunctionArn\": \"${LAMBDA_ARN}\",
      \"lambdaExecutionRoleArn\": \"${ROLE_ARN}\"
    }
  }" \
  --region us-east-2

# Verify account pool created
aws datazone list-account-pools \
  --domain-identifier dzd-bda44pkz3crp7t \
  --region us-east-2
```

**Expected Output**:
```json
{
    "domainId": "dzd-bda44pkz3crp7t",
    "name": "AccountPoolFactory-Test",
    "id": "cln5qjqEXAMPLE",
    "resolutionStrategy": "MANUAL",
    "accountSource": {
        "customAccountPoolHandler": {
            "lambdaFunctionArn": "arn:aws:lambda:us-east-2:495869084367:function:AccountProvider-dzd-bda44pkz3crp7t",
            "lambdaExecutionRoleArn": "arn:aws:iam::495869084367:role/AccountProviderRole-Test"
        }
    }
}
```

**Verification Checklist**:
- [ ] Account pool created
- [ ] Lambda function registered
- [ ] Resolution strategy is MANUAL
- [ ] Can list account pools

**Status**: ⏳ PENDING

---

### Step 4.2: Test Account Pool from DataZone

**Objective**: Verify the account pool works from DataZone console.

**Manual Steps**:
1. Open DataZone portal: https://dzd-bda44pkz3crp7t.sagemaker.us-east-2.on.aws
2. Navigate to Account Pools section
3. Verify "AccountPoolFactory-Test" appears
4. Check that 3 accounts are listed as available

**Verification Checklist**:
- [ ] Account pool visible in console
- [ ] Shows 3 available accounts
- [ ] Account names match mock data
- [ ] Can view account details

**Status**: ⏳ PENDING

---

### Step 4.3: Create Test Project with Account Pool

**Objective**: Create a DataZone project that uses the account pool.

**Commands**:
```bash
# Create project (via CLI or console)
aws datazone create-project \
  --domain-identifier dzd-bda44pkz3crp7t \
  --name "Test-Project-001" \
  --description "Test project for Account Pool Factory" \
  --region us-east-2

# Note: Account assignment happens automatically when project is created
# if account pool is configured at domain level
```

**Manual Steps** (if using console):
1. Go to DataZone portal
2. Click "Create Project"
3. Enter project name: "Test-Project-001"
4. Select account pool: "AccountPoolFactory-Test"
5. Complete project creation

**Verification Checklist**:
- [ ] Project created successfully
- [ ] Account assigned from pool
- [ ] Account state changed to ASSIGNED in DynamoDB
- [ ] Project can access assigned account

**Status**: ⏳ PENDING

---

## Phase 5: Pool Management Testing

### Step 5.1: Implement Pool Manager Lambda

**Objective**: Create Lambda to monitor and replenish the pool.

**File**: `src/pool-manager/handler.py`

**Commands**:
```bash
# Similar to Account Provider deployment
cd src/pool-manager
# ... build and deploy steps
```

**Verification Checklist**:
- [ ] Pool Manager implemented
- [ ] Can check pool size
- [ ] Can trigger replenishment
- [ ] Unit tests pass

**Status**: ⏳ PENDING

---

### Step 5.2: Test Pool Replenishment

**Objective**: Verify pool automatically replenishes when accounts are assigned.

**Test Scenario**:
1. Assign all 3 available accounts to projects
2. Pool Manager detects pool is below threshold
3. New mock accounts are created
4. Pool returns to minimum size

**Commands**:
```bash
# Manually trigger Pool Manager
aws lambda invoke \
  --function-name PoolManager-dzd-bda44pkz3crp7t \
  --region us-east-2 \
  response.json

# Check pool size
aws dynamodb query \
  --table-name AccountPool-dzd-bda44pkz3crp7t \
  --index-name StateIndex \
  --key-condition-expression "State = :state" \
  --expression-attribute-values '{":state": {"S": "AVAILABLE"}}' \
  --region us-east-2
```

**Verification Checklist**:
- [ ] Pool Manager detects low pool
- [ ] New accounts created
- [ ] Pool size returns to minimum
- [ ] CloudWatch metrics emitted

**Status**: ⏳ PENDING

---

## Phase 6: Monitoring and Observability

### Step 6.1: Create CloudWatch Dashboard

**Objective**: Set up monitoring dashboard for pool health.

**Commands**:
```bash
# Deploy dashboard via CloudFormation
aws cloudformation create-stack \
  --stack-name AccountPoolFactory-Dashboard-Test \
  --template-body file://templates/cloudformation/test/dashboard.yaml \
  --region us-east-2
```

**Verification Checklist**:
- [ ] Dashboard created
- [ ] Pool size widget shows data
- [ ] Assignment rate widget shows data
- [ ] Error rate widget shows data

**Status**: ⏳ PENDING

---

### Step 6.2: Configure CloudWatch Alarms

**Objective**: Set up alarms for critical conditions.

**Alarms to Create**:
1. Pool Low (< 3 accounts)
2. Pool Empty (0 accounts)
3. High Error Rate (> 10%)

**Verification Checklist**:
- [ ] All alarms created
- [ ] SNS topic configured
- [ ] Test alarm triggers

**Status**: ⏳ PENDING

---

## Phase 7: End-to-End Testing

### Step 7.1: Complete Workflow Test

**Objective**: Test the entire workflow from project creation to account assignment.

**Test Steps**:
1. Verify pool has available accounts
2. Create new DataZone project
3. Verify account assigned
4. Verify pool replenishment triggered
5. Verify new account becomes available
6. Check all metrics and logs

**Verification Checklist**:
- [ ] Project creation successful
- [ ] Account assigned < 30 seconds
- [ ] Pool replenished automatically
- [ ] All metrics recorded
- [ ] No errors in logs

**Status**: ⏳ PENDING

---

## Phase 8: Cleanup

### Step 8.1: Delete Test Resources

**Objective**: Clean up all test resources.

**Commands**:
```bash
# Delete account pool
aws datazone delete-account-pool \
  --domain-identifier dzd-bda44pkz3crp7t \
  --identifier <pool-id> \
  --region us-east-2

# Delete Lambda functions
aws lambda delete-function \
  --function-name AccountProvider-dzd-bda44pkz3crp7t \
  --region us-east-2

# Delete CloudFormation stacks
aws cloudformation delete-stack \
  --stack-name AccountPoolFactory-DynamoDB-Test \
  --region us-east-2

# Delete IAM roles
aws iam delete-role \
  --role-name AccountProviderRole-Test
```

**Verification Checklist**:
- [ ] All Lambda functions deleted
- [ ] All DynamoDB tables deleted
- [ ] All CloudFormation stacks deleted
- [ ] All IAM roles deleted

**Status**: ⏳ PENDING

---

## Testing Progress Tracker

| Phase | Status | Completion Date | Notes |
|-------|--------|----------------|-------|
| 1.1 - Verify DataZone Domain | ✅ COMPLETED | 2026-02-27 | Domain verified and accessible |
| 1.2 - Verify IAM Permissions | ✅ COMPLETED | 2026-02-27 | Using Isengard CLI with Admin role |
| 1.3 - Setup Organization Structure | ✅ COMPLETED | 2026-02-27 | OUs created successfully |
| 1.4 - Deploy CF1 (Control Tower) | ✅ COMPLETED | 2026-03-01 | Account Factory setup deployed |
| 1.5 - Test Account Creation | ⏳ PENDING | - | Scripts ready, awaiting user approval |
| 1.6 - Verify Directory Structure | ✅ COMPLETED | 2026-02-27 | All directories exist |
| 1.7 - Install Dependencies | ⏳ PENDING | - | - |
| 2.1 - Create DynamoDB Tables | ⏳ PENDING | - | - |
| 2.2 - Initialize Configuration | ⏳ PENDING | - | - |
| 2.3 - Create Mock Accounts | ⏳ PENDING | - | - |
| 3.1 - Create Shared Utilities | ⏳ PENDING | - | - |
| 3.2 - Implement Account Provider | ⏳ PENDING | - | - |
| 3.3 - Deploy Account Provider | ⏳ PENDING | - | - |
| 4.1 - Create Account Pool | ⏳ PENDING | - | - |
| 4.2 - Test from DataZone | ⏳ PENDING | - | - |
| 4.3 - Create Test Project | ⏳ PENDING | - | - |
| 5.1 - Implement Pool Manager | ⏳ PENDING | - | - |
| 5.2 - Test Replenishment | ⏳ PENDING | - | - |
| 6.1 - Create Dashboard | ⏳ PENDING | - | - |
| 6.2 - Configure Alarms | ⏳ PENDING | - | - |
| 7.1 - End-to-End Test | ⏳ PENDING | - | - |
| 8.1 - Cleanup | ⏳ PENDING | - | - |

---

## Next Steps

**Current Status**: Step 1.4 completed ✅, Step 1.5 ready to test

**Next Action**: Proceed to Step 1.5 - Test Account Creation via Control Tower

**What We've Accomplished So Far**:
1. ✅ Organization structure created with proper banking OUs
2. ✅ CF1 (Control Tower Account Factory) deployed successfully
3. ✅ Test scripts created for account creation workflow
4. ✅ Async account creation with resumable monitoring

**What's Next**:
1. Run `./tests/setup/scripts/test-create-account.sh` to create first test account
2. Verify account creation completes successfully
3. Deploy approved StackSets (VPC, IAM Roles, Blueprints) to test account
4. Continue with DynamoDB and Lambda implementation

**Command to Run**:
```bash
cd experimental/AccountPoolFactory
./tests/setup/scripts/test-create-account.sh
```

**Important Notes**:
- Test account creation is a real AWS account via Control Tower
- Provisioning takes 5-10 minutes
- You can disconnect and reconnect - state is saved in provision files
- Keep test account for StackSet deployment testing
- Delete test account when done: `./tests/setup/scripts/test-delete-account.sh 100`

---

## Troubleshooting

### Common Issues

1. **AccessDenied errors**
   - Verify IAM permissions
   - Check Isengard credentials are active
   - Ensure correct region (us-east-2)

2. **Lambda timeout**
   - Increase timeout in Lambda configuration
   - Check DynamoDB table exists
   - Verify network connectivity

3. **Account pool not visible**
   - Verify Lambda function deployed
   - Check Lambda execution role permissions
   - Review CloudWatch logs

### Support

For issues or questions:
- Review CloudWatch Logs
- Check DynamoDB tables
- Verify configuration in config.yaml
- Consult design.md and requirements.md

---

## Appendix

### A. Configuration Reference

See `config.yaml` for all configuration parameters.

### B. API Reference

See `specs/design.md` section 3 for API specifications.

### C. Architecture Diagrams

See `specs/requirements.md` for architecture diagrams.

### D. Task List

See `specs/tasks.md` for complete implementation task list.

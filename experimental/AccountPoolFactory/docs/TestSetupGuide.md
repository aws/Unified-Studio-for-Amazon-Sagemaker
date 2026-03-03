# Test Setup Guide

This guide helps you set up a clean test environment to simulate a real production deployment. Use this when you're starting from scratch and need to create the prerequisite infrastructure.

## Overview

In a real deployment, you already have:
- AWS Organization configured
- Organizational Units (OUs) created
- DataZone domain deployed

This guide shows you how to create these prerequisites in a test environment so you can then follow the [User Guide](UserGuide.md) for actual Account Pool Factory deployment.

## Test Environment Architecture

```
Test Organization Admin Account (495869084367)
├── AWS Organization (o-nblj7uawmo)
│   └── Organizational Units
│       ├── RetailBanking
│       │   ├── CustomerAnalytics (target for project accounts)
│       │   └── RiskAnalytics
│       └── CommercialBanking

Test Domain Account (994753223772)
└── DataZone Domain (dzd-4igt64u5j25ko9)
```

## Prerequisites

- Two AWS accounts (or one account for simplified testing)
  - Organization Admin account (for AWS Organizations)
  - Domain account (for DataZone domain)
- AWS CLI installed and configured
- IAM permissions (Admin or equivalent)
- Python 3.12+ installed

## Step 1: Configure Test Environment

```bash
cd experimental/AccountPoolFactory

# Copy configuration template
cp config.yaml.template config.yaml

# Edit config.yaml with your test account details
# Set aws.account_id to your Org Admin account
# Set datazone.domain_id to "PLACEHOLDER" (will update after domain creation)
```

## Step 2: Create Organization Structure (Test Only)

**Purpose**: Create OUs to organize project accounts

**Real Deployment**: Skip this - your organization structure already exists

**Test Setup**:
```bash
# Configure credentials for Org Admin account
aws configure
# OR
eval $(isengardcli creds YOUR_ORG_ADMIN_PROFILE --role Admin)

# Deploy organization structure
./tests/setup/scripts/deploy-organization.sh
```

**What This Creates**:
- CloudFormation stack: `AccountPoolFactory-Organization-Test`
- 4 Organizational Units:
  - RetailBanking (parent)
    - CustomerAnalytics (target for project accounts)
    - RiskAnalytics
  - CommercialBanking (parent)
- Outputs saved to: `ou-ids.json`

**Verification**:
```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name AccountPoolFactory-Organization-Test \
  --region us-east-2

# View OUs in console
# Navigate to: AWS Organizations → Organizational structure
```

## Step 3: Create DataZone Domain (Test Only)

**Purpose**: Create a DataZone domain for testing

**Real Deployment**: Skip this - your DataZone domain already exists

**Test Setup**:

**Option A: Via AWS Console** (Recommended)
1. Navigate to DataZone console: https://console.aws.amazon.com/datazone
2. Click "Create domain"
3. Enter domain name (e.g., "test-domain-YYYYMMDD")
4. Select region (e.g., us-east-2)
5. Configure domain settings
6. Wait for domain creation (5-10 minutes)
7. Copy domain ID (dzd-xxxxxxxxxxxxx)

**Option B: Via AWS CLI**
```bash
# Configure credentials for Domain account
aws configure
# OR
eval $(isengardcli creds YOUR_DOMAIN_PROFILE --role Admin)

# Create domain
aws datazone create-domain \
  --name "test-domain-$(date +%Y%m%d-%H%M%S)" \
  --region us-east-2

# Get domain ID from output
# Copy the "id" field (dzd-xxxxxxxxxxxxx)
```

**Update Configuration**:
```bash
# Edit config.yaml and update datazone.domain_id with your new domain ID
# Example: dzd-4igt64u5j25ko9
```

**Verification**:
```bash
# Verify domain exists
aws datazone get-domain \
  --identifier YOUR_DOMAIN_ID \
  --region us-east-2

# Check domain status (should be AVAILABLE)
```

## Step 4: Wait for Initial Pool Population (Optional)

**Purpose**: Allow the Pool Manager to automatically create initial accounts

**Real Deployment**: The Pool Manager Lambda runs every 5 minutes and will automatically create accounts to reach minimum pool size

**Test Setup**:

After deploying CF2 (Account Provider Lambda) and configuring pool settings, the Pool Manager will automatically:
1. Check current pool size
2. Compare against minimum pool size configuration
3. Create new accounts if below minimum
4. Configure accounts via Setup Orchestrator
5. Mark accounts as AVAILABLE

**Monitor Pool Population**:
```bash
# Check pool status
./tests/setup/scripts/check-pool-status.sh

# Watch CloudWatch logs for Pool Manager
aws logs tail /aws/lambda/PoolManager-YOUR_DOMAIN_ID --follow

# Check available accounts in DynamoDB
aws dynamodb query \
  --table-name AccountPool-YOUR_DOMAIN_ID \
  --index-name StateIndex \
  --key-condition-expression "State = :state" \
  --expression-attribute-values '{":state": {"S": "AVAILABLE"}}' \
  --region us-east-2
```

**Trigger Manual Pool Check** (Optional):
```bash
# Invoke Pool Manager Lambda to check pool immediately
aws lambda invoke \
  --function-name PoolManager-YOUR_DOMAIN_ID \
  --region us-east-2 \
  response.json

cat response.json
```

**Expected Timeline**:
- Pool Manager runs: Every 5 minutes (configurable)
- Account creation: < 1 minute (Organizations API) or 10-15 minutes (Control Tower)
- Account configuration: 5-10 minutes (VPC, IAM roles, blueprints)
- Total time to first available account: ~10-15 minutes

**In Real Deployment**: Same process - Pool Manager automatically maintains pool size based on configuration.

## Step 5: Deploy VPC to Test Accounts (If Testing Manually Created Accounts)

**Purpose**: Pre-configure manually created test accounts with VPC for testing

**Real Deployment**: Skip this - VPC will be deployed automatically by Setup Orchestrator

**When to Use**: Only if you manually created test accounts outside the pool system for development/debugging purposes

**Test Setup**:
```bash
# Get test account ID (if you created accounts manually for testing)
TEST_ACCOUNT_ID=123456789012

# Deploy VPC StackSet instance
aws cloudformation create-stack-instances \
  --stack-set-name AccountPoolFactory-ControlTower-Test-VPCSetup \
  --accounts $TEST_ACCOUNT_ID \
  --regions us-east-2 \
  --parameter-overrides \
    ParameterKey=useVpcEndpoints,ParameterValue=false

# Wait for deployment (2-3 minutes)
aws cloudformation wait stack-instance-create-complete \
  --stack-set-name AccountPoolFactory-ControlTower-Test-VPCSetup \
  --stack-instance-account $TEST_ACCOUNT_ID \
  --stack-instance-region us-east-2
```

**Note**: Accounts created by the Pool Manager will have VPC automatically deployed by the Setup Orchestrator Lambda.

## Test Environment Ready!

Your test environment now matches a real production environment:
- ✅ AWS Organization with OUs
- ✅ DataZone domain created
- ✅ (Optional) Test accounts created and configured

## Next Steps

Now follow the [User Guide](UserGuide.md) to deploy the Account Pool Factory:

1. **Organization Administrator**: Deploy CF1 (Account Factory Setup)
2. **Organization Administrator**: Deploy Approved StackSets
3. **Domain Administrator**: Deploy CF2 (Account Provider Lambda)
4. **Domain Administrator**: Create Account Pool
5. **Domain Administrator**: Add accounts to pool
6. **Domain Administrator**: Create project profile
7. **Project Creator**: Create projects

## Cleanup Test Environment

When you're done testing, clean up resources:

```bash
# Delete test accounts
./tests/setup/scripts/test-delete-account.sh 100
./tests/setup/scripts/test-delete-account.sh 101
./tests/setup/scripts/test-delete-account.sh 102

# Delete CloudFormation stacks
aws cloudformation delete-stack \
  --stack-name AccountPoolFactory-Organization-Test \
  --region us-east-2

aws cloudformation delete-stack \
  --stack-name AccountPoolFactory-ControlTower-Test \
  --region us-east-2

aws cloudformation delete-stack \
  --stack-name AccountPoolFactory-DomainSharing-Test \
  --region us-east-2

# Delete DataZone domain (via console or CLI)
aws datazone delete-domain \
  --identifier YOUR_DOMAIN_ID \
  --region us-east-2

# Delete StackSets
aws cloudformation delete-stack-set \
  --stack-set-name AccountPoolFactory-ControlTower-Test-VPCSetup \
  --region us-east-2

aws cloudformation delete-stack-set \
  --stack-set-name AccountPoolFactory-ControlTower-Test-IAMRoles \
  --region us-east-2

aws cloudformation delete-stack-set \
  --stack-set-name AccountPoolFactory-ControlTower-Test-BlueprintEnablement \
  --region us-east-2
```

## Troubleshooting

### Organization Structure Creation Fails
- Verify you have Organizations permissions
- Check if OUs with same names already exist
- Ensure you're in the Organization Admin account

### DataZone Domain Creation Fails
- Verify DataZone is available in your region
- Check IAM permissions for DataZone
- Ensure you're in the Domain account

### Test Account Creation Fails
- Verify CF1 stack is deployed
- Check account email is unique
- Ensure you have Organizations:CreateAccount permission
- For Control Tower: Verify Control Tower is enabled

### VPC Deployment Fails
- Verify StackSet exists
- Check AWSControlTowerExecution role exists in target account
- Ensure target account is in correct OU

## Reference

- [User Guide](UserGuide.md) - Real deployment instructions
- [Testing Guide](TestingGuide.md) - Comprehensive testing procedures
- [Development Progress](DevelopmentProgress.md) - What's working, lessons learned

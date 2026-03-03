# Account Pool Factory - Development Progress

This document tracks the development journey, experiments, and lessons learned during implementation.

## Current Status

**Last Updated**: March 3, 2026

**Overall Progress**: Phase 3 Complete (End-to-End Project Creation Working)

### Quick Summary

✅ Infrastructure setup complete (CF1, Organization structure, test accounts)
✅ Account pool integration working (Lambda, DataZone integration)
✅ Domain sharing working (RAM with correct permissions)
✅ Project account setup complete (IAM roles, blueprints, policy grants)
✅ End-to-end project creation with environment deployment working

### What's Working Right Now

- Organizations API account creation (< 1 minute)
- VPC deployment to project accounts
- IAM roles deployment (ManageAccess + Provisioning with AdministratorAccess)
- Blueprint enablement (17 blueprints)
- Policy grants for blueprint authorization
- DataZone account pool with Lambda integration
- Account authorization workflow
- Domain sharing via RAM (per-account approach)
- Project creation with environment deployment (Tooling environment ACTIVE)

### Current Blockers

None! Ready to implement Setup Orchestrator Lambda for automated account setup.

## Completed Milestones

### Phase 1: Infrastructure Setup ✅

#### 1.1 Organization Structure (Feb 27, 2026)
- Created 4 OUs across 2 business units (RetailBanking, CommercialBanking)
- Target OUs: CustomerAnalytics, RiskAnalytics
- CloudFormation template: `01-org-admin/organization-structure.yaml`
- Stack: AccountPoolFactory-Organization-Test

#### 1.2 Control Tower Account Factory (CF1) (Mar 1, 2026)
- Deployed CF1 with multi-strategy support
- Selected Organizations API strategy (faster for testing)
- EventBridge integration for account lifecycle events
- Stack: AccountPoolFactory-ControlTower-Test
- Key outputs: AccountCreationRoleArn, EventBusArn

#### 1.3 Account Creation Testing (Mar 1, 2026)
- Created 2 test accounts successfully
  - Account 100: 004878717744 (TestAccount-OrgsApi-100)
  - Account 101: 400398152132 (TestAccount-OrgsApi-101)
- Account creation time: < 1 minute (Organizations API)
- Accounts moved to CustomerAnalytics OU
- EventBridge events emitted successfully

#### 1.4 StackSet Deployment (Mar 1, 2026)
- Deployed VPC StackSet to account 100
- VPC ID: vpc-0d764624c03680061 (10.38.0.0/16)
- 3 private subnets across 3 AZs
- Deployment time: ~2.5 minutes
- Status: SUCCEEDED ✅

#### 1.5 Account Pool Integration (Mar 2-3, 2026)
- Created DataZone account pool with Lambda integration
- Pool ID: d47walsa85zkx5
- Deployed Account Provider Lambda
- Lambda successfully invoked by DataZone
- Validated account authorization workflow

### Phase 2: Account Pool Setup ✅

#### 2.1 Lambda Development (Mar 2, 2026)
- Implemented Account Provider Lambda
- Supports ListAccountsInAccountPool API
- Supports ValidateAccountAuthorizationRequest API
- CloudWatch logging with emojis and timestamps
- CloudWatch metrics published

#### 2.2 Project Profile Creation (Mar 2, 2026)
- Created project profile with account pool integration
- Profile ID: 3q3bu487vip8a1
- Configured 8 blueprints (Tooling, DataLake, etc.)
- Added policy grants for blueprints

#### 2.3 Project Creation Testing (Mar 3, 2026)
- Successfully created project with account pool
- Project ID: dc8wy15jbbh8yx
- Account: 004878717744 (TestAccount-100)
- Lambda invoked for authorization
- Authorization result: GRANT ✅

## Key Findings

### 1. IAM Role Permissions Boundary Issue
**Date**: March 3, 2026

**Discovery**: AmazonDataZoneEnvironmentRolePermissionsBoundary causes explicit deny on required permissions.

**Problem**: The AWS managed policy `AmazonDataZoneEnvironmentRolePermissionsBoundary` has a "NotDeniedOperations" statement that explicitly denies all actions NOT in its allow list. Critical actions like `glue:GetDataCatalogEncryptionSettings` and `lakeformation:GetDataLakeSettings` are missing from the allow list.

**Solution**: 
- Do NOT attach AmazonDataZoneEnvironmentRolePermissionsBoundary as a managed policy
- For isolated project accounts, use AdministratorAccess on ProvisioningRole
- For ManageAccessRole, use custom inline policies with required permissions

**Impact**: Environment deployment now works without permission errors.

### 2. Policy Grants Must Be in Project Account
**Date**: March 3, 2026

**Discovery**: Policy grants for blueprints must be created in the PROJECT account, not the domain account.

**Evidence**:
- Domain account blueprints: Entity identifier `994753223772:${BlueprintId}`, grants in domain account
- Project account blueprints: Entity identifier `004878717744:${BlueprintId}`, grants in project account
- Creating grants in wrong account results in 403 authorization errors

**Correct Structure**:
```json
{
  "DomainIdentifier": "dzd-4igt64u5j25ko9",
  "EntityType": "ENVIRONMENT_BLUEPRINT_CONFIGURATION",
  "EntityIdentifier": "004878717744:6bbrztdwfxomeh",
  "PolicyType": "CREATE_ENVIRONMENT_FROM_BLUEPRINT",
  "Principal": {
    "Project": {
      "ProjectDesignation": "CONTRIBUTOR",
      "ProjectGrantFilter": {
        "DomainUnitFilter": {
          "DomainUnit": "6kg8zlq8mvid9l",
          "IncludeChildDomainUnits": true
        }
      }
    }
  }
}
```

**Impact**: Projects can now create environments from blueprints in project accounts.

### 3. S3 Bucket Required for Blueprints
**Date**: March 3, 2026

**Discovery**: Blueprint enablement requires an S3 bucket for artifacts, but CloudFormation doesn't create it.

**Solution**: Create S3 bucket before enabling blueprints
- Bucket name format: `datazone-blueprints-${AccountId}-${Region}`
- Example: `s3://datazone-blueprints-004878717744-us-east-2`

**Impact**: Added S3 bucket creation to account setup workflow.

### 4. ON_CREATE Does NOT Work with Account Pools
### 4. ON_CREATE Does NOT Work with Account Pools
**Date**: March 2, 2026

**Discovery**: ON_CREATE deployment mode is incompatible with account pools using MANUAL resolution strategy.

**Evidence**:
- Tested with 4 blueprints as ON_CREATE: 0 environments created
- Tested with 1 blueprint as ON_CREATE: 0 environments created
- Lambda never invoked during project creation
- API model shows MANUAL as only resolution strategy

**Conclusion**: All environments must be created manually (ON_DEMAND) when using account pools.

**Impact**: Updated requirements and design to reflect manual environment creation workflow.

### 5. Lambda Event Structure
### 5. Lambda Event Structure
**Date**: March 3, 2026

**Critical Bug Fix**: Event uses `regionName` not `awsRegion`

**Correct Event Structure**:
```python
# validateAccountAuthorizationRequest
{
  "operationRequest": {
    "validateAccountAuthorizationRequest": {
      "domainIdentifier": "dzd-xxxxxxxxxxxxx",
      "awsAccountId": "123456789012",
      "regionName": "us-east-2",  # NOT awsRegion!
      "userIdentifier": "user-id"
    }
  }
}
```

**Fix Applied**: Updated Lambda to use `request.get('regionName')` instead of `request.get('awsRegion')`

### 6. AccountResolutionRole Trust Policy
### 6. AccountResolutionRole Trust Policy
**Date**: March 3, 2026

**Issue**: DataZone does NOT pass `aws:SourceAccount` or `aws:SourceArn` context keys

**Impact**: Trust policy cannot have these conditions (causes authorization failures)

**Workaround**: Use basic trust policy without source account conditions

### 7. Organizations API vs Control Tower
### 7. Organizations API vs Control Tower
**Date**: March 1, 2026

**Comparison**:
- Organizations API: < 1 minute, simpler, lower cost
- Control Tower: 10-15 minutes, automatic governance, higher cost

**Recommendation**: Use Organizations API for testing, Control Tower for production

### 8. StackSet Deployment Success
**Date**: March 1, 2026

**Finding**: StackSets work perfectly with Organizations API accounts

**Evidence**:
- VPC StackSet deployed successfully to account 100
- Deployment time: ~2.5 minutes
- All resources created correctly

**Conclusion**: No need for Control Tower enrollment for StackSet deployments

## Account Setup Requirements

### Complete Setup Workflow

When a new account is added to the pool, the following setup steps must be completed:

#### 1. VPC Deployment
- Deploy VPC with 3 private subnets across 3 AZs
- VPC CIDR: 10.x.0.0/16 (x = account-specific)
- Subnet CIDRs: 10.x.0.0/24, 10.x.1.0/24, 10.x.2.0/24
- Template: `templates/cloudformation/03-project-account/vpc-setup.yaml`
- Deployment time: ~2.5 minutes

#### 2. IAM Roles Deployment
- Deploy DataZoneManageAccessRole with custom inline policies
- Deploy DataZoneProvisioningRole with AdministratorAccess
- Template: `templates/cloudformation/03-project-account/iam-roles.yaml`
- Key requirement: Do NOT use AmazonDataZoneEnvironmentRolePermissionsBoundary
- Deployment time: ~2 minutes

#### 3. S3 Bucket Creation
- Create S3 bucket for blueprint artifacts
- Bucket name: `datazone-blueprints-${AccountId}-${Region}`
- Example: `s3://datazone-blueprints-004878717744-us-east-2`
- Required before blueprint enablement

#### 4. Blueprint Enablement
- Enable all 17 DataZone blueprints
- Template: `templates/cloudformation/03-project-account/blueprint-enablement.yaml`
- Parameters: DomainId, ManageAccessRoleArn, ProvisioningRoleArn, S3Location, Subnets, VpcId
- Deployment time: ~3 minutes
- Blueprints: LakehouseCatalog, AmazonBedrockGuardrail, MLExperiments, Tooling, RedshiftServerless, EmrServerless, Workflows, AmazonBedrockPrompt, DataLake, AmazonBedrockEvaluation, AmazonBedrockKnowledgeBase, PartnerApps, AmazonBedrockChatAgent, AmazonBedrockFunction, AmazonBedrockFlow, EmrOnEc2, QuickSight

#### 5. Policy Grants Creation
- Create policy grants in PROJECT account (not domain account)
- One grant per blueprint (17 total)
- Script: `tests/setup/scripts/deploy-policy-grants-project-account.sh`
- Entity identifier: `${AccountId}:${BlueprintId}`
- Principal: Project with CONTRIBUTOR designation, root domain unit filter
- Deployment time: ~2 minutes

#### 6. Domain Sharing (RAM)
- Create RAM share in domain account
- Associate domain ARN as resource
- Associate project account as principal
- Permission: AWSRAMPermissionsAmazonDatazoneDomainExtendedServiceWithPortalAccess
- Template: `templates/cloudformation/02-domain-account/domain-sharing-setup.yaml`
- Deployment time: ~1 minute

### Total Setup Time
- Estimated: 10-12 minutes per account
- Critical path: VPC → IAM Roles → S3 Bucket → Blueprints → Policy Grants
- Parallel: Domain sharing can happen anytime

### Verification Steps
1. Verify domain visible in project account: `aws datazone list-domains`
2. Verify blueprints enabled: `aws datazone list-environment-blueprint-configurations`
3. Verify policy grants exist: `aws datazone list-policy-grants`
4. Test project creation with environment deployment

## Experiments and Tests

### Test 1: Four Blueprints as ON_CREATE
- **Date**: March 2, 2026
- **Profile ID**: 3q3bu487vip8a1
- **Test Project**: 4own4h2510q9wp
- **Configuration**: 4 ON_CREATE, 4 ON_DEMAND
- **Result**: ❌ 0 environments created, Lambda NOT invoked

### Test 2: Only Tooling as ON_CREATE
- **Date**: March 2, 2026
- **Profile ID**: 3q3bu487vip8a1 (updated)
- **Test Project**: 62aerryv7mwq3t
- **Configuration**: 1 ON_CREATE, 7 ON_DEMAND
- **Result**: ❌ 0 environments created, Lambda NOT invoked

### Test 3: Manual Lambda Invocation
- **Date**: March 2, 2026
- **Result**: ✅ Lambda works perfectly
- **Output**: Returns account 004878717744 with region us-east-2
- **Logs**: Comprehensive logging with emojis and timestamps

### Test 4: Project Creation with Account Pool
- **Date**: March 3, 2026
- **Project ID**: dc8wy15jbbh8yx
- **Result**: ✅ Project created, Lambda invoked for authorization
- **Authorization**: GRANT
- **Deployment**: FAILED (expected - CF3 not deployed yet)

## Pending Work

### Phase 3: Project Account Setup (CF3) ✅

#### 3.1 IAM Roles Deployment (Mar 3, 2026)
- Deployed DataZoneManageAccessRole and DataZoneProvisioningRole
- Stack: DataZone-IAM-Roles (account 004878717744)
- ManageAccessRole: Custom inline policies for Lake Formation, Glue, IAM, S3
- ProvisioningRole: AdministratorAccess policy (isolated account, no fine-grained permissions needed)
- Key Finding: AmazonDataZoneEnvironmentRolePermissionsBoundary NOT needed (causes explicit deny)

#### 3.2 Blueprint Enablement (Mar 3, 2026)
- Enabled 17 DataZone blueprints in project account
- Stack: DataZone-Blueprint-Enablement (account 004878717744)
- Blueprints: LakehouseCatalog, AmazonBedrockGuardrail, MLExperiments, Tooling, RedshiftServerless, EmrServerless, Workflows, AmazonBedrockPrompt, DataLake, AmazonBedrockEvaluation, AmazonBedrockKnowledgeBase, PartnerApps, AmazonBedrockChatAgent, AmazonBedrockFunction, AmazonBedrockFlow, EmrOnEc2, QuickSight
- S3 bucket created: s3://datazone-blueprints-004878717744-us-east-2
- Regional parameters: VPC, Subnets, S3Location configured

#### 3.3 Policy Grants Deployment (Mar 3, 2026)
- Deployed policy grants in PROJECT account (not domain account)
- Stack: DataZone-PolicyGrants (account 004878717744)
- 17 policy grants created (one per blueprint)
- Entity identifier format: `${AccountId}:${BlueprintId}` (e.g., 004878717744:6bbrztdwfxomeh)
- Principal: Project with CONTRIBUTOR designation
- Domain unit filter: Root domain unit with includeChildDomainUnits=true
- Key Finding: Grants must be created in the account where blueprints are enabled

#### 3.4 End-to-End Testing (Mar 3, 2026)
- Created test project: bp6rl6jtk3p2cp
- Account: 004878717744 (TestAccount-100)
- Environment: Tooling (ACTIVE)
- Deployment status: SUCCESSFUL
- Project owner: analyst1-amirbo (added as PROJECT_OWNER)
- Total deployment time: ~3 minutes

### Phase 4: Setup Orchestrator
- [ ] Implement Setup Orchestrator Lambda
- [ ] Automate CF3 deployment on account assignment
- [ ] Create RAM share for domain
- [ ] Verify domain visibility in project account
- [ ] Enable blueprints automatically
- [ ] Create policy grants automatically

### Phase 5: Pool Management
- [ ] Implement Pool Manager Lambda
- [ ] Monitor pool size and replenishment
- [ ] CloudWatch dashboard for pool health
- [ ] Alarms for low pool size

### Phase 6: Multi-Account Testing
- [ ] Test with separate Org Admin account
- [ ] Test with separate Domain account
- [ ] Verify cross-account EventBridge
- [ ] Test StackSet deployment across accounts

## Technical Debt

### 1. Placeholder Lambda ARNs
- **Issue**: Account pool created with placeholder Lambda ARNs
- **Impact**: Pool doesn't work until Lambda is deployed
- **Fix**: Update account pool after Lambda deployment

### 2. Manual Environment Creation
- **Issue**: ON_CREATE doesn't work with account pools
- **Impact**: Users must create environments manually
- **Documentation**: Updated requirements and user guide

### 3. CF3 Deployment
- **Issue**: Project accounts need manual CF3 deployment
- **Impact**: Environment creation fails without CF3
- **Solution**: Implement Setup Orchestrator Lambda

### 4. Trust Policy Limitations
- **Issue**: Cannot use source account conditions in trust policy
- **Impact**: Less secure trust policy
- **Workaround**: Use basic trust policy, rely on Lambda validation

## Lessons Learned

### 1. Start with Organizations API
Organizations API is much faster for testing and development. Control Tower can be added later for production governance.

### 2. Test Lambda Manually First
Manual Lambda testing revealed the event structure and helped debug issues before DataZone integration.

### 3. Read API Models Carefully
The DataZone API model revealed that MANUAL is the only resolution strategy, explaining the ON_CREATE behavior.

### 4. Trust CloudWatch Logs
Comprehensive logging with timestamps and emojis made debugging much easier.

### 5. StackSets Are Powerful
StackSets provide a clean way to deploy approved templates to multiple accounts with proper governance.

## Performance Metrics

### Account Creation
- Organizations API: < 1 minute
- Control Tower: 10-15 minutes

### StackSet Deployment
- VPC Setup: ~2.5 minutes
- IAM Roles: ~2 minutes (estimated)
- Blueprint Enablement: ~3 minutes (estimated)

### Lambda Performance
- ListAccountsInAccountPool: < 100ms
- ValidateAccountAuthorizationRequest: < 100ms

### Project Creation
- Without environments: < 5 seconds
- With environment deployment: 5-10 minutes (depends on blueprint)

## Test Accounts

### Account 100
- **Account ID**: 004878717744
- **Email**: amirbo+100@amazon.com
- **Name**: TestAccount-OrgsApi-100
- **OU**: CustomerAnalytics
- **VPC**: vpc-0d764624c03680061 (10.38.0.0/16)
- **Status**: VPC deployed ✅

### Account 101
- **Account ID**: 400398152132
- **Email**: amirbo+101@amazon.com
- **Name**: TestAccount-OrgsApi-101
- **OU**: CustomerAnalytics
- **Status**: Available for testing

## Configuration Files

### Generated Files
- `ou-ids.json` - Organization structure outputs
- `cf1-outputs.json` - CF1 stack outputs
- `account-pool-details.json` - Account pool configuration
- `project-profile-details.json` - Project profile summary
- `project-profile-full-details.json` - Complete profile configuration
- `test-project-details.json` - Test project information
- `test-account-provision-100.json` - Account 100 provisioning details
- `test-account-provision-101.json` - Account 101 provisioning details

### CloudFormation Stacks
- `AccountPoolFactory-Organization-Test` - Organization structure
- `AccountPoolFactory-ControlTower-Test` - CF1 (Account Factory)
- `AccountPoolFactory-ControlTower-Test-VPCSetup` - VPC StackSet
- `AccountPoolFactory-ControlTower-Test-IAMRoles` - IAM Roles StackSet (pending)
- `AccountPoolFactory-ControlTower-Test-BlueprintEnablement` - Blueprint StackSet (pending)

## Next Steps

1. Deploy IAM Roles StackSet to account 100
2. Deploy Blueprint Enablement StackSet to account 100
3. Test manual environment creation
4. Implement Setup Orchestrator Lambda
5. Test complete workflow end-to-end

## References

- [User Guide](UserGuide.md) - Simplified user-facing documentation
- [Testing Guide](TestingGuide.md) - Detailed testing procedures
- [Requirements](../specs/requirements.md) - Functional requirements
- [Design](../specs/design.md) - Technical design
- [Success Report](../ACCOUNT_POOL_SUCCESS.md) - Account pool integration success
- [Findings Report](../ACCOUNT_POOL_FINDINGS.md) - ON_CREATE investigation findings


## Test Accounts Inventory

### Account 100
- **Account ID**: 004878717744
- **Email**: amirbo+100@amazon.com
- **Name**: TestAccount-OrgsApi-100
- **Strategy**: organizations_api
- **Status**: SUCCEEDED
- **OU**: ou-n5om-otvkrtx2 (CustomerAnalytics)
- **Created**: 2026-03-01T22:48:45Z
- **VPC Deployed**: ✅ Yes (vpc-0d764624c03680061)
- **Domain Associated**: ✅ Yes (via RAM share)
- **Domain Visible**: ✅ Yes (verified via API)
- **File**: `tests/setup/test-accounts/test-account-provision-100.json`

### Account 101
- **Account ID**: 400398152132
- **Email**: amirbo+101@amazon.com
- **Name**: TestAccount-OrgsApi-101
- **Strategy**: organizations_api
- **Status**: SUCCEEDED
- **OU**: ou-n5om-otvkrtx2 (CustomerAnalytics)
- **Created**: 2026-03-01T22:53:34Z
- **VPC Deployed**: ❌ No
- **Domain Associated**: ✅ Yes (via RAM share)
- **Domain Visible**: ⏳ To be verified
- **File**: `tests/setup/test-accounts/test-account-provision-101.json`

## CloudFormation Stacks Status

### Deployed Stacks ✅
1. **AccountPoolFactory-Organization-Test**
   - Status: CREATE_COMPLETE
   - Purpose: Organization structure with OUs
   - Outputs: Saved to `ou-ids.json`

2. **AccountPoolFactory-ControlTower-Test**
   - Status: CREATE_COMPLETE
   - Purpose: Control Tower Account Factory setup (CF1)
   - Strategy: organizations_api
   - Outputs: Saved to `cf1-outputs.json`

3. **AccountPoolFactory-DomainSharing-Test**
   - Status: CREATE_COMPLETE ✅
   - Purpose: Domain sharing via RAM (CF2)
   - Working: Domain visible in project accounts
   - Outputs: RAM shares created for accounts 100 & 101
   - Template: `templates/cloudformation/02-domain-account/domain-sharing-setup.yaml`

4. **AccountPoolFactory-ControlTower-Test-VPCSetup** (StackSet)
   - Status: CURRENT ✅
   - Purpose: VPC deployment to project accounts
   - Deployed to: Account 100 (004878717744)
   - VPC ID: vpc-0d764624c03680061 (10.38.0.0/16)

### Pending Stacks ⏳
5. **AccountPoolFactory-ControlTower-Test-IAMRoles** (StackSet)
   - Purpose: IAM roles for DataZone blueprint management
   - Blocked by: Domain setup completion

6. **AccountPoolFactory-ControlTower-Test-BlueprintEnablement** (StackSet)
   - Purpose: Enable all 17 DataZone blueprints
   - Blocked by: IAM roles deployment

## Domain Sharing Solution

### Working Approach
**Per-account RAM shares with correct permission ARN**

### Critical Discovery
The permission ARN must include "WithPortalAccess":
- ✅ `AWSRAMPermissionsAmazonDatazoneDomainExtendedServiceWithPortalAccess`
- ❌ `AWSRAMPermissionsAmazonDatazoneDomainExtendedServiceAccess`

### Implementation Details
- **Template**: `templates/cloudformation/02-domain-account/domain-sharing-setup.yaml`
- **Method**: One RAM share per account using `Fn::ForEach`
- **Acceptance**: Automatic within same organization
- **Verification**: Domain visible in project accounts via DataZone API

### Test Results
- ✅ CF stack deployed successfully
- ✅ 2 RAM shares created (one per account)
- ✅ Domain resource associated with both shares
- ✅ Domain visible in project account 004878717744
- ✅ Domain status: AVAILABLE
- ✅ No manual console steps required

### Organization-Level Sharing
- ❌ NOT supported for DataZone domains
- Tested and failed with "Principal ID is malformed" error
- Must use per-account sharing approach

### Commands Used

**Deploy Stack**:
```bash
eval $(isengardcli creds amirbo+3 --role Admin)

aws cloudformation deploy \
  --template-file templates/cloudformation/02-domain-account/domain-sharing-setup.yaml \
  --stack-name AccountPoolFactory-DomainSharing-Test \
  --parameter-overrides \
    DomainId="dzd-4igt64u5j25ko9" \
    DomainName="domain-03-01-2026-182246" \
    DomainArn="arn:aws:datazone:us-east-2:994753223772:domain/dzd-4igt64u5j25ko9" \
    ProjectAccountIds="004878717744,400398152132" \
    EnableSharing="true" \
  --region us-east-2
```

**Verify in Project Account**:
```bash
# Assume role in project account
eval $(isengardcli creds amirbo+1 --role Admin)
CREDS=$(aws sts assume-role \
  --role-arn "arn:aws:iam::004878717744:role/OrganizationAccountAccessRole" \
  --role-session-name "test" \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text)

export AWS_ACCESS_KEY_ID=$(echo $CREDS | awk '{print $1}')
export AWS_SECRET_ACCESS_KEY=$(echo $CREDS | awk '{print $2}')
export AWS_SESSION_TOKEN=$(echo $CREDS | awk '{print $3}')

# List domains
aws datazone list-domains --region us-east-2
```

## Multi-Strategy Account Creation

### Performance Comparison

| Metric | Organizations API | Control Tower | Winner |
|--------|------------------|---------------|---------|
| Provisioning Time | < 1 minute | 10-15 minutes | Organizations API |
| Prerequisites | Organizations only | Control Tower + Organizations | Organizations API |
| Cost | Lower | Higher (Control Tower fees) | Organizations API |
| Governance | Manual | Automatic guardrails | Control Tower |
| Complexity | Simple | Complex | Organizations API |

### CF1 Stack Update Results

**Stack**: AccountPoolFactory-ControlTower-Test
**Strategy Selected**: organizations_api
**Update Duration**: ~2 minutes

**Changes Applied**:
- Removed Control Tower-specific resources (not needed for Organizations API)
- Added OrganizationsApiAccountCreationPolicy with Organizations permissions
- Added OrganizationsApiAccountCreationRule for custom events
- Added OrganizationsApiEventForwardingRole
- Added AccountCreationStrategyParameter (SSM)
- Added OrganizationsConfigParameter (SSM)
- Modified AccountCreationRole to use new policy
- Modified ForwardToRequestingAccountRule to handle both event sources

### Organizations API Test Results

**Test Account Details**:
- Email: amirbo+100@amazon.com
- Name: TestAccount-OrgsApi-100
- Account ID: 004878717744
- Request ID: car-554f55c5a22b47acb6e7693876443e43

**Timeline**:
- Creation initiated: 16:48:47
- Status check attempt 1: SUCCEEDED (< 10 seconds!)
- Account moved to target OU: Success
- Total time: < 1 minute (much faster than expected 5-8 minutes!)

**Verification**:
```bash
aws organizations describe-account --account-id 004878717744
```
- Status: ACTIVE ✅
- Email: amirbo+100@amazon.com ✅
- Name: TestAccount-OrgsApi-100 ✅
- JoinedMethod: CREATED ✅

### VPC StackSet Deployment Results

**Target Account**: 004878717744 (TestAccount-OrgsApi-100)
**StackSet Name**: AccountPoolFactory-ControlTower-Test-VPCSetup
**Operation ID**: e39101ef-9fa4-40cc-8aee-49660ff8c038

**Timeline**:
- Operation initiated: 23:12:08 UTC
- Operation completed: 23:14:31 UTC
- Total time: ~2.5 minutes

**Stack Instance Status**: CURRENT ✅
**Stack Status**: CREATE_COMPLETE ✅

**Resources Created**:
- VPC ID: vpc-0d764624c03680061
- VPC CIDR: 10.38.0.0/16
- VPC Name: SageMakerUnifiedStudioVPC
- Private Subnets: 3 subnets across 3 AZs
  - subnet-0f5bf55074875ddb0 (us-east-2a)
  - subnet-02b257c30ca46056e (us-east-2b)
  - subnet-0be15065bbb85a4fa (us-east-2c)

**Key Findings**:
1. StackSet deployment works perfectly with Organizations API accounts
2. AWSControlTowerExecution role setup script works correctly
3. VPC resources created successfully in target account
4. CloudFormation stack outputs are properly configured
5. Ready for DataZone domain setup in next phase

## Issues Encountered and Fixed

### Issue 1: EventBridge Rule Configuration
**Problem**: OrganizationsApiAccountCreationRule tried to use same event bus as source and target
**Error**: "Source EventBus and Target EventBus must not be the same"
**Fix**: Changed rule to listen on default bus and forward to AccountLifecycleEventBus
**Status**: ✅ Fixed

### Issue 2: ou-ids.json Format
**Problem**: Script expected object format, but file was array format
**Error**: `Cannot index array with string "CustomerAnalytics"`
**Fix**: Updated jq query to filter array: `.[] | select(.OutputKey=="TargetOUId") | .OutputValue`
**Status**: ✅ Fixed

### Issue 3: CloudFormation Permissions
**Problem**: Assumed role didn't have CloudFormation:DescribeStacks permission
**Error**: AccessDenied when trying to get EventBusName from stack outputs
**Fix**: Hardcoded event bus name (known value: AccountPoolFactoryEventBus)
**Status**: ✅ Fixed (account already created, EventBridge event emission is optional for testing)

## Configuration

### Current Environment
- **AWS Account (Org Admin)**: 495869084367
- **AWS Account (Domain)**: 994753223772 (amirbo+3@amazon.com)
- **Region**: us-east-2
- **Profile (Org Admin)**: amirbo+1 (Admin role via Isengard CLI)
- **Profile (Domain)**: amirbo+3 (Admin role via Isengard CLI)
- **Organization**: o-nblj7uawmo
- **Domain ID**: dzd-4igt64u5j25ko9 ✅
- **Domain Name**: domain-03-01-2026-182246
- **Domain Account**: 994753223772
- **Portal URL**: https://dzd-4igt64u5j25ko9.sagemaker.us-east-2.on.aws
- **Git Branch**: amirbo_account_factory_initial

### Configuration Files
- `config.yaml` - Main configuration (up to date)
- `ou-ids.json` - Organization structure outputs
- `cf1-outputs.json` - CF1 stack outputs
- `account-pool-details.json` - Account pool configuration
- `project-profile-details.json` - Project profile summary
- `project-profile-full-details.json` - Complete profile configuration
- `test-project-details.json` - Test project information
- `tests/setup/test-accounts/*.json` - Test account records

## Account Setup Orchestration Workflow

The Setup Orchestrator Lambda coordinates the complete account setup after creation:

```
Account Created Event
    ↓
1. Create RAM Share (Domain Account)
   - Create AWS RAM resource share
   - Associate domain ARN as resource
   - Associate new account ID as principal
   - Use correct permission ARN with portal access
   - Wait for share to become ACTIVE
    ↓
2. Verify Domain Visibility (New Account)
   - Assume role in new account
   - Call DataZone ListDomains API
   - Verify domain is visible and status is AVAILABLE
   - Retry with exponential backoff if not yet visible
    ↓
3. Deploy CF3 StackSet (New Account)
   - Deploy baseline IAM roles and security configuration
   - Wait for StackSet deployment to complete
   - Verify all resources created successfully
    ↓
4. Enable Blueprints (New Account)
   - For each configured blueprint:
     - Call DataZone EnableBlueprint API
     - Provide required parameters (roles, VPC, subnets)
     - Verify blueprint enabled successfully
    ↓
5. Create Policy Grants (Domain Account)
   - Grant CREATE_ENVIRONMENT_FROM_BLUEPRINT permissions
   - Grant CREATE_PROJECT_FROM_PROJECT_PROFILE permissions
    ↓
6. Mark Account as AVAILABLE
   - Validate all setup steps completed
   - Update DynamoDB account state to AVAILABLE
   - Emit CloudWatch metrics
   - Send SNS notification
```

### Error Handling
- Each step includes retry logic with exponential backoff
- Failed steps logged with detailed error information
- Account marked as FAILED if max retries exceeded
- SNS alert sent for manual intervention
- Partial setup can be resumed from last successful step
- Setup progress tracked in DynamoDB for debugging

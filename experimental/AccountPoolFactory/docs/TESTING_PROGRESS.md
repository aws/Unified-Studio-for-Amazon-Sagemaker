# Account Pool Factory - Testing Progress

## Test Environment

**Date Started**: March 3, 2026
**Domain Type**: IAM-based (changed from IDC)
**Region**: us-east-2
**Tester**: User

## Test Objectives

1. Deploy complete Account Pool Factory infrastructure
2. Verify all Lambda functions work correctly
3. Test account creation and setup workflow
4. Verify DataZone integration with IAM-based domain
5. Test project creation with account pool
6. Validate monitoring and alerting
7. Test account deletion and cleanup

## Prerequisites Status

### AWS Accounts
- [ ] Organization Admin Account: 495869084367
- [ ] Domain Account: 994753223772
- [ ] Target OU created and identified

### Domain Configuration
- [x] New IAM-based DataZone domain created
- [x] Domain ID obtained: dzd-5o0lje5xgpeuw9
- [x] Domain ARN obtained
- [x] Root domain unit ID obtained: 563ikhcj7fgkrt
- [x] config.yaml updated with new domain details

### AWS CLI and Tools
- [ ] AWS CLI configured
- [ ] Python 3.12+ installed
- [ ] Git repository up to date
- [ ] Credentials configured for both accounts

---

## Testing Phases

**CURRENT STATUS**: Phase 5 - Account Setup In Progress

**LATEST UPDATE**: March 4, 2026 - Cross-account access fixed, StackSet polling working, accounts being configured

**Current State**:
- ✅ Cross-account role deployed with CloudFormation permissions
- ✅ StackSet polling implemented and working
- ✅ 4 accounts created (3 older + 1 new test account)
- ⏳ Setup Orchestrator configuring newest account (863148076418)
- ⏳ VPC deployment completed, IAM roles deploying

**Quick Status Check**:
```bash
# Check account states
aws dynamodb query --table-name AccountPoolFactory-AccountState \
  --index-name StateIndex \
  --key-condition-expression '#state = :state' \
  --expression-attribute-names '{"#state":"state"}' \
  --expression-attribute-values '{":state":{"S":"SETTING_UP"}}' \
  --region us-east-2

# Monitor Setup Orchestrator
aws logs tail /aws/lambda/SetupOrchestrator --since 5m --region us-east-2

# Monitor Pool Manager
aws logs tail /aws/lambda/PoolManager --since 5m --region us-east-2
```

---

## Phase 1: Configuration Update

### Step 1.1: Update config.yaml with New Domain
**Status**: ✅ Complete
**Command**: Manual edit of config.yaml
**Expected**: New domain ID, ARN, root unit ID
**Actual**: 
- Domain ID: dzd-5o0lje5xgpeuw9
- Domain Name: Default_03032026_Domain
- Root Domain Unit ID: 563ikhcj7fgkrt
- Domain Type: IAM-based (IAM_ROLE, IAM_USER)
- Domain Mode: EXPRESS
**Notes**: Successfully retrieved and updated config.yaml with new IAM-based domain details 

---

## Phase 2: Organization Admin Deployment

### Step 2.1: Deploy Approved StackSets
**Status**: ⏳ Pending
**Command**: `./tests/setup/scripts/deploy-approved-stacksets.sh`
**Expected**: 3 StackSets created (VPCSetup, IAMRoles, BlueprintEnablement)
**Actual**:
**Resources Created**:
- [ ] VPCSetup StackSet
- [ ] IAMRoles StackSet
- [ ] BlueprintEnablement StackSet
**Notes**:

---

## Phase 3: Domain Account Deployment

### Step 3.1: Deploy Infrastructure Stack
**Status**: ✅ Complete
**Command**: `./deploy-infrastructure.sh`
**Expected**: Infrastructure stack with all components
**Actual**: Stack deployed successfully
**Resources Created**:
- [x] DynamoDB table: AccountPoolFactory-AccountState
- [x] EventBridge central bus: AccountPoolFactory-CentralBus
- [x] SNS topic: AccountPoolFactory-Alerts
- [x] Pool Manager Lambda: arn:aws:lambda:us-east-2:994753223772:function:PoolManager
- [x] Setup Orchestrator Lambda: arn:aws:lambda:us-east-2:994753223772:function:SetupOrchestrator
- [ ] Account Provider Lambda (not in stack yet - needs separate deployment)
- [x] SSM parameters (13 parameters configured)
- [ ] CloudWatch dashboards (need to verify)
**Notes**: Infrastructure deployed successfully. Lambda functions updated with latest code. All SSM parameters populated with correct domain configuration.

### Step 3.2: Verify Lambda Functions
**Status**: ⏳ Pending
**Command**: `aws lambda list-functions --region us-east-2`
**Expected**: 3 Lambda functions visible
**Actual**:
**Notes**:

### Step 3.3: Verify SSM Parameters
**Status**: ⏳ Pending
**Command**: `aws ssm get-parameters-by-path --path /AccountPoolFactory/ --recursive --region us-east-2`
**Expected**: All configuration parameters present
**Actual**:
**Notes**:

---

## Phase 4: DataZone Integration

### Step 4.1: Create Account Pool in DataZone
**Status**: ✅ Complete
**Command**: `./create-account-pool.sh`
**Expected**: Account pool created with Lambda integration
**Actual**: Account pool created successfully
**Resources Created**:
- [x] Account pool with MANUAL resolution strategy
- [x] Lambda integration configured
- Pool ID: 5id04597iehicp
- Pool Name: AccountPoolFactory
- Lambda ARN: arn:aws:lambda:us-east-2:994753223772:function:AccountProvider
**Notes**: Account pool created with customAccountPoolHandler pointing to AccountProvider Lambda. Details saved to account-pool-details.json

### Step 4.2: Create Project Profile with Account Pool
**Status**: ✅ Complete
**Command**: `./create-open-project-profile-pool.sh` (for IAM domain)
**Expected**: Project profile with account pool enabled
**Actual**: Profile created successfully
**Resources Created**:
- [x] Project profile: Open Project - Account Pool (ID: danattlt8uwzah)
- [x] Environment configurations with account pool (3 blueprints)
- [x] Policy grants for blueprints
- [x] Policy grant for project profile
**Notes**: 
- Created TWO scripts for different domain types:
  - `./create-open-project-profile-pool.sh` - For IAM domains (ToolingLite, S3Bucket, S3TableCatalog)
  - `./create-closed-project-profile-pool.sh` - For IDC domains (Tooling, DataLake, RedshiftServerless, etc.)
- Used open profile for current IAM domain
- Profile uses account pool ID: 5id04597iehicp
- Saved details to open-project-profile-details.json

**Actual Output**:
```
🚀 Creating Open Project Profile with Account Pool (IAM Domain)
==============================================================
Domain ID: dzd-5o0lje5xgpeuw9
Domain Unit ID: 563ikhcj7fgkrt
Domain Account: 994753223772
Region: us-east-2

Account Pool ID: 5id04597iehicp

📋 Fetching blueprint IDs from domain...
Blueprint IDs (IAM Domain):
  ToolingLite: 4iny26qew2b8mh
  S3Bucket: 3ydt1bhkq3sesp
  S3TableCatalog: 4sfeixs7cu9v1l

🔧 Building environment configurations for open projects...
📦 Creating open project profile...

✅ Open project profile created successfully!

Profile ID: danattlt8uwzah
Profile Name: Open Project - Account Pool

📄 Profile details saved to: open-project-profile-details.json

🔐 Adding policy grants...
✅ Policy grant added for ToolingLite
✅ Policy grant added for S3Bucket
✅ Policy grant added for S3TableCatalog
✅ Policy grant added for Project Profile

✅ Open project profile setup complete!

Profile Type: Open (IAM Domain)
Blueprints: ToolingLite (ON_CREATE), S3Bucket, S3TableCatalog (ON_DEMAND)
```

---

## Phase 5: Initial Pool Seeding

### Step 5.1: Trigger Manual Replenishment
**Status**: ✅ Complete - SSM Pagination Fixed
**Command**: `./seed-initial-pool.sh`
**Expected**: Pool Manager creates initial accounts
**Actual**: Successfully created 3 accounts
**Notes**:

**Issues Found and Fixed**:
1. ✅ FIXED: Email domain format in config.yaml had extra `@` symbol
   - Was: `email_domain: aws-test@example.com`
   - Fixed: `email_domain: example.com`
   - Updated SSM parameter: `/AccountPoolFactory/PoolManager/EmailDomain`

2. ✅ FIXED: Pool Manager Lambda cross-account role integration
   - Pool Manager runs in Domain account (994753223772)
   - Account creation must happen in Org Admin account (495869084367)
   - Created cross-account IAM role template: `templates/cloudformation/01-org-admin/account-creation-role.yaml`
   - Created deployment script: `./deploy-org-admin-role.sh`
   - Updated Pool Manager Lambda code to use cross-account role:
     - Added `get_organizations_client()` function to assume role
     - Updated `create_accounts_parallel()` to use cross-account client
     - Updated `wait_for_account_creation()` to accept org_client parameter
     - Updated `move_account_to_target_ou()` to accept org_client parameter
     - Updated `reclaim_account_delete()` to use cross-account client
     - Updated `handle_delete_failed_account()` to use cross-account client
   - Role uses external ID for security: `AccountPoolFactory-{DomainAccountId}`
   - Role uses least-privilege permissions (only necessary Organizations API actions)

3. ✅ FIXED: SSM parameter pagination issue
   - Problem: `load_config()` function only loaded first 10 parameters (SSM default)
   - ExternalId was the 11th parameter and wasn't being loaded
   - Solution: Added pagination loop with `NextToken` handling
   - Result: All 11 parameters now loaded successfully
   - Added detailed logging for cross-account parameters (OrgAdminRoleArn, ExternalId)

**Test Results**:
✅ Pool Manager successfully loaded all 11 SSM parameters with pagination
✅ ExternalId loaded correctly: `AccountPoolFactory-994753223772`
✅ OrgAdminRoleArn loaded correctly: `arn:aws:iam::495869084367:role/SMUS-AccountPoolFactory-AccountCreation`
✅ Cross-account role assumption successful
✅ 3 AWS accounts created successfully:
   - Account 1: 669468173247 (DataZone-Pool-1772588955-0)
   - Account 2: 476383094227 (DataZone-Pool-1772588955-1)
   - Account 3: 071378140110 (DataZone-Pool-1772588955-2)
✅ All accounts moved to target OU: ou-n5om-otvkrtx2
✅ DynamoDB records created with state SETTING_UP
✅ Setup Orchestrator invoked for all accounts

**Known Issues**:
1. ✅ FIXED: Setup Orchestrator AssumeRole permission issue
   - Root cause: OrganizationAccountAccessRole trust policy only trusted Org Admin account
   - Solution: Created StackSet to deploy SMUS-AccountPoolFactory-DomainAccess role
   - StackSet auto-deploys to all accounts in target OU
   - Pool Manager polls for StackSet deployment before invoking Setup Orchestrator
   - Setup Orchestrator now successfully assumes DomainAccess role
   
2. ✅ FIXED: StackSet polling AccessDenied error
   - Root cause: AccountCreation role lacked CloudFormation permissions
   - Solution: Added cloudformation:ListStackInstances and DescribeStackSet permissions
   - Pool Manager can now poll StackSet deployment status
   - Polling works with 10-second intervals, max 5-minute timeout
   
3. ✅ FIXED: Setup Orchestrator "Account does not exist" error
   - Was checking Organizations API instead of DynamoDB
   - Fixed by changing validation to check DynamoDB only
   
4. ✅ FIXED: CloudFormation templates not packaged with Lambda
   - Templates were missing from Lambda deployment package
   - Fixed by updating deploy-infrastructure.sh to include templates
   - All 5 templates now packaged: vpc-setup, iam-roles, eventbridge-rules, blueprint-enablement, blueprint-enablement-with-grants

**Current Test Accounts**:
- 476383094227 (SETTING_UP) - Created March 4, 01:49 UTC
- 071378140110 (SETTING_UP) - Created March 4, 01:49 UTC  
- 863148076418 (SETTING_UP) - Created March 4, 13:48 UTC (newest, actively deploying)

**Latest Test Results** (March 4, 2026 13:50 UTC):
✅ Pool Manager successfully loaded all 11 SSM parameters with pagination
✅ ExternalId loaded correctly: `AccountPoolFactory-994753223772`
✅ OrgAdminRoleArn loaded correctly: `arn:aws:iam::495869084367:role/SMUS-AccountPoolFactory-AccountCreation`
✅ Cross-account role assumption successful
✅ StackSet polling working (no more AccessDenied errors)
✅ StackSet deployment detected (status changed from OUTDATED → CURRENT in 72 seconds)
✅ Setup Orchestrator invoked after StackSet ready
✅ Setup Orchestrator successfully assumed SMUS-AccountPoolFactory-DomainAccess role
✅ VPC deployment started successfully for account 863148076418
⏳ IAM roles and EventBridge rules deploying (Wave 2)
⏳ Waiting for complete setup workflow (6-8 minutes total)

**Next Steps to Complete**:
1. ✅ Deploy updated Lambda code: `./deploy-infrastructure.sh` - COMPLETE
2. ✅ Switch to Org Admin account (495869084367) - COMPLETE
3. ✅ Deploy cross-account role: `./deploy-org-admin-role.sh` - COMPLETE
4. ✅ Switch back to Domain account (994753223772) - COMPLETE
5. ✅ Add SSM parameters with role ARN and external ID - COMPLETE
6. ✅ Test pool seeding: `./seed-initial-pool.sh` - COMPLETE
7. ⏳ Investigate Setup Orchestrator DynamoDB query issue
8. ⏳ Monitor accounts reaching AVAILABLE state

### Step 5.2: Monitor Account Creation
**Status**: ⏳ Pending
**Command**: `aws logs tail /aws/lambda/PoolManager --follow --region us-east-2`
**Expected**: Accounts created via Organizations API
**Actual**:
**Accounts Created**:
- [ ] Account 1: ID, Email, Status
- [ ] Account 2: ID, Email, Status
- [ ] Account 3: ID, Email, Status
- [ ] Account 4: ID, Email, Status
- [ ] Account 5: ID, Email, Status
**Notes**:

### Step 5.3: Monitor Setup Orchestrator
**Status**: ⏳ Pending
**Command**: `aws logs tail /aws/lambda/SetupOrchestrator --follow --region us-east-2`
**Expected**: Accounts configured through 8-step workflow
**Actual**:
**Setup Progress**:
- [ ] Wave 1: VPC deployment
- [ ] Wave 2: IAM roles + EventBridge rules
- [ ] Wave 3: S3 bucket + RAM share
- [ ] Wave 4: Blueprint enablement
- [ ] Wave 5: Policy grants
- [ ] Wave 6: Domain visibility
**Notes**:

### Step 5.4: Verify DynamoDB State
**Status**: ⏳ Pending
**Command**: `aws dynamodb scan --table-name AccountPoolFactory-AccountState --region us-east-2`
**Expected**: 5 accounts in AVAILABLE state
**Actual**:
**Notes**:

---

## Phase 6: Project Creation Testing

### Step 6.1: Create Test Project
**Status**: ⏳ Pending
**Command**: Via DataZone portal or CLI
**Expected**: Project created with account assigned
**Actual**:
**Resources Created**:
- [ ] DataZone project
- [ ] Account assigned from pool
- [ ] CloudFormation stack in project account
**Notes**:

### Step 6.2: Verify Account Assignment
**Status**: ⏳ Pending
**Command**: Check DynamoDB for ASSIGNED state
**Expected**: One account moved to ASSIGNED state
**Actual**:
**Notes**:

### Step 6.3: Verify Replenishment Trigger
**Status**: ⏳ Pending
**Command**: Check Pool Manager logs
**Expected**: Replenishment triggered if below minimum
**Actual**:
**Notes**:

---

## Phase 7: Environment Creation Testing

### Step 7.1: Create Environment Manually
**Status**: ⏳ Pending
**Command**: Via DataZone portal
**Expected**: Environment created in assigned account
**Actual**:
**Notes**:

### Step 7.2: Verify Account Provider Lambda
**Status**: ⏳ Pending
**Command**: Check Account Provider logs
**Expected**: Lambda invoked and returned account
**Actual**:
**Notes**:

---

## Phase 8: Monitoring Validation

### Step 8.1: Check CloudWatch Dashboards
**Status**: ⏳ Pending
**Command**: Navigate to CloudWatch console
**Expected**: 4 dashboards with data
**Actual**:
**Dashboards Verified**:
- [ ] AccountPoolFactory-Overview
- [ ] AccountPoolFactory-Inventory
- [ ] AccountPoolFactory-FailedAccounts
- [ ] AccountPoolFactory-OrgLimits
**Notes**:

### Step 8.2: Verify CloudWatch Metrics
**Status**: ⏳ Pending
**Command**: Check CloudWatch metrics
**Expected**: Metrics published by both Lambdas
**Actual**:
**Notes**:

### Step 8.3: Subscribe to SNS Alerts
**Status**: ⏳ Pending
**Command**: `aws sns subscribe --topic-arn <ARN> --protocol email --notification-endpoint <email> --region us-east-2`
**Expected**: Subscription confirmed
**Actual**:
**Notes**:

---

## Phase 9: Failure Testing

### Step 9.1: Test Failed Account Handling
**Status**: ⏳ Pending
**Command**: Simulate failure scenario
**Expected**: Account marked FAILED, replenishment blocked
**Actual**:
**Notes**:

### Step 9.2: Test Manual Failed Account Deletion
**Status**: ⏳ Pending
**Command**: Delete failed account
**Expected**: Replenishment unblocked
**Actual**:
**Notes**:

---

## Phase 10: Cleanup Testing

### Step 10.1: Delete Test Project
**Status**: ⏳ Pending
**Command**: Via DataZone portal
**Expected**: CloudFormation DELETE_COMPLETE event
**Actual**:
**Notes**:

### Step 10.2: Verify Account Deletion
**Status**: ⏳ Pending
**Command**: Check Pool Manager logs
**Expected**: Account closed via Organizations API
**Actual**:
**Notes**:

### Step 10.3: Verify DynamoDB Cleanup
**Status**: ⏳ Pending
**Command**: Check DynamoDB for deleted account
**Expected**: Account record removed
**Actual**:
**Notes**:

---

## Issues Encountered

### Issue 1: [Title]
**Phase**: 
**Description**: 
**Error Message**: 
**Resolution**: 
**Status**: 

---

## Key Findings

### IAM-based Domain Differences
- 

### Performance Metrics
- Account creation time: 
- Setup orchestrator duration: 
- Total time to AVAILABLE: 

### Configuration Changes Required
- 

---

## Test Results Summary

**Overall Status**: ⏳ In Progress

**Phases Completed**: 0/10
**Phases Failed**: 0/10
**Phases Pending**: 10/10

**Critical Issues**: 0
**Minor Issues**: 0

**Recommendation**: 

---

## Next Steps

1. Update config.yaml with new IAM-based domain details
2. Begin Phase 2: Organization Admin Deployment
3. Continue through all phases systematically
4. Document all issues and resolutions
5. Update implementation if changes needed for IAM-based domains

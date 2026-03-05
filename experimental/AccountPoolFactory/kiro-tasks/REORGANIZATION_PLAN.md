# Account Pool Factory - Reorganization Plan

## Current State Analysis

### Problems:
1. **Root directory clutter**: 30+ scripts and config files in root directory
2. **Inconsistent naming**: Mix of "org-admin", "domain", "project" naming across different locations
3. **Test vs Production unclear**: Test-specific resources mixed with production code
4. **No clear deployment sequence**: Scripts lack numbering or clear ordering
5. **Hardcoded values**: Account IDs and regions in some scripts
6. **No IaC abstraction**: CloudFormation, CDK, Terraform not abstracted

---

## New Directory Structure

```
experimental/AccountPoolFactory/
├── README.md                          # Main entry point
├── .gitignore                         # Updated to exclude config files
├── config.yaml.template               # Template only (actual config.yaml in .gitignore)
│
├── docs/                              # Documentation
│   ├── Architecture.md                # What's deployed in each account (text + diagrams)
│   ├── GettingStarted.md             # Quick start guide
│   ├── UserGuide.md                  # Full user guide
│   └── TestingGuide.md               # Testing instructions
│
├── src/                               # Lambda source code (production)
│   ├── pool-manager/
│   ├── setup-orchestrator/
│   ├── account-creator/
│   └── shared/
│
├── templates/                         # IaC templates (production)
│   ├── cloudformation/               # Default IaC (controlled by config)
│   │   ├── org-admin/                # Org Management Account resources
│   │   │   ├── deploy/
│   │   │   │   ├── 01-stackset-roles.yaml
│   │   │   │   ├── 02-account-creation-role.yaml
│   │   │   │   └── 03-trust-policy-stackset.yaml
│   │   │   └── cleanup/
│   │   │       └── cleanup-org-admin.yaml
│   │   │
│   │   ├── domain-account/           # DataZone Domain Account resources
│   │   │   ├── deploy/
│   │   │   │   ├── 01-infrastructure.yaml
│   │   │   │   ├── 02-lambdas.yaml
│   │   │   │   └── 03-monitoring.yaml
│   │   │   └── cleanup/
│   │   │       └── cleanup-domain-account.yaml
│   │   │
│   │   └── project-account/          # Project Account resources (deployed by StackSet)
│   │       ├── deploy/
│   │       │   ├── 01-stackset-execution-role.yaml
│   │       │   ├── 02-vpc-setup.yaml
│   │       │   ├── 03-iam-roles.yaml
│   │       │   ├── 04-eventbridge-rules.yaml
│   │       │   └── 05-blueprint-enablement.yaml
│   │       └── cleanup/
│   │           └── cleanup-project-account.yaml
│   │
│   ├── cdk/                          # CDK templates (future)
│   └── terraform/                    # Terraform templates (future)
│
├── scripts/                          # Deployment and utility scripts (production)
│   ├── deploy/
│   │   ├── org-admin/
│   │   │   ├── 01-deploy-stackset-roles.sh
│   │   │   ├── 02-deploy-account-creation-role.sh
│   │   │   └── 03-deploy-trust-policy-stackset.sh
│   │   │
│   │   ├── domain-account/
│   │   │   ├── 01-deploy-infrastructure.sh
│   │   │   ├── 02-deploy-lambdas.sh
│   │   │   └── 03-deploy-monitoring.sh
│   │   │
│   │   └── project-account/
│   │       └── README.md             # Deployed via StackSet, not manually
│   │
│   ├── cleanup/
│   │   ├── org-admin/
│   │   │   └── cleanup-org-admin.sh
│   │   ├── domain-account/
│   │   │   └── cleanup-domain-account.sh
│   │   └── project-account/
│   │       └── cleanup-project-account.sh
│   │
│   └── utils/
│       ├── validate-config.sh        # Validate config.yaml
│       ├── switch-account.sh         # Helper to switch AWS accounts
│       ├── get-account-info.sh       # Get account details
│       └── check-prerequisites.sh    # Check AWS CLI, permissions, etc.
│
├── tests/                            # Test-specific resources
│   ├── config/
│   │   └── test-config.yaml.template # Test-specific configuration
│   │
│   ├── setup/                        # Test environment setup
│   │   ├── 01-create-test-domain.sh
│   │   ├── 02-create-test-ou.sh
│   │   └── 03-seed-test-accounts.sh
│   │
│   ├── cleanup/                      # Test environment cleanup
│   │   ├── cleanup-test-accounts.sh
│   │   └── cleanup-test-domain.sh
│   │
│   └── integration/                  # Integration tests
│       ├── test-account-creation.sh
│       ├── test-setup-workflow.sh
│       └── test-ram-share.sh
│
└── examples/                         # Example configurations
    ├── config-new-accounts.yaml      # For testing new accounts (1a)
    └── config-existing-accounts.yaml # For existing accounts (1b)
```

---

## Reorganization Tasks

### Phase 1: Create New Structure (No Breaking Changes)

#### Task 1.1: Create Directory Structure
- [ ] Create `scripts/deploy/org-admin/`
- [ ] Create `scripts/deploy/domain-account/`
- [ ] Create `scripts/deploy/project-account/`
- [ ] Create `scripts/cleanup/org-admin/`
- [ ] Create `scripts/cleanup/domain-account/`
- [ ] Create `scripts/cleanup/project-account/`
- [ ] Create `scripts/utils/`
- [ ] Create `tests/config/`
- [ ] Create `tests/setup/`
- [ ] Create `tests/cleanup/`
- [ ] Create `tests/integration/`
- [ ] Create `examples/`

#### Task 1.2: Reorganize CloudFormation Templates
- [ ] Rename `templates/cloudformation/01-org-admin/` → `templates/cloudformation/org-admin/deploy/`
- [ ] Rename `templates/cloudformation/02-domain-account/` → `templates/cloudformation/domain-account/deploy/`
- [ ] Rename `templates/cloudformation/03-project-account/` → `templates/cloudformation/project-account/deploy/`
- [ ] Add numbered prefixes to templates (01-, 02-, 03-) for deployment order
- [ ] Create cleanup templates in each account folder

#### Task 1.3: Move and Rename Scripts

**Org Admin Scripts:**
- [ ] Move `deploy-org-admin-role.sh` → `scripts/deploy/org-admin/02-deploy-account-creation-role.sh`
- [ ] Move `deploy-trust-policy-stackset.sh` → `scripts/deploy/org-admin/03-deploy-trust-policy-stackset.sh`
- [ ] Create `scripts/deploy/org-admin/01-deploy-stackset-roles.sh` (new)

**Domain Account Scripts:**
- [ ] Move `deploy-infrastructure.sh` → `scripts/deploy/domain-account/01-deploy-infrastructure.sh`
- [ ] Move `deploy-account-provider.sh` → `scripts/deploy/domain-account/02-deploy-lambdas.sh`
- [ ] Create `scripts/deploy/domain-account/03-deploy-monitoring.sh` (new)

**Cleanup Scripts:**
- [ ] Move `cleanup-infrastructure.sh` → `scripts/cleanup/domain-account/cleanup-domain-account.sh`
- [ ] Move `cleanup-all.sh` → `scripts/cleanup/cleanup-all.sh` (orchestrator)
- [ ] Move `cleanup-all-accounts.sh` → `tests/cleanup/cleanup-test-accounts.sh`
- [ ] Move `cleanup-failed-accounts.sh` → `scripts/utils/cleanup-failed-accounts.sh`
- [ ] Move `cleanup-retain-accounts.sh` → `scripts/utils/cleanup-retain-accounts.sh`

**Test Scripts:**
- [ ] Move `seed-initial-pool.sh` → `tests/setup/03-seed-test-accounts.sh`
- [ ] Move `run-full-test.sh` → `tests/integration/test-full-workflow.sh`
- [ ] Move `test-ram-share.sh` → `tests/integration/test-ram-share.sh`
- [ ] Move `fix-trust-policy-and-test.sh` → `tests/integration/test-trust-policy.sh`

**Utility Scripts:**
- [ ] Move `get-domain-info.sh` → `scripts/utils/get-domain-info.sh`
- [ ] Move `add-domain-execution-role.sh` → `scripts/utils/add-domain-execution-role.sh`
- [ ] Create `scripts/utils/validate-config.sh` (new)
- [ ] Create `scripts/utils/switch-account.sh` (new)
- [ ] Create `scripts/utils/check-prerequisites.sh` (new)

**Project Profile Scripts (move to tests):**
- [ ] Move `create-account-pool.sh` → `tests/setup/04-create-account-pool.sh`
- [ ] Move `create-open-project-profile-pool.sh` → `tests/setup/05-create-open-profile.sh`
- [ ] Move `create-closed-project-profile-pool.sh` → `tests/setup/06-create-closed-profile.sh`

#### Task 1.4: Update Configuration Management
- [ ] Update `.gitignore` to exclude `config.yaml`, `*-outputs.json`, `*.log`
- [ ] Keep `config.yaml.template` with placeholder values
- [ ] Create `examples/config-new-accounts.yaml` (for testing - 1a)
- [ ] Create `examples/config-existing-accounts.yaml` (for production - 1b)
- [ ] Create `tests/config/test-config.yaml.template`

#### Task 1.5: Remove Hardcoded Values
- [ ] Audit all scripts for hardcoded account IDs
- [ ] Audit all scripts for hardcoded regions
- [ ] Replace with config.yaml references
- [ ] Add validation in scripts to check config.yaml exists

#### Task 1.6: Add IaC Abstraction Layer
- [ ] Add `iac_provider` field to config.yaml (cloudformation|cdk|terraform)
- [ ] Create wrapper scripts that call appropriate IaC tool
- [ ] Update all deploy scripts to use wrapper

---

### Phase 2: Update Documentation

#### Task 2.1: Update Architecture Documentation
- [ ] Update `docs/Architecture.md` with clear account breakdown:
  - **Org Admin Account**: StackSet roles, Account creation role, Trust policy StackSet
  - **Domain Account**: DynamoDB, SNS, EventBridge, PoolManager Lambda, SetupOrchestrator Lambda
  - **Project Accounts**: VPC, IAM roles, EventBridge rules, S3 bucket, Blueprint configs
- [ ] Add architecture diagrams (text-based or image)
- [ ] Document cross-account IAM roles and trust relationships
- [ ] Document StackSet deployment flow

#### Task 2.2: Update User Guides
- [ ] Update `docs/GettingStarted.md` with new script paths
- [ ] Update `docs/UserGuide.md` with deployment sequence
- [ ] Update `docs/TestingGuide.md` with new test paths
- [ ] Create `scripts/deploy/README.md` with deployment order
- [ ] Create `scripts/cleanup/README.md` with cleanup order

#### Task 2.3: Update Root README
- [ ] Update main README.md with new structure
- [ ] Add quick start section
- [ ] Add links to detailed docs
- [ ] Add prerequisites section

---

### Phase 3: Testing and Validation

#### Task 3.1: Test New Structure
- [ ] Test org-admin deployment scripts
- [ ] Test domain-account deployment scripts
- [ ] Test project-account StackSet deployment
- [ ] Test cleanup scripts
- [ ] Test utility scripts

#### Task 3.2: Integration Testing
- [ ] Run full workflow test with new structure
- [ ] Verify all cross-account operations work
- [ ] Verify StackSet deployments work
- [ ] Verify cleanup works correctly

---

### Phase 4: Cleanup Old Files

#### Task 4.1: Remove Old Files
- [ ] Delete old scripts from root (after verifying new ones work)
- [ ] Delete old JSON output files from root
- [ ] Delete old log files from root
- [ ] Delete old markdown files from root (move to docs if needed)

#### Task 4.2: Final Validation
- [ ] Verify no broken references
- [ ] Verify all documentation is updated
- [ ] Verify .gitignore is complete
- [ ] Run full integration test

---

## Migration Guide for Users

### For Testing New Accounts (Audience 1a):
1. Copy `examples/config-new-accounts.yaml` to `config.yaml`
2. Update with your test account IDs
3. Run `tests/setup/01-create-test-domain.sh`
4. Run `tests/setup/02-create-test-ou.sh`
5. Run deployment scripts in order

### For Existing Accounts (Audience 1b):
1. Copy `examples/config-existing-accounts.yaml` to `config.yaml`
2. Update with your production account IDs and domain info
3. Run deployment scripts in order

---

## Configuration Changes

### New config.yaml Structure:
```yaml
# IaC Provider Selection
iac:
  provider: cloudformation  # cloudformation | cdk | terraform

# AWS Configuration
aws:
  region: us-east-2
  org_admin_account_id: "PLACEHOLDER"
  domain_account_id: "PLACEHOLDER"

# DataZone Domain Configuration
datazone:
  domain_id: PLACEHOLDER
  domain_name: PLACEHOLDER
  root_domain_unit_id: PLACEHOLDER
  domain_execution_role_arn: PLACEHOLDER

# Account Pool Configuration
account_pool:
  name: AccountPoolFactory
  minimum_pool_size: 3
  target_pool_size: 10

# Testing Configuration (only for audience 1a)
testing:
  enabled: true
  test_ou_name: TestAccounts
  test_domain_name: TestDomain
```

---

## Success Criteria

- [ ] No scripts or config files in root directory (except README, .gitignore, config.yaml.template)
- [ ] Clear separation between test and production resources
- [ ] Consistent naming across all folders (org-admin, domain-account, project-account)
- [ ] Numbered deployment scripts showing clear sequence
- [ ] No hardcoded account IDs or regions
- [ ] IaC provider abstraction in place
- [ ] Updated architecture documentation with diagrams
- [ ] All tests passing with new structure


---

## Phase 0: Current State Analysis & Remediation

### Current Account Setup

**Org Admin Account (495869084367)**:
- Purpose: Organization management, account creation, StackSet administration
- Email: amirbo+1@amazon.com
- Access: `eval $(isengardcli credentials amirbo+1@amazon.com)`

**Domain Account (994753223772)**:
- Purpose: DataZone domain, Lambda functions, DynamoDB, EventBridge
- Email: amirbo+3@amazon.com
- Access: `eval $(isengardcli credentials amirbo+3@amazon.com)`
- DataZone Domain: dzd-5o0lje5xgpeuw9 (IAM-based, EXPRESS mode)

**Project Accounts (Pool Accounts)**:
- Target OU: ou-n5om-otvkrtx2 (RetailBanking/CustomerAnalytics)
- Current accounts: 476383094227, 071378140110, 863148076418
- State: SETTING_UP (testing in progress)

### Current Resource Deployment

#### Org Admin Account (495869084367)

**Deployed Resources**:
- ✅ CloudFormation Stack: `AccountPoolFactory-AccountCreationRole`
  - Template: `templates/cloudformation/01-org-admin/account-creation-role.yaml`
  - Role: `AccountPoolFactory-AccountCreation`
  - Trust: Domain Account Pool Manager
  - ExternalId: `AccountPoolFactory-994753223772`

- ✅ CloudFormation Stack: `AccountPoolFactory-StackSetRoles`
  - Template: `templates/cloudformation/01-org-admin/stackset-roles.yaml`
  - Role: `AWSCloudFormationStackSetAdministrationRole`
  - **MISSING**: `AccountPoolFactory-StackSetManagement` role (needs to be added)

- ✅ CloudFormation StackSet: `AccountPoolFactory-TrustPolicy`
  - Template: `templates/cloudformation/01-org-admin/trust-policy-update.yaml`
  - Deploys: `AccountPoolFactory-DomainAccess` role to project accounts
  - Status: ACTIVE, deployed to 3 accounts

**Issues to Fix**:
1. ❌ Infrastructure stack deployed in WRONG account (should only be in Domain account)
2. ❌ Missing `AccountPoolFactory-StackSetManagement` role for SetupOrchestrator
3. ❌ StackSet roles template needs DomainAccountId parameter

#### Domain Account (994753223772)

**Deployed Resources**:
- ✅ CloudFormation Stack: `AccountPoolFactory-Infrastructure`
  - Template: `templates/cloudformation/02-domain-account/infrastructure.yaml`
  - Resources: DynamoDB, SNS, EventBridge, Lambda roles, SSM parameters
  - Lambda Functions: PoolManager, SetupOrchestrator, AccountProvider

**Issues to Fix**:
1. ❌ SetupOrchestrator Lambda missing `ORG_ADMIN_ACCOUNT_ID` environment variable
2. ❌ SetupOrchestrator IAM role missing permission to assume StackSet management role
3. ❌ Lambda code needs update for StackSet instance deployment

#### Project Accounts (Pool Accounts)

**Deployed Resources** (via StackSet):
- ✅ CloudFormation Stack: `AccountPoolFactory-StackSetExecutionRole`
  - Role: `AWSCloudFormationStackSetExecutionRole`
  - Trust: Org Admin StackSet Administration Role

- ✅ CloudFormation Stack: `AccountPoolFactory-TrustPolicy`
  - Role: `AccountPoolFactory-DomainAccess`
  - Trust: Domain Account SetupOrchestrator
  - ExternalId: Domain ID (dzd-5o0lje5xgpeuw9)

**In Progress** (being deployed by SetupOrchestrator):
- ⏳ VPC stack (Wave 1) - COMPLETED
- ⏳ IAM roles stack (Wave 2) - IN PROGRESS
- ⏳ EventBridge rules stack (Wave 2) - IN PROGRESS
- ⏳ S3 bucket (Wave 3) - PENDING
- ⏳ RAM share (Wave 3) - PENDING
- ⏳ Blueprint enablement (Wave 4) - PENDING

### Remediation Actions

#### Action 0.1: Fix Org Admin Account Resources

**Task**: Update StackSet roles to include StackSet management role

- [ ] Update `templates/cloudformation/01-org-admin/stackset-roles.yaml`:
  - Add `DomainAccountId` parameter
  - Add `AccountPoolFactory-StackSetManagement` role
  - Add trust policy for SetupOrchestrator
  - Add permissions for StackSet instance operations
  - Add ExternalId condition

- [ ] Redeploy stack in Org Admin account:
  ```bash
  eval $(isengardcli credentials amirbo+1@amazon.com)
  aws cloudformation deploy \
    --template-file templates/cloudformation/org-admin/deploy/01-stackset-roles.yaml \
    --stack-name AccountPoolFactory-StackSetRoles \
    --parameter-overrides DomainAccountId=994753223772 \
    --capabilities CAPABILITY_NAMED_IAM \
    --region us-east-2
  ```

- [ ] Verify role created:
  ```bash
  aws iam get-role --role-name AccountPoolFactory-StackSetManagement
  ```

**Status**: ✅ COMPLETED (changes made to template)

#### Action 0.2: Fix Domain Account Resources

**Task**: Update infrastructure stack with StackSet management support

- [ ] Update `templates/cloudformation/02-domain-account/infrastructure.yaml`:
  - Add `OrgAdminAccountId` parameter (already exists)
  - Add `ORG_ADMIN_ACCOUNT_ID` to SetupOrchestrator environment variables
  - Add permission to assume `AccountPoolFactory-StackSetManagement` role

- [ ] Update SetupOrchestrator Lambda code:
  - Modify `deploy_stackset_instance()` to assume StackSet management role
  - Add ExternalId for cross-account access
  - Use assumed role credentials for CloudFormation client

- [ ] Redeploy infrastructure stack:
  ```bash
  eval $(isengardcli credentials amirbo+3@amazon.com)
  cd scripts/deploy/domain-account
  ./01-deploy-infrastructure.sh
  ```

- [ ] Redeploy Lambda code:
  ```bash
  cd scripts/deploy/domain-account
  ./02-deploy-lambdas.sh
  ```

**Status**: ✅ COMPLETED (changes made to templates and code)

#### Action 0.3: Verify Cross-Account Access

**Task**: Test that SetupOrchestrator can assume StackSet management role

- [ ] Check SetupOrchestrator can assume role:
  ```bash
  # From Domain account
  aws sts assume-role \
    --role-arn arn:aws:iam::495869084367:role/AccountPoolFactory-StackSetManagement \
    --role-session-name test \
    --external-id AccountPoolFactory-994753223772
  ```

- [ ] Test StackSet instance creation:
  ```bash
  # Seed one test account
  cd tests/setup
  ./03-seed-test-accounts.sh
  ```

- [ ] Monitor CloudWatch Logs for SetupOrchestrator:
  ```bash
  aws logs tail /aws/lambda/SetupOrchestrator --follow --region us-east-2
  ```

**Status**: ⏳ PENDING (waiting for deployment)

#### Action 0.4: Clean Up Duplicate Infrastructure Stack

**Task**: Remove infrastructure stack from Org Admin account (if it exists)

- [ ] Check if stack exists in Org Admin account:
  ```bash
  eval $(isengardcli credentials amirbo+1@amazon.com)
  aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-Infrastructure \
    --region us-east-2 2>/dev/null || echo "Stack not found (good)"
  ```

- [ ] If stack exists, delete it:
  ```bash
  aws cloudformation delete-stack \
    --stack-name AccountPoolFactory-Infrastructure \
    --region us-east-2
  ```

- [ ] Wait for deletion:
  ```bash
  aws cloudformation wait stack-delete-complete \
    --stack-name AccountPoolFactory-Infrastructure \
    --region us-east-2
  ```

**Status**: ⏳ PENDING (needs verification)

#### Action 0.5: Document Current State

**Task**: Update architecture documentation with current deployment

- [ ] Update `docs/Architecture.md`:
  - Add clear section for each account
  - List all CloudFormation stacks per account
  - Document all IAM roles and trust relationships
  - Add sequence diagrams for cross-account flows
  - Document StackSet deployment process

- [ ] Create deployment state document:
  - List all deployed stacks with status
  - List all IAM roles with ARNs
  - List all Lambda functions with versions
  - Document SSM parameters

- [ ] Create troubleshooting guide:
  - Common issues and solutions
  - How to check cross-account access
  - How to verify StackSet deployment
  - How to monitor Lambda execution

**Status**: ⏳ PENDING

### Deployment Sequence (Current State)

#### Org Admin Account Deployment:
1. ✅ Deploy StackSet roles: `deploy-org-admin-role.sh` → `AccountPoolFactory-StackSetRoles`
2. ✅ Deploy account creation role: `deploy-org-admin-role.sh` → `AccountPoolFactory-AccountCreationRole`
3. ✅ Deploy trust policy StackSet: `deploy-trust-policy-stackset.sh` → `AccountPoolFactory-TrustPolicy`

#### Domain Account Deployment:
1. ✅ Deploy infrastructure: `deploy-infrastructure.sh` → `AccountPoolFactory-Infrastructure`
2. ✅ Deploy Lambda functions: `deploy-account-provider.sh` → Updates Lambda code

#### Project Account Deployment:
1. ✅ Automatic via StackSet: `AccountPoolFactory-TrustPolicy` → `AccountPoolFactory-DomainAccess` role
2. ⏳ Automatic via SetupOrchestrator: VPC, IAM, EventBridge, S3, Blueprints

### Testing Accounts Status

| Account ID | State | Created | Last Updated | Current Step |
|------------|-------|---------|--------------|--------------|
| 476383094227 | SETTING_UP | Mar 4, 01:49 | Mar 4, 01:52 | Wave 1 complete |
| 071378140110 | SETTING_UP | Mar 4, 01:49 | Mar 4, 01:52 | Wave 1 complete |
| 863148076418 | SETTING_UP | Mar 4, 13:48 | Mar 4, 13:52 | Wave 2 in progress |

**Next Steps for Testing**:
1. Wait for current accounts to complete setup (Wave 2-6)
2. Verify accounts reach AVAILABLE state
3. Deploy fixes from Actions 0.1 and 0.2
4. Seed one new clean account to test StackSet management role
5. Monitor end-to-end workflow

### Critical Issues Blocking Progress

1. **StackSet Instance Deployment** (HIGH PRIORITY)
   - Issue: SetupOrchestrator cannot create StackSet instances
   - Root Cause: Missing StackSet management role in Org Admin account
   - Impact: New accounts fail at Wave 0 (StackSet deployment)
   - Fix: Actions 0.1 and 0.2
   - Status: ✅ Code changes complete, needs deployment

2. **RAM Share Authorization** (MEDIUM PRIORITY)
   - Issue: RAM share creation failing with authorization error
   - Root Cause: Wrong RAM permission or domain execution role issue
   - Impact: Accounts fail at Wave 3 (RAM share creation)
   - Fix: Already implemented in Lambda code (using correct permission)
   - Status: ⏳ Needs testing with clean account

3. **Blueprint Enablement** (MEDIUM PRIORITY)
   - Issue: Blueprint enablement may fail due to RAM share issue
   - Root Cause: Domain not accessible from project account
   - Impact: Accounts fail at Wave 4 (blueprint enablement)
   - Fix: Depends on RAM share fix
   - Status: ⏳ Needs testing

### Success Criteria for Phase 0

- [ ] All CloudFormation stacks deployed in correct accounts
- [ ] No duplicate infrastructure stacks
- [ ] StackSet management role exists and is assumable
- [ ] SetupOrchestrator can create StackSet instances
- [ ] One clean account completes full setup workflow (Wave 0-6)
- [ ] Account reaches AVAILABLE state in DynamoDB
- [ ] Architecture documentation updated with current state
- [ ] All IAM roles and trust relationships documented

### Estimated Time for Phase 0

- Action 0.1: 10 minutes (deploy StackSet roles)
- Action 0.2: 15 minutes (deploy infrastructure + Lambda)
- Action 0.3: 20 minutes (test and verify)
- Action 0.4: 5 minutes (cleanup duplicate stack)
- Action 0.5: 30 minutes (documentation)

**Total**: ~1.5 hours

### Dependencies

- Phase 0 must complete before Phase 1 (reorganization)
- Current testing accounts can continue running
- New test accounts should wait for Phase 0 completion
- Documentation updates can happen in parallel


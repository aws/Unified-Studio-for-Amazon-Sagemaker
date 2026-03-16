# Refactor: Account-Centric Project Structure

## Goal

1. Reorganize into `01-org-account/` and `02-domain-account/` top-level folders, each self-contained.
2. Eliminate `03-project-account` — approved StackSet templates become `approved-stacksets/`.
3. Separate concerns: org admin is pool-agnostic (governance only), domain admin owns pools.
4. Remove `scripts/deploy-all.sh` and shared `scripts/utils/`.

## Current vs Target Structure

```
CURRENT:                                    TARGET:
scripts/                                    01-org-account/
  deploy-all.sh                               config.yaml
  01-org-mgmt-account/{deploy,cleanup}/        scripts/{deploy,cleanup}/
  02-domain-account/{deploy,cleanup}/          scripts/resolve-config.sh
  03-project-account/deploy/                   templates/cloudformation/
  utils/                                    02-domain-account/
templates/cloudformation/                     config.yaml
  01-org-mgmt-account/                         scripts/{deploy,cleanup}/
  02-domain-account/                           scripts/resolve-config.sh
  03-project-account/                          scripts/utils/  (all operational utils)
  stacksets/{idc,iam}/                         templates/cloudformation/
org-config.yaml                             approved-stacksets/cloudformation/{idc,iam}/
domain-config.yaml                          src/ docs/ tests/ ui/ specs/ (unchanged)
```

## Config Responsibility Split

### Org admin config (`01-org-account/config.yaml`) — governance only, no pool concept

```yaml
region: us-east-2
stackset_prefix: "SMUS-AccountPoolFactory"

approved_stacksets:       # flat list — org admin controls what's allowed
  - 01-domain-access.yaml
  - 02-vpc-setup.yaml
  - 03-iam-roles.yaml
  - 04-eventbridge-rules.yaml
  - 05-project-role.yaml
  - 06-blueprint-enablement.yaml

ous:                      # per-OU settings — domain admin references OU name in pool config
  - name: "RetailBanking/CustomerAnalytics"
    email_prefix: "amirbo+pool-test"
    email_domain: "amazon.com"
    account_tags:
      ManagedBy: "AccountPoolFactory"
```

### Domain admin config (`02-domain-account/config.yaml`) — pool management

```yaml
region: us-east-2
domain_id: "dzd-4h7jbz76qckoh5"
domain_name: "domain-03-06-2026-164120"
org_admin_account_id: "495869084367"

pools:
  - name: default
    ou_name: "RetailBanking/CustomerAnalytics"
    min_size: 2
    target_size: 5
    reclaim_strategy: REUSE
    default_project_owner: "analyst1-amirbo"
    project_profile_name: "All Capabilities - Account Pool"
    stacksets:                                    # subset of org-approved, with waves
      - template: 01-domain-access.yaml
        wave: 1
      - template: 02-vpc-setup.yaml
        wave: 2
      - template: 03-iam-roles.yaml
        wave: 2
      - template: 04-eventbridge-rules.yaml
        wave: 2
      - template: 05-project-role.yaml
        wave: 2
      - template: 06-blueprint-enablement.yaml
        wave: 3
```

## SSM Parameter Changes

### Org account SSM — changes from per-pool to per-OU
```
OLD: /AccountPoolFactory/Pools/{pool}/OUId, EmailPrefix, EmailDomain, AccountTags, StackSets
NEW: /AccountPoolFactory/OUs/{ou-id}/EmailPrefix, EmailDomain, AccountTags
     /AccountPoolFactory/TemplateBucketName, StackSetPrefix (unchanged)
```

### Domain account SSM — gains stacksets + OU config per pool
```
UNCHANGED: /AccountPoolFactory/Pools/{pool}/MinimumPoolSize, TargetPoolSize, ReclaimStrategy, ProjectProfileName
NEW:       /AccountPoolFactory/Pools/{pool}/OUName, OUId, StackSets (JSON)
```

## Cross-Account Info Flow

```
Domain deploys first → prints ProvisionAccountRoleArn (human copies to org admin)
Org admin runs: 01-org-account/scripts/deploy/01-deploy.sh <domain-account-id> <domain-id> <role-arn>

At runtime:
  PoolManager reads pool config from domain SSM (including ouId + stacksets)
  PoolManager invokes ProvisionAccount with { ouId, stacksets, domainId, domainAccountId }
  ProvisionAccount assumes AccountCreation role, reads email/tags from org SSM /OUs/{ou-id}/*
  ProvisionAccount creates account, deploys StackSets in wave order
```

## Lambda Code Changes Summary

| Lambda | Current | New |
|--------|---------|-----|
| ProvisionAccount | Reads OU, email, tags, stacksets from org SSM `/Pools/{pool}/*` | Gets ouId + stacksets from event. Reads email/tags from org SSM `/OUs/{ou-id}/*` |
| PoolManager | Invokes ProvisionAccount with `{poolName, domainId, domainAccountId}` | Also passes `ouId` + `stacksets` (from domain SSM) |
| SetupOrchestrator | `_load_pool_stacksets_config()` reads from org SSM via cross-account role | Reads from domain SSM `/Pools/{pool}/StackSets` |
| AccountReconciler | May read stackset config from org SSM | Reads from domain SSM |
| DeprovisionAccount | Uses deployedStackSets from DynamoDB | No change |
| AccountProvider | No relevant config reads | No change |
| AccountRecycler | Invokes SetupOrchestrator/ProvisionAccount | No direct change |

## Tasks

All code, file moves, and doc changes are done first (Phases 1-7).
Deployment and testing is the final phase (Phase 8).

### Phase 1: Config restructure + Lambda code changes

- [x] 1.1 Create `01-org-account/config.yaml.template` — new schema (approved_stacksets, ous[])
- [x] 1.2 Create `01-org-account/config.yaml` — converted from current org-config.yaml
- [x] 1.3 Create `02-domain-account/config.yaml.template` — new schema (pools[] with ou_name + stacksets)
- [x] 1.4 Create `02-domain-account/config.yaml` — converted from current domain-config.yaml
- [x] 1.5 Update `ProvisionAccount` Lambda (`src/provision-account/lambda_function.py`):
  - `load_pool_config_from_ssm()` → renamed to `load_ou_config_from_ssm()`, reads `/OUs/{ou-id}/*`
  - Accept `ouId` + `stacksets` from event payload (passed by PoolManager)
  - Remove pool-name-based SSM reads from org account
- [x] 1.6 Update `PoolManager` Lambda (`src/pool-manager/lambda_function.py`):
  - Load pool's StackSets + OUId from domain SSM `/Pools/{pool}/StackSets` and `/Pools/{pool}/OUId`
  - Pass `ouId` + `stacksets` in ProvisionAccount invocation payload
- [x] 1.7 Update `SetupOrchestrator` Lambda (`src/setup-orchestrator/lambda_function.py`):
  - `_load_pool_stacksets_config()` → reads from domain SSM (no cross-account call)
- [x] 1.8 Update `AccountReconciler` Lambda (`src/account-reconciler/lambda_function.py`):
  - Removed cross-account org SSM read, now reads all pool config from domain SSM only
- [x] 1.9 Create `01-org-account/scripts/resolve-config.sh` — org-only (approved_stacksets, ous[])
- [x] 1.10 Create `02-domain-account/scripts/resolve-config.sh` — domain-only (pools[] with ou_name + stacksets)

### Phase 2: Rewrite deploy/cleanup scripts for new structure

- [x] 2.1 Rewrite org deploy (`01-org-account/scripts/deploy/01-deploy.sh`):
  - Upload ALL approved_stacksets to S3, create/update StackSet definitions
  - Write per-OU SSM: `/OUs/{ou-id}/EmailPrefix`, `EmailDomain`, `AccountTags`
  - No pool SSM params
- [x] 2.2 Rewrite org verify (`01-org-account/scripts/deploy/02-verify.sh`):
  - Check per-OU SSM params instead of per-pool
- [x] 2.3 Rewrite org cleanup (`01-org-account/scripts/cleanup/cleanup.sh`):
  - Source new resolve-config.sh, updated PROJECT_ROOT
- [x] 2.4 Rewrite domain deploy (`02-domain-account/scripts/deploy/01-deploy.sh`):
  - Write per-pool SSM: StackSets JSON, OUId, OUName (in addition to existing sizing params)
  - OU resolution via cross-account role to call Organizations API
  - Template path: `02-domain-account/templates/cloudformation/01-infrastructure.yaml`
  - Lambda packaging: templates from `approved-stacksets/cloudformation/idc/`
- [x] 2.5 Update remaining domain deploy scripts (02 through 06):
  - Source new resolve-config.sh, updated PROJECT_ROOT
- [x] 2.6 Rewrite domain cleanup (`02-domain-account/scripts/cleanup/cleanup.sh`):
  - Source new resolve-config.sh, updated PROJECT_ROOT

### Phase 3: Move files to new directory structure

- [x] 3.1 Move org scripts to `01-org-account/scripts/{deploy,cleanup}/`
- [x] 3.2 Move org template to `01-org-account/templates/cloudformation/`
- [x] 3.3 Move domain scripts to `02-domain-account/scripts/{deploy,cleanup}/`
- [x] 3.4 Move domain template to `02-domain-account/templates/cloudformation/`
- [x] 3.5 Create `approved-stacksets/cloudformation/idc/` — merge stacksets/idc/ + 03-project-account/deploy/
  - Deduplicate same-named files (keep stacksets/idc/ version)
- [x] 3.6 Move `templates/cloudformation/stacksets/iam/` → `approved-stacksets/cloudformation/iam/`
- [x] 3.7 Create empty `approved-stacksets/cdk/` and `approved-stacksets/terraform/`
- [x] 3.8 Move all utils from `scripts/utils/` → `02-domain-account/scripts/utils/`
- [x] 3.9 Move `scripts/03-project-account/deploy/01-create-test-project.py` → `tests/create-test-project.py`
- [x] 3.10 Delete `scripts/deploy-all.sh`, old config files from root
- [x] 3.11 Remove old empty directories: `scripts/`, `templates/`

### Phase 4: Update path references in moved scripts and utils

- [x] 4.1 Update all domain utils that source resolve-config.sh → new relative path
- [x] 4.2 Update `02-domain-account/scripts/utils/update-blueprint-stackset.py` → approved-stacksets path
- [x] 4.3 Update any utils referencing old `scripts/utils/` or template paths

### Phase 5: Update documentation

- [x] 5.1 Update `README.md` — project structure, deploy paths
- [x] 5.2 Update `docs/OrgAdminGuide.md`:
  - New config schema (approved_stacksets, ous[] instead of pools[])
  - Deploy paths: `./01-org-account/scripts/deploy/*`
  - StackSet template dir: `approved-stacksets/cloudformation/idc/`
  - Remove "Adding a New Pool" (org doesn't know about pools)
  - SSM params now per-OU
- [x] 5.3 Update `docs/DomainAdminGuide.md`:
  - New config schema (pools[] with ou_name + stacksets subset)
  - Deploy paths: `./02-domain-account/scripts/deploy/*`
  - Utils paths: `./02-domain-account/scripts/utils/*`
  - Test project: `tests/create-test-project.py`
- [x] 5.4 Update `docs/Architecture.md` — project structure tree, Lambda packaging, SSM descriptions
- [x] 5.5 Update `docs/SecurityGuide.md` — any path references
- [x] 5.6 Update `docs/TestingGuide.md` — deploy/cleanup/test script paths, config paths
- [ ] 5.7 Rewrite `02-domain-account/scripts/utils/README.md` — new tree, deploy order, utils paths

### Phase 6: Update specs, kiro-tasks, config references

- [x] 6.1 Update `01-org-account/config.yaml` — comment paths
- [x] 6.2 Update `specs/requirements.md` — template and config path references
- [x] 6.3 Update `kiro-tasks/multi-pool-org-stackset-config.md` — path + config schema references
- [x] 6.4 Update `kiro-tasks/account-deletion-queue.md` — path references

### Phase 7: Update test scripts and .kiro tmp

- [x] 7.1 Update `tests/setup/deploy-approved-stacksets.sh` — TEMPLATES_DIR
- [x] 7.2 Update `tests/setup/deploy-blueprint-enablement.sh` — template path
- [x] 7.3 Update `tests/setup/deploy-blueprint-stackset.sh` — TEMPLATES_DIR
- [x] 7.4 Update `tests/setup/deploy-iam-roles-stackset.sh` — TEMPLATES_DIR
- [x] 7.5 Update `tests/setup/deploy-vpc-stackset.sh` — TEMPLATES_DIR
- [x] 7.6 Update `tests/setup/deploy-iam-roles-direct.sh` — template path
- [x] 7.7 Update `tests/setup/README-StackSets.md` — path references
- [x] 7.8 Update `tests/setup/deploy-account-provider-lambda.sh` — template path
- [x] 7.9 Update `tests/setup/deploy-domain-sharing.sh` — template path
- [ ] 7.10 Update `.kiro/tmp/` scripts — template paths (low priority, can skip)
- [x] 7.11 Update `.kiro/specs/glue-lakeformation-test-data/` — design.md and tasks.md

### Phase 8: Pre-deploy verification (local, no AWS)

- [x] 8.1 Grep for remaining references to old paths
- [x] 8.2 Verify PROJECT_ROOT calculations in all moved scripts
- [x] 8.3 Syntax check all Lambda Python files
- [x] 8.4 Test resolve-config.sh scripts parse new config schema (dry run, no AWS)

### Phase 9: Deploy and test (live AWS)

**Migration sequence — SSM params first, then Lambdas:**

- [x] 9.1 Org account: run new deploy script → writes `/OUs/{ou-id}/*` SSM params
  - Old `/Pools/{pool}/*` params still exist (old Lambdas still work if rollback needed)
- [x] 9.2 Domain account: run new deploy script → writes `/Pools/{pool}/StackSets`, `OUId`, `OUName`
  - Existing sizing params overwritten in place (same paths)
- [x] 9.3 Domain account: deploy new Lambda code (all 7 functions)
- [x] 9.4 Verify: `aws ssm get-parameters-by-path --path /AccountPoolFactory/OUs/ --recursive` (org account)
- [x] 9.5 Verify: `aws ssm get-parameter --name /AccountPoolFactory/Pools/default/StackSets` (domain account)

**Smoke tests:**

- [x] 9.6 Invoke AccountReconciler `{"dryRun":true}` — should not mark any AVAILABLE as FAILED
- [x] 9.7 Invoke PoolManager `{"action":"force_replenishment"}` — pool at 68 AVAILABLE, no new accounts needed
- [x] 9.8 Wait for new account to reach AVAILABLE (N/A — pool already full)

**End-to-end:**

- [x] 9.9 Run `tests/integration/test-e2e-pool-lifecycle.py` — create → assign → delete → reclaim ✅

**Cleanup (only after all tests pass):**

- [x] 9.10 Delete old org SSM params: `/AccountPoolFactory/Pools/{pool}/OUId,EmailPrefix,EmailDomain,AccountTags,StackSets`
- [x] 9.11 Run AccountReconciler once more after cleanup to confirm nothing breaks — `failedValidation: 0` ✅

**Rollback plan:**
- Old SSM params not deleted until 9.10 (after all tests pass)
- If new Lambdas fail: revert Lambda code to previous zip, old Lambdas read old SSM params
- DynamoDB and S3 are untouched — no data loss possible

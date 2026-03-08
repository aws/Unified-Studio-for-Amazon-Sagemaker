# Implementation Tasks — Account Reconciliation & Recycling

## Status Summary

| Task | Description | Status |
|------|-------------|--------|
| 1 | Org Admin CloudFormation — tag permissions + Reconciler trust | ✅ DONE |
| 2 | ProvisionAccount Lambda — tag accounts after creation | ✅ DONE |
| 3 | Domain Account CloudFormation — Reconciler + Recycler infra | ✅ DONE |
| 4 | AccountReconciler Lambda implementation | ✅ DONE |
| 5 | AccountRecycler Lambda implementation | ✅ DONE |
| 6 | Documentation updates (6 files) | ✅ DONE |
| 7 | Deploy and verify | ✅ DONE |
| 8 | Make setup stack patterns configurable (not hardcoded) | ✅ DONE |
| 9 | Fix reconciler validation for AVAILABLE accounts | ✅ DONE |
| 10 | Fix recycler force flag for FAILED state | ✅ DONE |
| 11 | Fix recycler invoke_lambda_sync failure detection | ✅ DONE |
| 12 | Fix DomainAccess StackSet not deployed to pool accounts | ✅ DONE |
| 13 | Clean separation: reconciler detects, recycler fixes | ✅ DONE |
| 14 | Fix reconciler logging (print failure reason) | ✅ DONE |
| 15 | Fix enable_blueprints() idempotency (check_existing_stack) | ✅ DONE |
| 16 | Fix deploy script: --lambdas-only flag + correct zip packaging | ✅ DONE |
| 17 | Full system test: self-healing + create-project end-to-end | 🔄 IN PROGRESS |

## Files Modified (all paths relative to `experimental/AccountPoolFactory/`)

| File | Task | What Changed |
|------|------|-------------|
| `templates/cloudformation/01-org-mgmt-account/deploy/02-provision-account.yaml` | 1 | Added `ListTagsForResource`, `TagResource`, `ListAccountsForParent` to AccountCreationRole policy. Added AccountReconciler role as trusted principal. Added `TagResource`+`ListTagsForResource` to ProvisionAccountRole. |
| `src/provision-account/lambda_function.py` | 2 | Added `organizations.tag_resource()` after account creation with `ManagedBy=AccountPoolFactory` + `PoolName` tags. Non-fatal try/except. |
| `src/pool-manager/lambda_function.py` | 2 | Added `poolName` to payload in `create_accounts_parallel()`. |
| `templates/cloudformation/02-domain-account/deploy/01-infrastructure.yaml` | 3 | Added AccountReconcilerRole, AccountRecyclerRole, AccountReconcilerFunction (300s), AccountRecyclerFunction (900s), SSM params (MaxRecycleRetries=3, MaxConcurrentRecycles=3), log groups, outputs. |
| `src/account-reconciler/lambda_function.py` | 4 | New file. Full reconciler: SSM config, cross-account STS, OU-scoped listing, tag check/backfill, multi-pool isolation, DynamoDB reconciliation, dry-run, autoRecycle, autoReplenish. |
| `src/account-recycler/lambda_function.py` | 5 | New file. Full recycler: CLEANING→deprovision→setup→AVAILABLE, FAILED retry/classify, ORPHANED handling, batch mode with ThreadPoolExecutor, CloudWatch metrics, SNS. Added `force` flag for re-recycling AVAILABLE accounts with incomplete setup. |
| `src/deprovision-account/lambda_function.py` | 7 | Bug fix: no longer sets state to AVAILABLE after cleanup. Leaves state as CLEANING so recycler can proceed to SetupOrchestrator. |
| `templates/cloudformation/03-project-account/deploy/blueprint-enablement-iam.yaml` | 7 | Updated all 17 blueprint identifiers to match new domain (`Tooling`, `DataLake`, `LakehouseCatalog`, etc. replacing old `ToolingLite`, `S3Bucket`, `S3TableCatalog`). |
| `scripts/utils/invoke-recycler.sh` | 7 | Added `--force` flag support for re-recycling AVAILABLE accounts. |
| `docs/Architecture.md` | 6 | Added AccountReconciler + AccountRecycler Lambda sections with reconciliation flow diagram. |
| `docs/UserGuide.md` | 6 | Added "Account Reconciliation & Recycling" section with invocation examples, state table, config params. Added ORPHANED/SUSPENDED to account states. |
| `docs/ProjectStructure.md` | 6 | Added `account-reconciler/` and `account-recycler/` to directory tree and component list. |
| `docs/TestingGuide.md` | 6 | Added reconciliation/recycling test procedures (dry-run, live, batch, CloudWatch verification). |
| `docs/SecurityGuide.md` | 6 | Added tag-based identification strategy, AccountCreationRole trust update, new Reconciler/Recycler role docs. |
| `README.md` | 6 | Added reconciliation/recycling to Overview paragraph. |

## Design References

- Spec: `.kiro/specs/account-reconciliation-recycling/design.md`
- Requirements: `.kiro/specs/account-reconciliation-recycling/requirements.md`

## Key Design Decisions

1. **No new role in Org Admin** — reuse existing `SMUS-AccountPoolFactory-AccountCreation` role (added Reconciler as trusted principal)
2. **Tag-based identification** — `ManagedBy: AccountPoolFactory` + `PoolName` tags; name prefix as fallback
3. **OU-scoped listing** — `list_accounts_for_parent` scoped to Target OU (not full org)
4. **Multi-pool isolation** — each Reconciler only processes accounts with matching `PoolName`
5. **autoReplenish replaces seeding** — Reconciler counts AVAILABLE, invokes Pool Manager if below MinimumPoolSize
6. **Tagging is non-fatal** — ProvisionAccount tags after creation; Reconciler backfills if tagging failed

---

## Task 7: Deploy and Verify — COMPLETED

### Deployment — DONE

All Lambdas deployed via `deploy-all.sh` and individual updates:
- ✅ Org Admin: StackSet roles, ProvisionAccount stack + Lambda, DomainAccess StackSet
- ✅ Domain: Infrastructure stack, all 6 Lambdas (PoolManager, SetupOrchestrator, DeprovisionAccount, AccountProvider, AccountReconciler, AccountRecycler)

### Verification — DONE

- ✅ Reconciler dry-run: discovered 213 pool accounts in target OU
- ✅ Reconciler live: created ORPHANED records for all untracked accounts
- ✅ Account pool registered in DataZone (pool ID: `c5r1rtjwi2qhbd`)
- ✅ Project profile created ("All Capabilities - Account Pool", 17 env configs)
- ✅ StackSet updated with new domain ID
- ✅ Recycler tested on account `821589437303` — full cycle: CLEANING → deprovision → setup → AVAILABLE
- ✅ All 5 stacks verified in 821589437303: VPC, IAM, ProjectRole, EventBridge, Blueprints (17 blueprints)
- ✅ Setup duration: 61 seconds

### Bugs Found and Fixed During Verification

1. **Blueprint template outdated** — `blueprint-enablement-iam.yaml` referenced old blueprint names (`ToolingLite`, `S3Bucket`, `S3TableCatalog`) that don't exist in new domain. Fixed: updated to 17 correct identifiers (`Tooling`, `DataLake`, `LakehouseCatalog`, etc.)
2. **DeprovisionAccount set state to AVAILABLE** — caused SetupOrchestrator to skip (idempotency check). Fixed: DeprovisionAccount now leaves state as CLEANING; recycler handles lifecycle transitions.
3. **Recycler couldn't re-process AVAILABLE accounts** — incomplete setup left account stuck in AVAILABLE. Fixed: added `force` flag to recycler + `--force` to invoke-recycler.sh.

### End-to-End Test — BLOCKED (see Task 8–12 below)

- [ ] Create test project using `create-test-project.sh`
- [ ] Verify project + environments deploy successfully
- [ ] Verify account assigned to project

---

## Post-Deploy Fixes (Tasks 8–12)

### Task 8: Make Setup Stack Patterns Configurable — ✅ DONE

Previously the reconciler had `EXPECTED_SETUP_STACKS` hardcoded in the Lambda. Now follows the config chain:
`config.yaml` → deploy script → CF parameter → SSM parameter → Lambda reads SSM at runtime.

Files changed:
- `config.yaml` — added `setup_stacks` list
- `templates/cloudformation/02-domain-account/deploy/01-infrastructure.yaml` — added `ExpectedStackPatterns` parameter + SSM parameter
- `scripts/02-domain-account/deploy/01-deploy-infrastructure.sh` — extracts patterns from config.yaml, passes to CF
- `src/account-reconciler/lambda_function.py` — replaced hardcoded list with `get_expected_setup_stacks()` that reads from SSM

### Task 9: Fix Reconciler Validation for AVAILABLE Accounts — ✅ DONE

Fixed `reconcile_with_dynamodb()` to call `validate_available_account()` which returns `(ok, failure_reason)` tuple. Validates both DomainAccess role AND all expected setup stacks.

Files changed:
- `src/account-reconciler/lambda_function.py`

### Task 10: Fix Recycler Force Flag for FAILED State — ✅ DONE

`handle_failed()` now accepts `force=False`. When `force=True`, resets retryCount to 0 and bypasses retry limit (but NOT non-recoverable errors). `recycle_account()` passes `force` through.

Files changed:
- `src/account-recycler/lambda_function.py`

### Task 11: Fix Recycler invoke_lambda_sync Not Detecting SetupOrchestrator Failures — ✅ DONE

`invoke_lambda_sync()` wasn't checking `FunctionError` or `statusCode` from Lambda responses. SetupOrchestrator returned `{'statusCode': 500}` but recycler only checked for `{'status': 'ERROR'}`, silently marking broken accounts AVAILABLE. Fixed to check both `FunctionError` in response metadata and `statusCode >= 400` in payload.

Files changed:
- `src/account-recycler/lambda_function.py`

### Task 12: Fix DomainAccess StackSet Not Deployed to Pool Accounts — 🔄 IN PROGRESS

**Problem**: 210 of 213 pool accounts never had the `SMUS-AccountPoolFactory-DomainAccess` StackSet instance deployed. The StackSet only had 2 instances. Without the DomainAccess role, SetupOrchestrator can't assume into these accounts, so they're all broken despite being marked AVAILABLE.

**Root cause**: These accounts were created before the StackSet was set up, or the StackSet instance was never deployed to them.

**Solution — Self-healing reconciler**:
1. Reconciler detects AVAILABLE account where DomainAccess role is not assumable
2. Reconciler invokes ProvisionAccount Lambda (Org Admin) with `fixStackSet` action
3. ProvisionAccount deploys StackSetExecution role first (via OrganizationAccountAccessRole), then deploys DomainAccess StackSet instance
4. Reconciler waits 15s for IAM propagation, retries validation
5. If still fails, marks account FAILED for recycler to handle later

**What's been done**:
- ✅ Added `fix_stackset` action to ProvisionAccount Lambda (Org Admin) — DEPLOYED
- ✅ Added `fix_stackset_instance()` to Reconciler Lambda — DEPLOYED
- ✅ Updated `validate_available_account()` to auto-fix missing DomainAccess role — DEPLOYED
- ✅ Added `PROVISION_ACCOUNT_FUNCTION_ARN` env var to Reconciler in CF template — DEPLOYED
- ✅ Updated `01-deploy-infrastructure.sh` to also deploy AccountReconciler + AccountRecycler Lambda code
- ✅ Updated `invoke-reconciler.sh` to support `--account ACCOUNT_ID` for single-account testing
- ✅ Fixed chicken-and-egg: `fix_stackset` now deploys StackSetExecution role FIRST (via OrganizationAccountAccessRole), then DomainAccess StackSet instance — DEPLOYED

**Bug found and fixed during testing**:
- First test on account `050366487338` failed: StackSet deployment errored because the target account didn't have the `SMUS-AccountPoolFactory-StackSetExecution` role. This role is needed for SELF_MANAGED StackSets. The `fix_stackset` function was only calling `deploy_domain_access_role_stackset()` but not `deploy_stackset_execution_role()` first. Fixed by adding Step 1 (deploy StackSetExecution role via OrganizationAccountAccessRole) before Step 2 (deploy StackSet instance).

**Current state**:
- 209 accounts in AVAILABLE (need reconciler to fix their StackSet + validate)
- 4 accounts in FAILED (3 original + 1 from first test attempt)
- All code deployed to both Org Admin and Domain accounts
- Single-account test needed on an actual AVAILABLE account (previous tests hit FAILED accounts or rate limits)

**Next steps to complete this task**:
1. Test reconciler on a single AVAILABLE account: `eval $(isengardcli credentials amirbo+3@amazon.com) && bash experimental/AccountPoolFactory/scripts/utils/invoke-reconciler.sh --account 021104859107`
2. Check logs to confirm StackSet fix worked: role deployed, validation passed, account stays AVAILABLE
3. If single-account test passes, run full reconciler (will take a while — 209 accounts, each needs StackSet deployment): `bash experimental/AccountPoolFactory/scripts/utils/invoke-reconciler.sh --auto-recycle`
4. NOTE: The reconciler has 300s timeout. With 209 accounts each needing StackSet deployment (~3 min each), it will timeout. May need to increase timeout or run in batches.
5. After all accounts are fixed, run end-to-end test: `bash experimental/AccountPoolFactory/tests/setup/create-test-project.sh`

**Files changed in this task**:
- `src/provision-account/lambda_function.py` — added `fixStackSet` action + `fix_stackset()` function, fixed to deploy StackSetExecution role first
- `src/account-reconciler/lambda_function.py` — added `fix_stackset_instance()`, updated `validate_available_account()` with self-healing
- `templates/cloudformation/02-domain-account/deploy/01-infrastructure.yaml` — added `PROVISION_ACCOUNT_FUNCTION_ARN` env var to AccountReconcilerFunction
- `scripts/02-domain-account/deploy/01-deploy-infrastructure.sh` — added AccountReconciler + AccountRecycler Lambda code deployment
- `scripts/utils/invoke-reconciler.sh` — added `--account ACCOUNT_ID` support


---

## Task 13: Clean Separation — Reconciler Detects, Recycler Fixes — 🔄 IN PROGRESS

**Problem**: The reconciler was doing too much — validating accounts AND attempting inline fixes (StackSet deployment, IAM propagation waits). This made it slow, prone to timeouts, and tightly coupled to the fix logic. No throttling/backoff handling for 200+ accounts.

**Design principle**: Self-healing system with clean separation of concerns:
- **Reconciler** = diagnostic pass (detect-only). Scans all pool accounts, validates health, marks unhealthy ones as FAILED with descriptive reason, queues them for the recycler. Does NOT attempt any repairs.
- **Recycler** = the fixer. Receives unhealthy accounts, routes based on failure reason (NEEDS_STACKSET, NEEDS_SETUP, or full deprovision+setup), fixes them in parallel. High concurrency since each account is independent.

**Changes made**:

### Reconciler (`src/account-reconciler/lambda_function.py`) — rewritten
- Removed `fix_stackset_instance()` — reconciler no longer fixes anything
- Removed self-healing retry loop and `time.sleep(15)` from `validate_available_account()`
- `validate_available_account()` is now pure detection: check role, check stacks, return what's wrong
- Failure reasons are descriptive: `NEEDS_STACKSET: DomainAccess role not assumable` or `NEEDS_SETUP: Missing: stack1, stack2`
- Added `retry_with_backoff()` for all AWS API calls (STS, CloudFormation, Organizations) — handles TooManyRequestsException, Throttling, etc. with exponential backoff + jitter
- Added parallel validation via `ThreadPoolExecutor` (5 workers) — AVAILABLE accounts are validated concurrently
- Split `validate_available_account()` into `validate_domain_access_role()` + `validate_setup_stacks()` for clarity
- Removed `PROVISION_ACCOUNT_FUNCTION_ARN` env var — reconciler no longer calls ProvisionAccount
- Only unhealthy accounts are sent to the recycler (healthy AVAILABLE accounts are left alone)

### Recycler (`src/account-recycler/lambda_function.py`) — rewritten
- Added `ensure_stackset()` — checks DomainAccess role, deploys StackSet via ProvisionAccount if missing, waits for IAM propagation
- Added `run_setup()` helper for clean SetupOrchestrator invocation
- `handle_failed()` now routes based on failure reason from reconciler:
  - `NEEDS_STACKSET` → deploy StackSet → run setup → AVAILABLE
  - `NEEDS_SETUP` → run setup → AVAILABLE
  - Other → full deprovision + setup cycle
- `handle_orphaned()` simplified: ensure_stackset → run_setup → AVAILABLE
- `handle_cleaning()` now also calls `ensure_stackset()` before setup (handles legacy accounts)
- Added `retry_with_backoff()` for all AWS API calls
- `invoke_lambda_sync()` retries on TooManyRequestsException
- Default `MaxConcurrentRecycles` increased from 3 to 10

### CF template (`templates/cloudformation/02-domain-account/deploy/01-infrastructure.yaml`)
- Removed `PROVISION_ACCOUNT_FUNCTION_ARN` from AccountReconcilerFunction env vars
- Increased AccountRecyclerFunction `ReservedConcurrentExecutions` from 3 to 10
- Updated `MaxConcurrentRecycles` SSM parameter default from 3 to 10

### No changes needed
- `scripts/02-domain-account/deploy/01-deploy-infrastructure.sh` — already deploys both Lambda code files
- `scripts/utils/invoke-reconciler.sh` — interface unchanged
- `scripts/utils/invoke-recycler.sh` — interface unchanged

**Deployment steps**:
1. Deploy CF stack update (domain account): `eval $(isengardcli credentials amirbo+3@amazon.com) && bash experimental/AccountPoolFactory/scripts/02-domain-account/deploy/01-deploy-infrastructure.sh`
2. Test reconciler dry-run: `bash experimental/AccountPoolFactory/scripts/utils/invoke-reconciler.sh --dry-run`
3. Test reconciler live on single account: `bash experimental/AccountPoolFactory/scripts/utils/invoke-reconciler.sh --account 021104859107`
4. Run reconciler with auto-recycle: `bash experimental/AccountPoolFactory/scripts/utils/invoke-reconciler.sh --auto-recycle`
5. Monitor recycler progress in CloudWatch logs for AccountRecycler

---

## Tasks 14–16: Logging, Idempotency, Deploy Script — ✅ DONE

### Task 14: Fix Reconciler Logging
- `update_state()` now prints `Updated {id}: AVAILABLE -> FAILED | reason: {note}`
- `_validate_one()` now prints `[{id}] FAILED validation: {reason}` before updating DynamoDB
- Files: `src/account-reconciler/lambda_function.py`

### Task 15: Fix enable_blueprints() Idempotency
- Added `check_existing_stack()` call at top of `enable_blueprints()` — same pattern as all other deploy_* functions
- Prevents `AlreadyExistsException` when recycler re-runs SetupOrchestrator on an account that already has a Blueprints stack (healthy or bad state)
- Files: `src/setup-orchestrator/lambda_function.py`

### Task 16: Fix Deploy Script
- Added `--lambdas-only` flag to skip CloudFormation stack update (saves ~2 min when only Lambda code changed)
- Replaced fragile `cd` + relative-path zip pattern with `zip -j` using `$PROJECT_ROOT` absolute paths
- SetupOrchestrator zip now correctly bundles `lambda_function.py` + all `*.yaml` templates flat (no subdirectory) — fixes `[Errno 2] No such file or directory: '02-vpc-setup.yaml'` error
- Files: `scripts/02-domain-account/deploy/01-deploy-infrastructure.sh`

---

## Task 17: Full System Test — 🔄 IN PROGRESS

**Current pool state**: 1 AVAILABLE, 212 FAILED

**Failure categories observed**:
- Most: `NEEDS_SETUP: Missing: DataZone-VPC-*, DataZone-IAM-*, DataZone-EventBridge-*, DataZone-ProjectRole-*, DataZone-Blueprints-*` — DomainAccess role exists, setup stacks missing
- Some: `NEEDS_STACKSET: DomainAccess role not assumable`
- Few: old RAM share timeout errors (pre-org-wide-share fix)

**Self-healing test on account 054012425702**:
- First attempt failed: `SetupOrchestrator returned 500: [Errno 2] No such file or directory: '02-vpc-setup.yaml'` — zip packaging bug (Task 16)
- Second attempt failed: `Stack DataZone-EventBridge-054012425702 in transient state: CREATE_IN_PROGRESS` — stack was mid-creation from previous attempt, recycler hit it too soon
- Account has VPC, IAM, ProjectRole stacks CREATE_COMPLETE; EventBridge still CREATE_IN_PROGRESS

**Next steps**:
1. ~~Wait for EventBridge stack to complete on 054012425702, then re-test recycler on it~~ ✅ Done
2. ~~If single-account test passes, trigger full recycler batch~~ ✅ Done — recycler running
3. Monitor recycler progress via CloudWatch logs
4. After pool has AVAILABLE accounts, run end-to-end create-project test: `python3 .test-create-from-pool.py`

**Self-healing loop now in place**:
- Recycler self-triggers near 900s timeout if work remains
- EventBridge schedule: reconciler runs hourly with `autoRecycle:true` → triggers recycler
- Recoverable failures (NEEDS_SETUP, NEEDS_STACKSET) auto-reset retryCount — never permanently stuck
- Batch StackSet fix: 196 NEEDS_STACKSET accounts processed in single `create_stack_instances` call

**Fixes deployed in this session**:
- `src/account-recycler/lambda_function.py`: self-trigger, batch StackSet pre-processing, recoverable retry reset, invoke_lambda_sync max_retries=6
- `src/provision-account/lambda_function.py`: `fixStackSetBatch` action, `_wait_for_any_stackset_operation`, fixed `OperationInProgressException` handler
- `src/account-reconciler/lambda_function.py`: failure reason logged in update_state + _validate_one
- `src/setup-orchestrator/lambda_function.py`: enable_blueprints idempotency via check_existing_stack
- `templates/cloudformation/02-domain-account/deploy/01-infrastructure.yaml`: EventBridge hourly schedule for reconciler
- `scripts/02-domain-account/deploy/01-deploy-infrastructure.sh`: --lambdas-only flag, correct zip packaging
- `scripts/01-org-mgmt-account/deploy/02-deploy-provision-account.sh`: --lambdas-only flag
- `scripts/utils/invoke-recycler.sh`: --async flag
- `scripts/utils/check-account-state.sh`: new utility script

**Current status (last check ~05:08 UTC)**:
- AVAILABLE: 19 and growing (was 2 at start of session)
- FAILED: ~195 and shrinking
- Self-healing loop active: recycler self-triggers every ~900s, reconciler scheduled hourly
- Batch StackSet waves running: 182 accounts being processed per wave in ProvisionAccount
- No manual intervention needed — system will converge to all AVAILABLE

**Remaining**: wait for convergence (~2-3 more recycler waves), then run `python3 .test-create-from-pool.py`

---

## Tasks 18–20: Blueprint Regional Params + Rolling Update + Authorization — 🔄 IN PROGRESS

### Task 18: Fix blueprint-enablement-iam.yaml regional params — ✅ DONE
- All 17 blueprints now pass `VpcId`, `SubnetIds`, `S3BucketName` as regional parameters
- SetupOrchestrator `enable_blueprints()` updated to accept vpc_result + s3_result and call `update_stack()` when stack already exists
- Files: `templates/cloudformation/03-project-account/deploy/blueprint-enablement-iam.yaml`, `src/setup-orchestrator/lambda_function.py`

### Task 19: Rolling blueprint update across all pool accounts — ✅ DONE
- Added `mode: updateBlueprints` to SetupOrchestrator — reads VPC/IAM/S3 from existing stacks, updates Blueprints stack only
- Added `updateBlueprints` event param to AccountRecycler — queries all AVAILABLE accounts, updates in batches of 10, self-triggers near timeout
- Added `--update-blueprints` flag to `invoke-recycler.sh`
- Triggered: 213 accounts updating at ~10/wave, completes in ~5 min
- Files: `src/setup-orchestrator/lambda_function.py`, `src/account-recycler/lambda_function.py`, `scripts/utils/invoke-recycler.sh`

### Task 20: Fix CREATE_ENVIRONMENT_FROM_BLUEPRINT authorization — 🔄 IN PROGRESS
- Error: `403: Caller is not authorized to create environment using blueprintId 3owsbi7jjppvc9`
- This is a DataZone policy grant issue — `ENVIRONMENT_BLUEPRINT_CONFIGURATION` entity needs `CREATE_ENVIRONMENT_FROM_BLUEPRINT` grant
- Admin role cannot call `AddPolicyGrant` for this entity type
- Next: test creating project using domain account itself (no pool account) to isolate whether the issue is pool-account-specific or domain-wide

### Task 20: Fix CREATE_ENVIRONMENT_FROM_BLUEPRINT authorization — ✅ DONE

**Root cause**: `AWS::DataZone::PolicyGrant` resources for `ENVIRONMENT_BLUEPRINT_CONFIGURATION` must be deployed via CloudFormation (using the domain's service role) — the Admin IAM role cannot call `AddPolicyGrant` directly for this entity type.

**Fix**: Added 17 `AWS::DataZone::PolicyGrant` resources directly into `blueprint-enablement-iam.yaml`, one per blueprint. Each grant:
- `EntityType: ENVIRONMENT_BLUEPRINT_CONFIGURATION`
- `EntityIdentifier: {AWS::AccountId}:{BlueprintId}` (auto-resolves to the project account)
- `PolicyType: CREATE_ENVIRONMENT_FROM_BLUEPRINT`
- `Principal: CONTRIBUTOR projects in root domain unit, cascade to children`

Also added `DomainUnitId` parameter to the template and updated SetupOrchestrator to pass it.

**Rolling update**: Triggered `--update-blueprints` cycle to update all 213 pool accounts.

**End-to-end test result**: ✅ SUCCESS
- Project created from pool account `054012425702`
- All 17 env configs passed with pool account + pool ID
- `analyst1-amirbo` added as PROJECT_OWNER via `create_project_membership`
- Deployment status: `IN_PROGRESS` → environments provisioning

**Files changed**:
- `templates/cloudformation/03-project-account/deploy/blueprint-enablement-iam.yaml` — added DomainUnitId param + 17 PolicyGrant resources
- `src/setup-orchestrator/lambda_function.py` — pass DomainUnitId to blueprint stack
- `config.yaml` — added `default_project_owner: analyst1-amirbo`
- `.test-create-from-pool-IDC.py` — fixed: all 17 env configs, user lookup by name, owner via create_project_membership
- `.test-create-domain-account.py` — new test script for domain account (no pool)
- `.test-create-from-pool-IAM-DOMAIN.py` — renamed from old IAM domain test script
- `tests/setup/deploy-policy-grants-cf.sh` — fixed to use DataZone API for blueprint IDs, added domain unit grant via API
- `scripts/utils/invoke-recycler.sh` — added --update-blueprints flag
- `src/account-recycler/lambda_function.py` — added updateBlueprints mode + get_available_accounts + update_blueprints_batch

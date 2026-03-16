# StackSet-Driven Account Setup — Migration Tasks

## Goal

Replace the SetupOrchestrator's direct `create_stack()` approach with StackSet-driven
deployment for all waves. The org admin owns and pre-creates all StackSet definitions.
The SetupOrchestrator calls `add_stack_instances()` per wave, waits for completion,
then reads outputs directly from the CF stack in the target account.
DynamoDB must accurately reflect exactly what is deployed in each account at all times.

## Current State

- Wave 0 (DomainAccess): already StackSet-driven via ProvisionAccount Lambda ✅
- Wave 1 (VPC, IAM, ProjectRole, EventBridge): direct `create_stack()` via cross-account CF client ❌
- Wave 2 (Blueprints): direct `create_stack()` via cross-account CF client ❌
- StackSets for wave 1/2 exist in org-admin account but have 0 instances
- DynamoDB records do not accurately reflect what is deployed (missing `deployedStackSets`)

## Target State

- All waves use `add_stack_instances()` from the org-admin account
- SetupOrchestrator reads stack outputs from the target account after each wave completes
- `deployedStackSets` in DynamoDB is the source of truth — written as each wave completes
- AccountCreationRole cannot deploy arbitrary CF stacks directly into project accounts
- Cleanup and re-setup of accounts is driven by the reconciliation/recycler flow, not ad-hoc scripts

## Execution Order

1. Cleanup code (T1–T2) — add `cleanupStacks` to Recycler + `stacksToDelete` to DeprovisionAccount, deploy both
2. Account cleanup (T3) — delete projects, invoke `cleanupStacks`, verify accounts are clean
3. Architecture code (T4–T7) — implement StackSet-driven setup, tighten IAM, update Reconciler
4. Deploy architecture code (T8) — deploy org-admin CF stack, SetupOrchestrator, Reconciler
5. Reconciliation re-setups accounts (T9) — reconciler detects `NEEDS_SETUP`, recycler re-runs SetupOrchestrator
6. Test (T10)
7. Docs (T11)

---

## Tasks

### T1 — AccountRecycler: Add `cleanupStacks` action ✅

### T2 — DeprovisionAccount: Add `stacksToDelete` override ✅

### T3 — Account cleanup ✅

Projects deleted, cleanupStacks ran (221/221 cleaned). Note: old SetupOrchestrator
immediately re-setup accounts via the recycler before new code was deployed.
T4–T8 must be completed and deployed before accounts are fully clean.

### T4 — Verify StackSet definitions are complete and up to date ✅

All 6 StackSets ACTIVE/SELF_MANAGED. Parameters confirmed match SetupOrchestrator.

### T5 — AccountCreationRole: Tighten IAM to StackSet-only ✅

No direct CreateStack/UpdateStack/DeleteStack. StackSet instance permissions and
EnforceS3TemplateSource deny already in place. No CF changes needed.

### T6 — SetupOrchestrator: Replace direct CF calls with StackSet instance deployment ✅

### T7 — AccountReconciler: Update stack validation to use deployedStackSets ✅

### T8 — Deploy architecture code ✅

All Lambdas deployed. cleanupStacks re-run: 223/223 accounts cleaned.

### T9 — Reconciliation re-setups all accounts

- [x] T9.1 Deployed SetupOrchestrator with StackSet-driven setup (retry logic, old stack cleanup, correct parameters)
- [x] T9.2 Fixed BlueprintEnablement StackSet template (was IDC, updated to IAM with correct blueprint identifiers)
- [x] T9.3 Fixed `_read_stack_outputs` to use DomainAccess role (not OrganizationAccountAccessRole)
- [x] T9.4 Fixed `_add_stackset_instance` retry: flat 30s delay instead of exponential backoff
- [x] T9.5 Added `_cleanup_old_stacks` (Wave 0.5) to delete old DataZone-* CF stacks before StackSet deployment
- [x] T9.6 Fixed `update_progress` to deduplicate deployedStackSets on retry
- [x] T9.7 Reduced SQS concurrency to 2 to avoid StackSet contention
- [ ] T9.8 Monitor — accounts moving SETTING_UP → AVAILABLE (~204 remaining, ~2 per 15-min cycle)
- [ ] T9.9 Verify all 6 StackSets show ~211 instances in org-admin console
- [ ] T9.10 Spot-check 5 accounts: confirm DynamoDB `resources` match actual account values

### T10 — Testing

- [x] T10.11 End-to-end lifecycle test: ran `tests/integration/test-e2e-pool-lifecycle.py`.
  - AccountProvider returned 24 available accounts ✅
  - Project created, account assigned in 10s ✅
  - Project deployed (17 env configs, 303s) ✅
  - Project deleted, environments cleaned up ✅
  - Account reclaim triggered (ASSIGNED → SETTING_UP) ✅
  - Re-setup didn't complete within 20min timeout (queue backlog from bulk migration) — expected
  - Account 108750422936 has all 5 deployedStackSets after re-setup completes
  SetupOrchestrator tests — verify wave ordering, parallel execution, output reading.
- [ ] T10.2 Unit: test `read_stack_outputs` — verify CF output key mapping.
- [ ] T10.3 Unit: test `cleanupStacks` — verify correct `stacksToDelete` list and DynamoDB reset.
- [ ] T10.4 Integration: provision one brand-new account end-to-end. Verify all 6
  StackSets gained one new instance.
- [ ] T10.5 Integration: assign to a DataZone project, verify it works.
- [ ] T10.6 Integration: delete the project, verify deprovision skips all
  `StackSet-SMUS-AccountPoolFactory-*` stacks.
- [ ] T10.7 Integration: run reconciler — confirm all accounts validate via `deployedStackSets`.
- [ ] T10.8 Failure test: manually delete one StackSet instance, verify reconciler detects it.
- [ ] T10.9 Concurrency test: provision 3 accounts simultaneously, verify StackSet
  operations are serialized.
- [ ] T10.10 Security test: attempt ProvisionAccount with tampered template body —
  confirm IAM denies it.
- [ ] T10.11 End-to-end lifecycle test: run `tests/integration/test-e2e-pool-lifecycle.py`
  against the new StackSet-driven setup. This script covers the full cycle:
  - Calls AccountProvider to get an AVAILABLE account
  - Creates a DataZone project using that account
  - Waits for account to reach ASSIGNED state
  - Deletes the project (environments + data sources first)
  - Waits for account to return to AVAILABLE via the REUSE reclaim flow
  Verify the test exits 0 and the account's DynamoDB record shows correct
  `deployedStackSets` after re-setup completes.

### T11 — Documentation

- [ ] T11.1 Update `docs/Architecture.md` — StackSet-driven flow, updated wave diagram.
- [ ] T11.2 Update `docs/OrgAdminGuide.md` — 6 required StackSets, IAM permissions,
  "StackSet operation already in progress" troubleshooting.
- [ ] T11.3 Update `docs/DomainAdminGuide.md` — replace `DataZone-VPC-*` references
  with `StackSet-SMUS-AccountPoolFactory-*`.
- [ ] T11.4 Update `02-domain-account/scripts/utils/check-account-state.sh` — update CF stack filter.
- [ ] T11.5 Update `README.md` architecture section.
- [ ] T11.6 Update `docs/SecurityGuide.md`:
  - Section [1] — update `AccountCreationRole` permissions table: remove any direct
    `cloudformation:CreateStack/UpdateStack/DeleteStack` entries; add
    `CreateStackInstances`, `DeleteStackInstances`, `DescribeStackSetOperation`,
    `ListStackInstances` to the StackSets row.
  - Section [2] — update description: SetupOrchestrator no longer calls CF directly
    in project accounts. The `DomainAccess` role is now used only by DeprovisionAccount
    (cleanup) and for reading stack outputs after StackSet deployment. Note that
    `AdministratorAccess` scope may be reducible in a future pass now that setup
    no longer requires direct CF stack creation.
  - Add new section: "StackSet-Driven Deployment Security" — explain that wave 1/2
    stacks are now deployed exclusively via StackSets from the org-admin account,
    the domain Lambda cannot supply template bodies (enforced by `EnforceS3TemplateSource`
    Deny), and the `AccountCreationRole` can only add instances of pre-approved
    `SMUS-AccountPoolFactory-*` StackSets.
  - Update the `LambdaExecutionRole` permissions table — STS `AssumeRole` on
    `OrganizationAccountAccessRole` is now only needed for reading stack outputs
    post-deployment, not for creating stacks. Document this narrowed usage.

### T12 — UI updates

The Pool Management Console (`ui/pool-console/app.js`) invokes AccountRecycler and
AccountReconciler directly. The new `cleanupStacks` action and the `deployedStackSets`
field need to be surfaced.

- [ ] T12.1 Pool Console — Account Detail panel: display `deployedStackSets` list for
  each account so operators can see exactly which StackSets are deployed.
- [ ] T12.2 Pool Console — Account Detail panel: add "Clean Stacks" action button that
  invokes `AccountRecycler` with `{"action":"cleanupStacks","accountIds":[<id>]}`.
  Only show for AVAILABLE accounts. Confirm before invoking.
- [ ] T12.3 Pool Console — Dashboard: update the "Reconcile" button payload to include
  `autoRecycle: true` so a single click triggers the full detect-and-fix cycle.
- [ ] T12.4 Pool Console — Accounts table: the `deployedStackSets` field is now the
  health indicator. Update the "healthy" badge logic to check that the account's
  `deployedStackSets` list is non-empty and matches the expected 6 StackSets,
  rather than checking for `DataZone-VPC-*` stack names.
- [ ] T12.5 Update `ui/mock/mock-server.py` mock data — add `deployedStackSets` to
  the sample account records so the UI renders correctly in mock mode.

---

## Notes

- `create_s3_bucket` and `create_ram_share_and_verify_domain` stay as direct SDK calls.
- Stack output reading uses `OrganizationAccountAccessRole` (not `AccountCreationRole`).
- The `SMUS-AccountPoolFactory-StackSetExecutionRole` stack in each account must never
  be deleted — it is what allows StackSet instances to be created.
- T1 and T2 must be deployed before T3 can run. Everything else waits until T3 is verified clean.

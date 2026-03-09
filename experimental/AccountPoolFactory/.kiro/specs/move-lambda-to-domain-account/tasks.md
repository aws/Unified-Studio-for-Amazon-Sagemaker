# Move ProvisionAccount Lambda to Domain Account

## Goal
Move the ProvisionAccount Lambda from the Org Admin account (495869084367) to the Domain account (994753223772). The Org Admin account should only contain a minimal, auditable CloudFormation stack that exposes a scoped cross-account IAM role. All application logic (Lambdas, DynamoDB, EventBridge, etc.) stays in the Domain account.

## Design Principles
- Org Admin account = governance only. Simple template, easy to audit, easy to install.
- Domain account = all application logic. PoolManager invokes ProvisionAccount locally (same account).
- The cross-account role in Org Admin is scoped to only the Organizations + StackSet actions needed.
- Adding new approved StackSets should be a one-line addition to the Org Admin template.

## Current State
- **Org Admin account** deploys 3 CF templates:
  - `01-stackset-roles.yaml` — StackSetAdmin role (CloudFormation service assumes it)
  - `02-provision-account.yaml` — ProvisionAccount Lambda + AccountCreation cross-account role
  - `03-domain-access-stackset.yaml` — StackSet template body for DomainAccess role in project accounts
- **Domain account** deploys `01-infrastructure.yaml` — all other Lambdas, DynamoDB, EventBridge, SSM, SNS
- PoolManager (domain) invokes ProvisionAccount (org admin) cross-account via `lambda:InvokeFunction`

## Target State
- **Org Admin account** deploys a single simplified template:
  - `SMUS-AccountPoolFactory-OrgAdmin.yaml` containing:
    - `AccountCreation` IAM role (trusted by domain account, scoped to Organizations + StackSet APIs)
    - `StackSetAdmin` IAM role (trusted by CloudFormation service, for StackSet deployments)
    - All StackSet definitions (DomainAccess, and future ones) — defined inline or referenced
    - A clear `ApprovedStackSets` section/mapping so org admins can see and add StackSets easily
  - One deploy script: `deploy-org-admin.sh`
  - No Lambdas, no application code
- **Domain account** gets ProvisionAccount Lambda added to `01-infrastructure.yaml`:
  - ProvisionAccount Lambda + its code
  - Lambda execution role with `sts:AssumeRole` to the Org Admin `AccountCreation` role
  - PoolManager invokes ProvisionAccount locally (same account, no cross-account Lambda invoke)

---

## Tasks

- [x] 1. Redesign the Org Admin CloudFormation template
  - [x] 1.1 Create `templates/cloudformation/01-org-mgmt-account/deploy/SMUS-AccountPoolFactory-OrgAdmin.yaml` that consolidates:
    - StackSetAdmin role (from current `01-stackset-roles.yaml`)
    - AccountCreation cross-account role (from current `02-provision-account.yaml`, minus the Lambda resources)
    - DomainAccess StackSet definition (from current `03-domain-access-stackset.yaml`)
    - A `Metadata` or `Mappings` section called `ApprovedStackSets` that lists all StackSets with their template bodies, so org admins can clearly see what gets deployed and add new ones
  - [x] 1.2 Scope the AccountCreation role permissions to only what the domain account needs:
    - `organizations:CreateAccount`, `DescribeCreateAccountStatus`, `DescribeAccount`, `ListParents`, `MoveAccount`, `CloseAccount`, `DescribeOrganization`, `ListRoots`, `ListOrganizationalUnitsForParent`, `DescribeOrganizationalUnit`, `ListTagsForResource`, `TagResource`, `ListAccountsForParent`
    - `cloudformation:CreateStackInstances`, `DescribeStackSetOperation`, `ListStackInstances`, `DescribeStackSet`, `UpdateStackSet`, `CreateStackSet` — scoped to `arn:aws:cloudformation:*:*:stackset/SMUS-AccountPoolFactory-*:*`
    - `sts:AssumeRole` on `arn:aws:iam::*:role/OrganizationAccountAccessRole` (needed to bootstrap StackSet execution role in new accounts)
  - [x] 1.3 Add clear comments/description in the template explaining what each role allows and why
  - [x] 1.4 Add Outputs that the domain account deploy script needs: AccountCreationRoleArn, ExternalId, StackSetAdminRoleArn

- [x] 2. Create simplified Org Admin deploy script
  - [x] 2.1 Create `scripts/01-org-mgmt-account/deploy/deploy-org-admin.sh` that:
    - Deploys the single consolidated template
    - Prints the outputs (role ARNs, external ID) needed by the domain account
    - Is simple enough that an org admin can read and understand it in 2 minutes
  - [ ] 2.2 Add a `scripts/01-org-mgmt-account/deploy/README.md` explaining what this installs, what permissions it grants, and how to add new approved StackSets

- [x] 3. Move ProvisionAccount Lambda to Domain account
  - [x] 3.1 Add ProvisionAccount Lambda function resource to `templates/cloudformation/02-domain-account/deploy/01-infrastructure.yaml`:
    - Same runtime/timeout/memory config as current
    - Uses a dedicated `ProvisionAccountRole` (separate from shared `LambdaExecutionRole` — different trust chain)
    - Environment variables: region, domain ID, domain account ID, org admin account ID, AccountCreationRoleArn, ExternalId
  - [x] 3.2 Update the shared `LambdaExecutionRole` in domain account template to add:
    - Lambda invoke permission for local `ProvisionAccount` function (replaces cross-account ARN)
  - [x] 3.3 Remove `ProvisionAccountFunctionArn` parameter from domain account template (no longer cross-account)
  - [x] 3.4 Update Lambda invoke permissions in domain account template — PoolManager references local ProvisionAccount

- [x] 4. Update ProvisionAccount Lambda code
  - [x] 4.1 Modify `src/provision-account/lambda_function.py` to assume the Org Admin `AccountCreation` role via STS before calling Organizations/StackSet APIs
  - [x] 4.2 Add environment variables for `ACCOUNT_CREATION_ROLE_ARN` and `EXTERNAL_ID` (read from CF parameters via Lambda env)
  - [x] 4.3 Updated error handling — STS assume-role failures surface clearly at handler entry

- [x] 5. Update PoolManager to invoke ProvisionAccount locally
  - [x] 5.1 In `src/pool-manager/lambda_function.py`, changed ProvisionAccount invocation to use local domain account ARN instead of cross-account org admin ARN
  - [x] 5.2 Removed `orgAdminAccountId` from ProvisionAccount payload (no longer needed)

- [x] 6. Update AccountRecycler to invoke ProvisionAccount locally
  - [x] 6.1 `PROVISION_ACCOUNT_FUNCTION_ARN` env var in CF template now points to local function — no code change needed in recycler

- [x] 7. Update deploy scripts
  - [x] 7.1 Updated `scripts/02-domain-account/deploy/01-deploy-infrastructure.sh`:
    - Removed `ProvisionAccountFunctionArn` parameter override
    - Added `AccountCreationRoleArn` and `ExternalId` parameters (read from org admin stack outputs)
    - Added ProvisionAccount Lambda packaging and deployment
    - Added guard: fails early if org admin stack outputs are missing
  - [x] 7.2 Updated `scripts/deploy-all.sh`: Phase 2 now calls `deploy-org-admin.sh`; Phase 1 reads org admin stack outputs; ProvisionAccount Lambda added to deploy list
  - [x] 7.3 `scripts/cleanup-all.sh` — references old test-specific stack names, not the new org admin stack; no functional change needed (cleanup of new stack handled by `cleanup-org-mgmt-account.sh`)

- [x] 8. Cleanup old Org Admin resources
  - [x] 8.1 Marked old templates as deprecated:
    - `01-stackset-roles.yaml` → deprecated header added
    - `02-provision-account.yaml` → deprecated header added
    - `03-domain-access-stackset.yaml` → StackSet definition moved into consolidated template (still used as reference)
  - [x] 8.2 Marked old deploy scripts as deprecated:
    - `01-deploy-stackset-roles.sh` → exits with deprecation message
    - `02-deploy-provision-account.sh` → exits with deprecation message
  - [x] 8.3 `config.yaml.template` — no org-admin-specific parameters changed, no update needed

- [x] 9. Write user guides (done — see task 12 below for details)

- [x] 10. Validate the refactored deployment end-to-end
  - [x] 10.1 Deploy the new consolidated org admin stack — `AccountPoolFactory-OrgAdmin` created successfully with both roles and correct outputs
  - [x] 10.2 Verified old org admin stacks deleted: `AccountPoolFactory-StackSetRoles` and `AccountPoolFactory-ProvisionAccount` gone
  - [x] 10.3 Deploy the updated domain account infrastructure stack — `AccountPoolFactory-Infrastructure` updated successfully; `ProvisionAccount` Lambda now exists in domain account (994753223772) with correct env vars
  - [x] 10.4 Verified cross-account role assumption works: invoked ProvisionAccount with unknown action — Lambda successfully assumed `SMUS-AccountPoolFactory-AccountCreation` in org admin account before returning `Unknown action` error
  - [x] 10.5 Verified PoolManager invokes ProvisionAccount locally: `force_replenishment` succeeded, logs show pool at 213 available accounts, no cross-account Lambda ARN in logs
  - [x] 10.6 Provisioned account `254076817587` end-to-end via ProvisionAccount from domain account: account created in Organizations, moved to OU, StackSetExecution role deployed, DomainAccess StackSet instance CURRENT, role assumable from domain account
  - [x] 10.7 AccountRecycler invoked successfully — ran without errors, no cross-account Lambda invocation errors
  - [x] 10.8 Full project creation test: created project via `.test-create-from-pool-IDC.py`, AccountProvider returned account, PoolManager processed assignment event, account moved to ASSIGNED state.
  - [x] 10.9 Fixed systematic issues discovered during testing:
    - EventBridge bus policy added to central bus (project accounts can now forward events)
    - Template versioning system added to all project account CF templates — bump version to force fleet-wide update
    - SetupOrchestrator `updateBlueprints` bypassing AVAILABLE accounts — fixed
    - Blueprint PolicyGrants missing from all pool accounts — fixed via `updateBlueprints` on all 212 accounts (one-time manual run; new accounts get correct template from ProvisionAccount)
    - Assignment trigger moved to `AccountProvider.validateAccountAuthorization` (reliable, immediate)
    - PoolManager now handles DataZone EventBridge events (`Environment Deployment Completed`, `Environment Deletion Completed`) for assignment and reclaim
    - Reclaim correctly waits for all environments in a project to be deleted before reclaiming account
    - End-to-end lifecycle test: `tests/integration/test-e2e-pool-lifecycle.py` — AVAILABLE→ASSIGNED in 10s, reclaim triggered in <20s ✅
  - [x] 10.10 Fixed remaining systematic gaps:
    - `wait_for_stack_complete` only checked `CREATE_COMPLETE`, not `UPDATE_COMPLETE` — caused REUSE re-setup to timeout even when stack succeeded ✅ fixed
    - `check_existing_stack` raised on `UPDATE_IN_PROGRESS` instead of waiting — caused concurrent setup failures ✅ fixed
    - Reconciler now checks blueprint template version on every scheduled run and triggers `updateBlueprints` fleet-wide if any account is outdated ✅ fixed
    - All fixes are in code/CF templates — no manual intervention needed going forward

- [ ]* 11. Migration guide (for existing deployments)
  - [x]* 11.1 Migration already performed: old 3-template org admin setup replaced with single `SMUS-AccountPoolFactory-OrgAdmin.yaml`. Old stacks (`AccountPoolFactory-StackSetRoles`, `AccountPoolFactory-ProvisionAccount`) deleted. StackSet preserved (has live instances).
  - [x]* 11.2 Safe deletion order followed: domain account infrastructure updated first (removed cross-account Lambda reference), then old org admin stacks deleted.

- [x] 9. Write user guides
  - [x] 9.1 Created `docs/OrgAdminGuide.md` — what installs, permissions, how to add StackSets, uninstall
  - [x] 9.2 Created `docs/DomainAdminGuide.md` — deployment, config, monitoring, day-to-day ops, uninstall
  - [x] 9.3 Updated `docs/TestingGuide.md` — deployment order, pool seeding, e2e lifecycle test, individual scripts, failure modes
  - [x] 9.4 Updated `scripts/README.md` to link to new guides

- [x] 12. Split UserGuide into OrgAdminGuide and DomainAdminGuide
  - [x] 12.1 Read existing `docs/UserGuide.md` and identified org admin vs domain admin content
  - [x] 12.2 Created `docs/OrgAdminGuide.md`
  - [x] 12.3 Created `docs/DomainAdminGuide.md`
  - [x] 12.4 Replaced `docs/UserGuide.md` with redirect index
  - [x] 12.5 Updated links in `README.md`, `docs/README.md`, `docs/GettingStarted.md`, `scripts/README.md`

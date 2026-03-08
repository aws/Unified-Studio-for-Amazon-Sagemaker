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

- [ ] 1. Redesign the Org Admin CloudFormation template
  - [ ] 1.1 Create `templates/cloudformation/01-org-mgmt-account/deploy/SMUS-AccountPoolFactory-OrgAdmin.yaml` that consolidates:
    - StackSetAdmin role (from current `01-stackset-roles.yaml`)
    - AccountCreation cross-account role (from current `02-provision-account.yaml`, minus the Lambda resources)
    - DomainAccess StackSet definition (from current `03-domain-access-stackset.yaml`)
    - A `Metadata` or `Mappings` section called `ApprovedStackSets` that lists all StackSets with their template bodies, so org admins can clearly see what gets deployed and add new ones
  - [ ] 1.2 Scope the AccountCreation role permissions to only what the domain account needs:
    - `organizations:CreateAccount`, `DescribeCreateAccountStatus`, `DescribeAccount`, `ListParents`, `MoveAccount`, `CloseAccount`, `DescribeOrganization`, `ListRoots`, `ListOrganizationalUnitsForParent`, `DescribeOrganizationalUnit`, `ListTagsForResource`, `TagResource`, `ListAccountsForParent`
    - `cloudformation:CreateStackInstances`, `DescribeStackSetOperation`, `ListStackInstances`, `DescribeStackSet`, `UpdateStackSet`, `CreateStackSet` — scoped to `arn:aws:cloudformation:*:*:stackset/SMUS-AccountPoolFactory-*:*`
    - `sts:AssumeRole` on `arn:aws:iam::*:role/OrganizationAccountAccessRole` (needed to bootstrap StackSet execution role in new accounts)
  - [ ] 1.3 Add clear comments/description in the template explaining what each role allows and why
  - [ ] 1.4 Add Outputs that the domain account deploy script needs: AccountCreationRoleArn, ExternalId, StackSetAdminRoleArn

- [ ] 2. Create simplified Org Admin deploy script
  - [ ] 2.1 Create `scripts/01-org-mgmt-account/deploy/deploy-org-admin.sh` that:
    - Deploys the single consolidated template
    - Prints the outputs (role ARNs, external ID) needed by the domain account
    - Is simple enough that an org admin can read and understand it in 2 minutes
  - [ ] 2.2 Add a `scripts/01-org-mgmt-account/deploy/README.md` explaining what this installs, what permissions it grants, and how to add new approved StackSets

- [ ] 3. Move ProvisionAccount Lambda to Domain account
  - [ ] 3.1 Add ProvisionAccount Lambda function resource to `templates/cloudformation/02-domain-account/deploy/01-infrastructure.yaml`:
    - Same runtime/timeout/memory config as current
    - Uses the existing shared `LambdaExecutionRole` (or a dedicated role if permissions differ significantly)
    - Environment variables: region, domain ID, domain account ID, org admin account ID, DynamoDB table, SNS topic
  - [ ] 3.2 Update the shared `LambdaExecutionRole` in domain account template to add:
    - `sts:AssumeRole` on the Org Admin `AccountCreation` role ARN (parameterized)
    - `sts:AssumeRole` on `arn:aws:iam::*:role/OrganizationAccountAccessRole` (for bootstrapping StackSet execution role)
    - `cloudformation:CreateStack`, `DescribeStacks` (for deploying StackSet execution role into new accounts via assumed role)
  - [ ] 3.3 Remove `ProvisionAccountFunctionArn` parameter from domain account template (no longer cross-account)
  - [ ] 3.4 Update Lambda invoke permissions in domain account template — PoolManager should reference the local ProvisionAccount function instead of a cross-account ARN

- [ ] 4. Update ProvisionAccount Lambda code
  - [ ] 4.1 Modify `src/provision-account/lambda_function.py` to assume the Org Admin `AccountCreation` role via STS before calling Organizations/StackSet APIs:
    - On entry, call `sts.assume_role()` with the AccountCreation role ARN and ExternalId
    - Use the temporary credentials for all `organizations.*` and `cloudformation.*` calls
    - Keep the `sts.assume_role()` for `OrganizationAccountAccessRole` (bootstrapping StackSet execution role) — this is done from the assumed AccountCreation role session
  - [ ] 4.2 Add environment variables for `ACCOUNT_CREATION_ROLE_ARN` and `EXTERNAL_ID` (read from SSM or CF parameters)
  - [ ] 4.3 Update error handling to surface STS assume-role failures clearly

- [ ] 5. Update PoolManager to invoke ProvisionAccount locally
  - [ ] 5.1 In `src/pool-manager/lambda_function.py`, change the ProvisionAccount invocation from cross-account ARN to local function name:
    - Replace `arn:aws:lambda:{region}:{org_admin_account_id}:function:ProvisionAccount` with just `ProvisionAccount` (or use an environment variable)
  - [ ] 5.2 Remove the `ProvisionAccountInvokePermission` Lambda permission resource from the old org admin template (no longer needed)
  - [ ] 5.3 Add `ProvisionAccount` to the Lambda invoke permissions in the domain account `LambdaExecutionRole`

- [ ] 6. Update AccountRecycler to invoke ProvisionAccount locally
  - [ ] 6.1 In `src/account-recycler/lambda_function.py`, update any references to the ProvisionAccount Lambda to use local invocation instead of cross-account ARN
  - [ ] 6.2 Update the `PROVISION_ACCOUNT_FUNCTION_ARN` environment variable in the domain account template to reference the local function

- [ ] 7. Update deploy scripts
  - [ ] 7.1 Update `scripts/02-domain-account/deploy/01-deploy-infrastructure.sh`:
    - Remove the `ProvisionAccountFunctionArn` parameter override (no longer cross-account)
    - Add packaging and deployment of ProvisionAccount Lambda code (zip + `update-function-code`)
    - Add `AccountCreationRoleArn` parameter (from org admin stack outputs or SSM)
  - [ ] 7.2 Update `scripts/deploy-all.sh` to reflect the new simplified org admin deployment
  - [ ] 7.3 Update `scripts/cleanup-all.sh` if it references the old org admin stacks

- [ ] 8. Cleanup old Org Admin resources
  - [ ] 8.1 Mark old templates as deprecated or remove them:
    - `01-stackset-roles.yaml` → consolidated into new template
    - `02-provision-account.yaml` → Lambda moved, role consolidated
    - `03-domain-access-stackset.yaml` → StackSet definition moved into consolidated template
  - [ ] 8.2 Mark old deploy scripts as deprecated or remove them:
    - `01-deploy-stackset-roles.sh`
    - `02-deploy-provision-account.sh`
  - [ ] 8.3 Update `config.yaml.template` if any org-admin-specific parameters changed

- [ ] 9. Write user guides
  - [ ] 9.1 Create `docs/OrgAdminGuide.md` — audience is the org admin who installs the governance stack:
    - What this installs and why (one CloudFormation stack, two IAM roles, StackSet definitions)
    - Prerequisites (AWS Organizations management account access, region)
    - Step-by-step: run `deploy-org-admin.sh`, copy the outputs, hand them to the domain admin
    - How to add a new approved StackSet (point to the `ApprovedStackSets` section in the template)
    - What permissions are granted and to whom (so the org admin can make an informed decision)
    - How to uninstall
  - [ ] 9.2 Create `docs/DomainAdminGuide.md` — audience is the domain admin who runs the pool application:
    - What this installs (all Lambdas, DynamoDB, EventBridge, SSM parameters, SNS)
    - Prerequisites (domain account access, DataZone domain ID, root domain unit ID, outputs from org admin)
    - Step-by-step: fill in `config.yaml`, run `01-deploy-infrastructure.sh`, run `02-deploy-project-profile.sh`
    - How to configure pool size, email prefix, reclaim strategy via SSM parameters
    - How to monitor the pool (CloudWatch metrics, SNS alerts, DynamoDB state table)
    - How to trigger manual replenishment, delete failed accounts
    - How to uninstall
  - [ ] 9.3 Create `docs/TestingGuide.md` — audience is a single person doing end-to-end testing (has access to both accounts):
    - Prerequisites and credential switching (`isengardcli credentials`)
    - Deployment order: org admin first, then domain admin
    - How to seed the pool and verify accounts reach AVAILABLE state
    - How to simulate account assignment (create a DataZone project) and verify ASSIGNED state
    - How to verify pool replenishment triggers
    - How to run the reconciler and recycler manually
    - Common failure modes and how to diagnose them (CloudWatch logs, DynamoDB state inspection)
  - [ ] 9.4 Update `scripts/README.md` to reflect the new deployment flow and link to the three guides above

- [ ] 10. Validate the refactored deployment end-to-end
  - [ ] 10.1 Deploy the new consolidated org admin stack and verify:
    - CF stack `AccountPoolFactory-OrgAdmin` creates successfully
    - `SMUS-AccountPoolFactory-AccountCreation` role exists with correct trust policy (domain account + ExternalId)
    - `SMUS-AccountPoolFactory-StackSetAdmin` role exists trusted by `cloudformation.amazonaws.com`
    - `SMUS-AccountPoolFactory-DomainAccess` StackSet exists and is in ACTIVE state
    - Stack outputs (AccountCreationRoleArn, ExternalId, StackSetAdminRoleArn) are present
  - [ ] 10.2 Verify the old org admin stacks are gone (or confirm they no longer conflict):
    - `AccountPoolFactory-StackSetRoles` — deleted or superseded
    - `AccountPoolFactory-ProvisionAccount` — deleted or superseded
  - [ ] 10.3 Deploy the updated domain account infrastructure stack and verify:
    - CF stack `AccountPoolFactory-Infrastructure` updates successfully
    - `ProvisionAccount` Lambda exists in the domain account (994753223772)
    - Lambda environment variables include `ACCOUNT_CREATION_ROLE_ARN` and `EXTERNAL_ID`
    - `ProvisionAccount` Lambda is no longer present in the org admin account (495869084367)
  - [ ] 10.4 Verify cross-account role assumption works from the domain account:
    - Invoke `ProvisionAccount` Lambda with a test payload `{"action": "provision", ...}` using a dry-run or canary account name
    - Confirm the Lambda successfully assumes `SMUS-AccountPoolFactory-AccountCreation` in the org admin account
    - Confirm it can call `organizations:DescribeOrganization` via the assumed role (read-only smoke test before creating real accounts)
  - [ ] 10.5 Verify PoolManager invokes ProvisionAccount locally (same account):
    - Invoke PoolManager with `{"action": "force_replenishment"}` and confirm it calls the local `ProvisionAccount` function (check CloudWatch logs — no cross-account Lambda ARN should appear)
    - Confirm no `lambda:InvokeFunction` cross-account permission errors in logs
  - [ ] 10.6 Provision one real account end-to-end and verify:
    - Account is created in AWS Organizations
    - Account is moved to the target OU
    - `SMUS-AccountPoolFactory-StackSetExecution` role is deployed into the new account
    - `SMUS-AccountPoolFactory-DomainAccess` StackSet instance is deployed into the new account
    - DynamoDB record transitions from `SETTING_UP` → `AVAILABLE`
  - [ ] 10.7 Verify AccountRecycler still works after the local invocation change:
    - Trigger a recycle manually and confirm it invokes the local `ProvisionAccount` function without errors

- [ ]* 11. Migration guide (for existing deployments)
  - [ ]* 11.1 Write a migration script or checklist for moving from the old 3-template org admin setup to the new single template
  - [ ]* 11.2 Document how to safely delete the old org admin CF stacks after deploying the new one (order matters — don't delete the Lambda before the domain account stops referencing it)

# Multi-Pool Support & Org-Controlled StackSet Configuration

## Status

| Field | Value |
|-------|-------|
| Status | 🔵 In Design |
| Last Updated | — |
| Current Phase | — |
| Current Task | — |
| Blocked By | — |

### Progress

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Configuration files | ✅ Done |
| 2 | Org admin deploy & infrastructure | ✅ Done |
| 3 | Domain admin deploy | ✅ Done |
| 4 | ProvisionAccount Lambda | ✅ Done |
| 5 | Pool Manager Lambda | ✅ Done |
| 6 | Setup Orchestrator Lambda | ✅ Done |
| 7 | Account Provider Lambda | ✅ Done |
| 8 | DeprovisionAccount Lambda | ✅ Done |
| 9 | Account Reconciler Lambda | ✅ Done |
| 10 | Account Recycler Lambda | ✅ Done |
| 11 | Documentation | ✅ Done |
| 12 | Cleanup & Redeploy | ✅ Done |
| 13 | Testing | ✅ Done |

> Status legend: ⬜ Not started · 🔄 In progress · ✅ Done · ❌ Blocked

---

## Goal

Support multiple account pools (each targeting a different OU), while keeping infrastructure deployment as a single one-time operation. The org admin declaratively defines which StackSets are allowed per pool — this is enforced both via IAM and via org-owned SSM parameters. The domain side references pools by name only and does not control what gets deployed into accounts.

## Design Summary

### Key Principles

1. **Pools are defined in `01-org-account/config.yaml`** — each pool maps to an OU and an ordered list of approved StackSets
2. **Org admin owns the StackSet templates** — CF templates are uploaded to an S3 bucket in the org admin account during deploy. The domain Lambda cannot supply its own template body.
3. **Three enforcement layers**:
   - IAM: `AccountCreationRole` scopes StackSet API calls to `SMUS-AccountPoolFactory-*` names only
   - IAM condition: `cloudformation:CreateStackSet` / `UpdateStackSet` require `TemplateURL` to match the org S3 bucket prefix (condition key `cloudformation:TemplateUrl`)
   - S3: bucket is in the org account; domain account has no direct S3 access — templates are only reachable via the assumed role
4. **Infrastructure deploys once** — adding a new pool = update `01-org-account/config.yaml` + re-run deploy script. No CF stack changes needed.
5. **Domain config simplified** — `02-domain-account/config.yaml` references pool names + sizing only. No `setup_stacks` list.

### Why S3-backed Templates Close the Security Gap

Without this, the `ProvisionAccount` Lambda (running in the domain account, assuming the org role) could call `UpdateStackSet` with an arbitrary `--template-body` containing malicious IAM policies. The IAM prefix restriction only controls *which* StackSet names can be touched — not *what* gets deployed into them.

With S3-backed templates:
- The org admin uploads approved templates to the org S3 bucket — the domain Lambda never supplies template content
- The `AccountCreationRole` IAM condition restricts StackSet create/update to only allow `TemplateURL` values pointing at the org bucket
- The domain account has no `s3:GetObject` on that bucket — it cannot read or substitute templates
- The `ProvisionAccount` Lambda passes the S3 URL (read from org SSM) to the StackSet API — it never touches the template content

### S3 Template Layout — Common vs Pool-Specific

Templates are split into two prefixes to support shared baseline templates and pool-specific ones that other pools must not use:

```
stacksets/
  common/                          # shared across all pools
    domain-access.yaml
    vpc.yaml
    iam-roles.yaml
    eventbridge.yaml
    blueprints.yaml
  pools/
    analytics/                     # only usable by the analytics pool
      analytics-specific-iam.yaml
    ml-training/                   # only usable by the ml-training pool
      gpu-instance-policy.yaml
```

IAM enforcement per pool: the `AccountCreationRole` policy uses a condition that allows `TemplateURL` matching either `stacksets/common/*` OR `stacksets/pools/{pool-name}/*`. This is enforced via two `StringLike` values in the condition. A pool cannot reference another pool's templates — the IAM condition will deny it.

The `01-org-account/config.yaml` `template` field uses a path relative to `stacksets/` — the deploy script resolves whether it lives under `common/` or `pools/{pool-name}/` and stores the full S3 URL in SSM.

### Config Structure

**`01-org-account/config.yaml`** (org admin fills this in):
```yaml
region: us-east-2   # Region for the org admin CF stack, StackSet control plane, S3 template bucket,
                    # and the target region when deploying StackSet instances into project accounts.
                    # Must match the domain account's region.

# Prefix used to derive StackSet names from template filenames.
# StackSet name = {stackset_prefix}-{template-stem}
# e.g. prefix "SMUS-AccountPoolFactory" + template "vpc.yaml" → StackSet "SMUS-AccountPoolFactory-vpc"
# Must match the IAM policy prefix — do not change after initial deploy without updating the CF stack.
stackset_prefix: "SMUS-AccountPoolFactory"   # default, can be omitted

pools:
  - name: analytics
    ou_name: "DataZone/Analytics"        # human-readable, resolved to ID automatically
    email_prefix: "analytics-pool"       # root email: analytics-pool+{uid}@example.com
    email_domain: "example.com"
    allowed_regions:                     # regions users can select when creating a project from this pool
      - us-east-1
      - us-east-2
      - us-west-2
    account_tags:                        # applied to the AWS account via Organizations TagResource
      CostCenter: "analytics-123"
      Team: "analytics"
      Pool: "analytics"                  # always added automatically if omitted
    stacksets:
      - template: domain-access.yaml     # resolved to stacksets/common/domain-access.yaml
        wave: 1
      - template: vpc.yaml               # resolved to stacksets/common/vpc.yaml
        wave: 2
      - template: iam-roles.yaml
        wave: 2
      - template: eventbridge.yaml
        wave: 2
      - template: blueprints.yaml
        wave: 3
      - template: pools/analytics/analytics-specific-iam.yaml   # pool-specific, not available to other pools
        wave: 2

  - name: ml-training
    ou_name: "DataZone/MLTraining"
    email_prefix: "ml-pool"
    email_domain: "example.com"
    allowed_regions:
      - us-east-2
      - eu-central-1
    account_tags:
      CostCenter: "ml-456"
      Team: "ml-platform"
      Pool: "ml-training"
    stacksets:
      - template: domain-access.yaml
        wave: 1
      - template: iam-roles.yaml
        wave: 2
      - template: blueprints.yaml
        wave: 3
      - template: pools/ml-training/gpu-instance-policy.yaml    # pool-specific
        wave: 2
```

Template path resolution: if the value starts with `pools/` it is used as-is under `stacksets/`; otherwise it is looked up under `stacksets/common/`. The deploy script resolves and stores the full S3 URL in SSM — the Lambda just uses the URL directly.

StackSet name derivation: `{stackset_prefix}-{template-stem-titlecased}` — e.g. `iam-roles.yaml` → `SMUS-AccountPoolFactory-IAMRoles`, `pools/analytics/analytics-specific-iam.yaml` → `SMUS-AccountPoolFactory-AnalyticsSpecificIam`. The deploy script handles the transform. The IAM condition on `cloudformation:TemplateUrl` and the StackSet name resource scope both use the same `stackset_prefix` — one value controls both security boundaries.

Templates in the same wave deploy in parallel; waves execute in ascending order.

**`02-domain-account/config.yaml`** (domain admin fills this in):
```yaml
region: us-east-2
domain_name: "your-domain-name"

pools:
  - name: analytics          # must match a pool name in 01-org-account/config.yaml
    min_size: 5
    target_size: 10
    reclaim_strategy: DELETE
    default_project_owner: "analytics-team-lead"
    project_profile_name: "All Capabilities - Account Pool"

  - name: ml-training
    min_size: 3
    target_size: 8
    reclaim_strategy: REUSE
    default_project_owner: "ml-team-lead"
    project_profile_name: "ML Capabilities - Account Pool"
```

### S3 Template Bucket (Org Admin Account)

Bucket name: `accountpoolfactory-templates-{org-account-id}` (created by `SMUS-AccountPoolFactory-OrgAdmin.yaml`)

Properties:
- Private (no public access)
- **Versioning enabled** — every `aws s3 cp` during deploy creates a new version; rollback = point StackSet at a previous version ID
- SSE-S3 encryption at rest
- Bucket policy: deny all access except from the org admin account itself and the CloudFormation service (for template fetching)

Layout:
```
stacksets/
  SMUS-AccountPoolFactory-DomainAccess.yaml
  SMUS-AccountPoolFactory-VPC.yaml
  SMUS-AccountPoolFactory-IAMRoles.yaml
  SMUS-AccountPoolFactory-EventBridge.yaml
  SMUS-AccountPoolFactory-Blueprints.yaml
  (any custom SMUS-AccountPoolFactory-*.yaml the org admin adds)
```

S3 versioning means:
- Each deploy uploads the current template, creating a new S3 version
- The StackSet `TemplateURL` always points to the latest version (no version ID in URL = latest)
- To roll back a template: copy the previous S3 version to latest (`aws s3api copy-object` with `--copy-source-version-id`), then re-run the deploy script to update the StackSet

IAM on `AccountCreationRole`:
- `s3:GetObject` on `arn:aws:s3:::accountpoolfactory-templates-{account-id}/stacksets/*` — allows CloudFormation service to fetch templates when deploying StackSet instances
- Condition on `cloudformation:CreateStackSet` / `UpdateStackSet`: `StringLike: cloudformation:TemplateUrl: https://s3.*.amazonaws.com/accountpoolfactory-templates-{account-id}/stacksets/*`

### SSM Layout

**Org admin account** (written by org deploy script, read by ProvisionAccount via assumed role):
```
/AccountPoolFactory/TemplateBucketName
/AccountPoolFactory/StackSetPrefix                       ← e.g. "SMUS-AccountPoolFactory"
/AccountPoolFactory/Pools/{pool-name}/OUId
/AccountPoolFactory/Pools/{pool-name}/EmailPrefix        ← per-pool
/AccountPoolFactory/Pools/{pool-name}/EmailDomain        ← per-pool
/AccountPoolFactory/Pools/{pool-name}/AllowedRegions     ← JSON array: ["us-east-1","us-east-2",...]
/AccountPoolFactory/Pools/{pool-name}/AccountTags        ← JSON object: {"CostCenter":"analytics-123",...}
/AccountPoolFactory/Pools/{pool-name}/StackSets          ← JSON array: [{template, stacksetName, wave}, ...]
```

`stacksetName` is pre-computed by the deploy script (`{prefix}-{derived-stem}`) and stored so the Lambda never needs to re-derive it at runtime. The Lambda constructs the full S3 URL as `https://s3.{region}.amazonaws.com/{bucket}/stacksets/{template}` and passes it to the StackSet API — it never touches the template content.

**Domain account** (written by domain deploy script, read by pool manager):
```
/AccountPoolFactory/Pools/{pool-name}/MinimumPoolSize
/AccountPoolFactory/Pools/{pool-name}/TargetPoolSize
/AccountPoolFactory/Pools/{pool-name}/ReclaimStrategy
/AccountPoolFactory/Pools/{pool-name}/ProjectProfileName  ← maps pool → DataZone project profile name; read by AccountProvider + UI
```

### DynamoDB Account Record — new fields

```json
{
  "accountId": "123456789012",
  "poolName": "analytics",
  "deployedStackSets": ["SMUS-AccountPoolFactory-DomainAccess", "SMUS-AccountPoolFactory-VPC", ...],
  "state": "AVAILABLE"
}
```

Reconciler validates against `deployedStackSets` per account, not a global config list.

### Deployment Order

The deployment order is **domain first, org second**. This allows the org admin to lock the `AccountCreationRole` trust policy to the specific `ProvisionAccount` Lambda execution role ARN rather than the entire domain account.

```
Step 1 — Domain admin deploys infrastructure stack (domain account)
         → Creates ProvisionAccount Lambda + its execution role
         → Outputs: ProvisionAccountRoleArn, DomainId, DomainAccountId

Step 2 — Domain admin hands ProvisionAccountRoleArn + DomainId to org admin

Step 3 — Org admin deploys AccountPoolFactory-OrgAdmin (org account)
         → AccountCreationRole trust policy trusts only ProvisionAccountRoleArn
         → Not the entire domain account root
```

This is a tighter trust boundary: even if another Lambda or principal in the domain account is compromised, it cannot assume `AccountCreationRole` — only the specific `ProvisionAccount` Lambda execution role can.

The `SMUS-AccountPoolFactory-OrgAdmin.yaml` template takes `ProvisionAccountRoleArn` as a parameter instead of `DomainAccountId` for the trust policy principal.

---

## Tasks

### Phase 1: Configuration

- [ ] 1.1 Update `01-org-account/config.yaml.template` — replace single `target_ou_name` with `pools` list (name, ou_name, stacksets with order)
- [ ] 1.2 Update `02-domain-account/config.yaml.template` — replace `setup_stacks` + single OU with `pools` list (name, min_size, target_size, reclaim_strategy)
- [ ] 1.3 Update `01-org-account/config.yaml` (live config) to new format with existing pool
- [ ] 1.4 Update `02-domain-account/config.yaml` (live config) to new format with existing pool
- [ ] 1.5 Update `resolve-config.sh` — parse multi-pool structure for both org and domain modes; export per-pool variables

### Phase 2: Org Admin Deploy Script & Infrastructure

- [ ] 2.1 Add S3 bucket resource to `SMUS-AccountPoolFactory-OrgAdmin.yaml`:
  - Versioning enabled (`VersioningConfiguration: Status: Enabled`)
  - SSE-S3 encryption (`BucketEncryption` with `SSEAlgorithm: AES256`)
  - `PublicAccessBlockConfiguration`: all four block settings set to `true`
  - Bucket policy: deny `s3:*` from any principal that is not the org admin account or `cloudformation.amazonaws.com`
  - Output: `TemplateBucketName`
- [ ] 2.2 Update `AccountCreationRole` trust policy in `SMUS-AccountPoolFactory-OrgAdmin.yaml`:
  - Replace `DomainAccountId` root principal with `ProvisionAccountRoleArn` parameter (specific Lambda execution role)
  - Add `ProvisionAccountRoleArn` as a required CF parameter
  - Keep `ExternalId` condition as second factor
- [ ] 2.3 Update `AccountCreationRole` IAM policy in `SMUS-AccountPoolFactory-OrgAdmin.yaml`:
  - Add `s3:GetObject` on `arn:aws:s3:::accountpoolfactory-templates-{account-id}/stacksets/*`
  - Add condition on `cloudformation:CreateStackSet` / `UpdateStackSet`: `StringLike: cloudformation:TemplateUrl: https://s3.*.amazonaws.com/accountpoolfactory-templates-{account-id}/stacksets/*`
- [ ] 2.4 Update `01-org-account/scripts/deploy/01-deploy.sh`:
  - Accept `ProvisionAccountRoleArn` as required argument (output from domain deploy)
  - Upload all templates from `approved-stacksets/cloudformation/idc/*.yaml` to `s3://{bucket}/stacksets/common/` and pool-specific templates to `s3://{bucket}/stacksets/pools/{pool-name}/`
  - Write `/AccountPoolFactory/TemplateBucketName` to SSM in org account
  - Iterate over pools, resolve each OU name → ID
  - Write per-pool SSM params (OUId, EmailPrefix, EmailDomain, AccountTags JSON, StackSets JSON with `template`+`stacksetName`+`wave` per entry)
  - Create/update StackSet definitions using S3 template URLs — never `--template-body`
- [ ] 2.5 Update `01-org-account/scripts/deploy/02-verify.sh` — verify S3 objects exist, SSM params exist per pool, StackSet definitions exist

### Phase 3: Domain Admin Deploy Script

- [ ] 3.1 Update `02-domain-account/scripts/deploy/01-deploy.sh`:
  - Deploy infrastructure stack first (no longer needs org admin outputs as prerequisite)
  - Print `ProvisionAccountRoleArn` output prominently — this is what the org admin needs
- [ ] 3.2 Update `02-domain-account/templates/cloudformation/01-infrastructure.yaml`:
  - Remove single `TargetOUId` / `ExpectedStackPatterns` params; infrastructure is pool-agnostic
  - Output `ProvisionAccountRoleArn` (the `SMUS-AccountPoolFactory-ProvisionAccount-Role` ARN) — needed by org admin deploy AND by the UI infrastructure task to scope trust policies on the two new API Lambda roles
- [ ] 3.3 Update `docs/DomainAdminGuide.md` deploy section — domain deploys first, then hands `ProvisionAccountRoleArn` + `DomainId` + `DomainAccountId` to org admin

### Phase 4: ProvisionAccount Lambda

- [ ] 4.1 Update `src/provision-account/lambda_function.py` — accept `poolName` in event payload; read OU ID, account tags, and StackSet list from org SSM (via assumed `AccountCreationRole`); apply tags to the new account via `organizations:TagResource` after creation; deploy StackSets in wave order; return `deployedStackSets` list in response
- [ ] 4.2 Ensure `provision_account()` passes `poolName` back in response so pool manager can store it in DynamoDB

### Phase 5: Pool Manager Lambda

- [ ] 5.1 Update `load_config()` — read all pool names from `/AccountPoolFactory/Pools/` SSM prefix; build a dict of per-pool config (MinimumPoolSize, TargetPoolSize, ReclaimStrategy) keyed by pool name
- [ ] 5.2 Update `check_pool_size_and_replenish()` — iterate over all configured pools independently; each pool gets its own available/setting-up/failed count; replenishment for one pool does not block another
- [ ] 5.2a Update `handle_force_replenishment()` — accept optional `poolName` in payload; if provided, replenish only that pool; if absent, replenish all pools (backward compatible). Required by the Pool Management Console UI which triggers per-pool replenishment.
- [ ] 5.3 Update `create_accounts_parallel()` — pass `poolName` in the ProvisionAccount payload so the Lambda knows which OU and StackSets to use
- [ ] 5.4 Update `create_account_record()` — store `poolName` in DynamoDB; `deployedStackSets` is populated from the ProvisionAccount response
- [ ] 5.5 Update `count_accounts_by_state()` — add optional `poolName` filter; when called per-pool, query DynamoDB with both `state` and `poolName` conditions (use `PoolIndex` GSI or filter expression)
- [ ] 5.6 Update reclaim logic (`reclaim_account_delete`, `reclaim_account_reuse`) — read `ReclaimStrategy` from the account's pool config, not a single global SSM param
- [ ] 5.7 Add `PoolIndex` GSI to DynamoDB table in `01-infrastructure.yaml`:
  - Add `poolName` to `AttributeDefinitions` (Type: S) — required before GSI can reference it
  - Add GSI: `PoolIndex`, partition key `poolName`, sort key `state`, projection ALL
  - This enables efficient per-pool state queries without full scans and is required by the Pool Management Console UI

### Phase 6: Setup Orchestrator Lambda

- [ ] 6.1 Update wave execution — read `deployedStackSets` from the account's DynamoDB record (written by ProvisionAccount); group by `wave` number; deploy each wave in parallel, waves in ascending order; no hardcoded stack list
- [ ] 6.2 Update idempotency check — compare existing CF stacks in the account against `deployedStackSets` list; skip stacks that already exist and are healthy
- [ ] 6.3 Update `updateBlueprints` mode — only update the blueprints stack entry from `deployedStackSets`, leave others untouched

### Phase 7: Account Provider Lambda

- [ ] 7.1 Update `list_authorized_accounts` — DataZone passes a context that includes the project profile name; map project profile name → pool name (read mapping from SSM `/AccountPoolFactory/Pools/{name}/ProjectProfileName`); query DynamoDB for AVAILABLE accounts filtered by that `poolName`
- [ ] 7.2 Update `validate_account_authorization` — verify the account's `poolName` matches the pool associated with the requesting project profile
- [ ] 7.3 If no pool mapping found for a project profile, fall back to returning accounts from any pool (backward-compatible default)
- [ ] 7.4 Write `/AccountPoolFactory/Pools/{name}/ProjectProfileName` SSM param in domain deploy script (`02-domain-account/scripts/deploy/01-deploy.sh`) — value comes from `02-domain-account/config.yaml` `pools[].project_profile_name`; read by both AccountProvider Lambda and the UI's ProjectsApiLambda to filter pool-backed profiles
### Phase 8: DeprovisionAccount Lambda

- [ ] 8.1 Update stack categorization — read `deployedStackSets` from the account's DynamoDB record; treat those StackSet-deployed stacks as "approved infrastructure" (never delete); delete everything else (DataZone project stacks)
- [ ] 8.2 Remove hardcoded `AccountPoolFactory-*` / `StackSet-*` pattern matching — replace with the per-account `deployedStackSets` list

### Phase 9: Account Reconciler Lambda

- [ ] 9.1 Update OU scanning — iterate over all pools' OUIds (read from org SSM via `AccountCreationRole`); reconcile each pool's OU independently
- [ ] 9.2 Update AVAILABLE account validation — read `deployedStackSets` from each account's DynamoDB record; validate those specific stacks exist and are healthy in the account (not a global pattern)
- [ ] 9.3 Update ORPHANED record creation — read `PoolName` tag from the org account to assign the correct pool; fall back to the OU it was found in
- [ ] 9.4 Update `autoReplenish` — trigger PoolManager per pool, not globally

### Phase 10: Account Recycler Lambda

- [ ] 10.1 Pass `poolName` through to SetupOrchestrator and DeprovisionAccount invocations so they operate with the correct per-account context
- [ ] 10.2 `updateBlueprints` mode — iterate over AVAILABLE accounts across all pools, update each account's blueprints stack based on its own `deployedStackSets`

### Phase 11: Documentation Updates

- [ ] 8.1 Rewrite `docs/OrgAdminGuide.md`:
  - New deployment order: domain deploys first, org deploys second
  - Document `01-org-account/config.yaml` new format: pools, per-pool email, stacksets as template paths with waves
  - Document S3 template bucket: common vs pool-specific layout, versioning, rollback procedure
  - Document trust policy change: `AccountCreationRole` now trusts specific Lambda role ARN, not entire account
  - Remove "How to Add a New Approved StackSet" manual steps — replaced by dropping a template in S3 + updating `01-org-account/config.yaml`
- [ ] 8.2 Rewrite `docs/DomainAdminGuide.md`:
  - New deployment order: domain deploys first, outputs `ProvisionAccountRoleArn` for org admin
  - Update `02-domain-account/config.yaml` section: per-pool `default_project_owner`, `project_profile_name`, `reclaim_strategy`
  - Remove `setup_stacks` references
  - Update SSM path examples to per-pool namespace
  - Update pool status monitoring commands to filter by pool name
- [ ] 8.3 Update `docs/Architecture.md`:
  - Update deployment sequence diagram: domain → org (reversed)
  - Add multi-pool section with OU-per-pool diagram
  - Update SSM layout section
  - Add S3 template bucket to org admin account resources
- [ ] 8.4 Update `01-org-account/config.yaml.template` and `02-domain-account/config.yaml.template` to final format with inline comments explaining each field

### Phase 12: Cleanup & Redeploy

- [ ] 9.1 Clean up existing pool accounts from DynamoDB:
  ```bash
  eval $(isengardcli credentials amirbo+3@amazon.com)
  # Invoke reconciler in dry-run first to see what exists
  aws lambda invoke --function-name AccountReconciler \
    --payload '{"source":"manual","dryRun":true}' \
    --cli-binary-format raw-in-base64-out --region us-east-2 /tmp/reconcile-dry.json
  cat /tmp/reconcile-dry.json
  ```
- [ ] 9.2 Delete existing StackSet instances from all pool accounts (org admin account):
  ```bash
  eval $(isengardcli credentials amirbo+1@amazon.com)
  ./01-org-account/scripts/cleanup/cleanup.sh
  ```
- [ ] 9.3 Delete existing domain infrastructure stack:
  ```bash
  eval $(isengardcli credentials amirbo+3@amazon.com)
  ./02-domain-account/scripts/cleanup/cleanup.sh
  ```
- [ ] 9.4 Delete existing org admin stack:
  ```bash
  eval $(isengardcli credentials amirbo+1@amazon.com)
  aws cloudformation delete-stack --stack-name AccountPoolFactory-OrgAdmin --region us-east-2
  aws cloudformation wait stack-delete-complete --stack-name AccountPoolFactory-OrgAdmin --region us-east-2
  ```
- [ ] 9.5 Redeploy domain account first (new order):
  ```bash
  eval $(isengardcli credentials amirbo+3@amazon.com)
  ./02-domain-account/scripts/deploy/01-deploy.sh
  # Note the ProvisionAccountRoleArn from stack outputs — needed for org deploy
  ```
- [ ] 9.6 Redeploy org admin account with `ProvisionAccountRoleArn`:
  ```bash
  eval $(isengardcli credentials amirbo+1@amazon.com)
  ./01-org-account/scripts/deploy/01-deploy.sh <domain-account-id> <domain-id> <provision-account-role-arn>
  ```
- [ ] 9.7 Verify org admin deployment:
  ```bash
  ./01-org-account/scripts/deploy/02-verify.sh
  ```
- [ ] 9.8 Deploy project profile:
  ```bash
  eval $(isengardcli credentials amirbo+3@amazon.com)
  ./02-domain-account/scripts/deploy/02-deploy-project-profile.sh
  ./02-domain-account/scripts/deploy/03-verify.sh
  ```

### Phase 13: Testing

- [ ] 13.1 Seed the pool — trigger initial replenishment and verify accounts reach AVAILABLE state:
  ```bash
  eval $(isengardcli credentials amirbo+3@amazon.com)
  aws lambda invoke --function-name PoolManager \
    --payload '{"action":"force_replenishment"}' \
    --cli-binary-format raw-in-base64-out --region us-east-2 /tmp/replenish.json
  # Monitor until accounts are AVAILABLE
  ./02-domain-account/scripts/utils/check-pool-status.sh
  ```
- [ ] 13.2 Verify accounts landed in the correct OU (org admin account):
  ```bash
  eval $(isengardcli credentials amirbo+1@amazon.com)
  aws organizations list-accounts-for-parent --parent-id <ou-id> --region us-east-2
  ```
- [ ] 13.3 Verify correct StackSets were deployed into pool accounts — check that only the templates declared for the pool are present, no extras:
  ```bash
  eval $(isengardcli credentials amirbo+3@amazon.com)
  # Check a AVAILABLE account's DynamoDB record for deployedStackSets
  ./02-domain-account/scripts/utils/check-account-state.sh <account-id>
  ```
- [ ] 13.4 Run reconciler and verify it validates correctly against per-account `deployedStackSets`:
  ```bash
  aws lambda invoke --function-name AccountReconciler \
    --payload '{"source":"manual","dryRun":false,"autoRecycle":false}' \
    --cli-binary-format raw-in-base64-out --region us-east-2 /tmp/reconcile.json
  cat /tmp/reconcile.json
  ```
- [ ] 13.5 Create a test project and verify account assignment works end-to-end
- [ ] 13.6 Delete the test project and verify reclaim strategy executes correctly
- [ ] 13.7 Verify pool replenishes automatically after assignment
- [ ] 13.8 Security test — verify domain Lambda cannot deploy a StackSet with an arbitrary template body:
  ```bash
  # Attempt to invoke ProvisionAccount with a tampered templateUrl pointing outside the org bucket
  # Should be denied by IAM condition
  ```

---

## Open Questions / Decisions Needed

- **Q1**: Should the `DomainAccess` StackSet always be implicitly first (enforced by code), or should the org admin always list it explicitly? Explicit is more transparent; implicit is safer.
- **Q2**: When a pool is removed from `01-org-account/config.yaml` and the deploy script re-runs, should existing accounts in that pool be left alone or flagged? Suggest: leave alone, reconciler will flag them as ORPHANED.
- **Q3**: The `StateIndex` GSI currently has `state` as partition key. For multi-pool, do we need a `PoolIndex` GSI (`poolName` PK, `state` SK) or is filtering in-memory acceptable for small pools? Suggest: add GSI if pools can have 50+ accounts each.
- **Q4**: ~~Should `email_prefix` / `email_domain` be per-pool or global?~~ **Resolved**: moved to `01-org-account/config.yaml` as global org-level settings. The domain admin has no say in account email ownership — that's an org admin concern.
- **Q5**: The `AccountRecycler` currently processes all FAILED/ORPHANED accounts. With multi-pool, should it be pool-aware (process one pool at a time) or continue processing all? Suggest: pool-aware to avoid cross-pool interference.

---

## Notes

- Backward compatibility: existing single-pool deployments should continue to work. The deploy script can detect old-format config and warn/migrate.
- The `SMUS-AccountPoolFactory-*` IAM prefix is the hard security boundary. Org admins who want to add a custom StackSet must name it with this prefix — this is intentional and should be documented.
- Stack name defaults: `SMUS-AccountPoolFactory-DomainAccess`, `SMUS-AccountPoolFactory-VPC`, `SMUS-AccountPoolFactory-IAMRoles`, `SMUS-AccountPoolFactory-EventBridge`, `SMUS-AccountPoolFactory-Blueprints`. These match the existing naming convention.

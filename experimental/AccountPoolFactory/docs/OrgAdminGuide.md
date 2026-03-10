# Account Pool Factory - Org Admin Guide

[← Back to README](../README.md) | [Domain Admin Guide](DomainAdminGuide.md) | [Architecture](Architecture.md) | [Security Guide](SecurityGuide.md) | [Testing Guide](TestingGuide.md)

---

Audience: the person who has access to the AWS Organizations management account.

**Deployment order**: Domain admin deploys first, then hands you `ProvisionAccountRoleArn`. You deploy second.

---

## Prerequisites

- Access to the AWS Organizations management account
- CloudFormation, IAM, S3, SSM, and StackSet permissions
- Domain admin has already deployed their infrastructure and given you `ProvisionAccountRoleArn`
- `org-config.yaml` filled in (copy from `org-config.yaml.template`):

```yaml
region: us-east-2
stackset_prefix: "SMUS-AccountPoolFactory"

pools:
  - name: default
    ou_name: "YourOU/SubOU"        # human-readable path — ID resolved automatically
    email_prefix: "accountpool"
    email_domain: "example.com"
    account_tags:
      CostCenter: "your-cost-center"
    stacksets:
      - template: 01-domain-access.yaml        # REQUIRED first — always wave 1
        wave: 1

      - template: 02-vpc-setup.yaml
        wave: 2
      - template: 03-iam-roles.yaml
        wave: 2
      - template: 04-eventbridge-rules.yaml
        wave: 2
      - template: 05-project-role.yaml        # optional — remove if not needed
        wave: 2

      - template: 06-blueprint-enablement.yaml  # MUST be after IAM roles (wave 2)
        wave: 3
```

---

## Deployment

```bash
# Switch to Org Admin account credentials
./scripts/01-org-mgmt-account/deploy/01-deploy.sh \
  <domain-account-id> \
  <domain-id> \
  <provision-account-role-arn>
```

Example:
```bash
./scripts/01-org-mgmt-account/deploy/01-deploy.sh \
  <domain-account-id> \
  <domain-id> \
  arn:aws:iam::<domain-account-id>:role/SMUS-AccountPoolFactory-ProvisionAccount-Role
```

The script:
1. Deploys the CF stack (IAM roles + S3 bucket)
2. Uploads StackSet templates to S3
3. Writes per-pool SSM parameters (OU ID, email, account tags, StackSet list with S3 URLs)
4. Creates/updates StackSet definitions pointing at S3 templates

Verify:
```bash
./scripts/01-org-mgmt-account/deploy/02-verify.sh
```

---

## Uninstall

```bash
# Switch to Org Admin account credentials
./scripts/01-org-mgmt-account/cleanup/cleanup.sh
```

This deletes StackSet instances from all pool accounts, then deletes the StackSet definitions and the CF stack.

---

## Adding a New Pool

1. Add a new entry to `pools:` in `org-config.yaml`
2. Re-run the deploy script — no CF stack changes needed
3. The deploy script writes new SSM params and creates new StackSet definitions

---

## Adding a New StackSet Template

1. Add the template file to `templates/cloudformation/stacksets/idc/` (IDC domains, active) or `templates/cloudformation/stacksets/iam/` (IAM domains, parked)
2. Add an entry to the pool's `stacksets:` list in `org-config.yaml`
3. Re-run the deploy script — it uploads all templates from `stacksets/idc/` to S3 and creates/updates StackSet definitions automatically

The `AccountCreationRole` IAM condition (`EnforceS3TemplateSource`) ensures StackSets can only be created/updated using templates from the org S3 bucket. The domain account cannot supply arbitrary template bodies.

---

## What This Installs

One CloudFormation stack (`AccountPoolFactory-OrgAdmin`) containing:

| Resource | Purpose |
|----------|---------|
| `SMUS-AccountPoolFactory-AccountCreation` IAM role | Trusted by the domain account's ProvisionAccount Lambda to call Organizations, StackSet, and SSM APIs. Trust is scoped to the specific ProvisionAccount Lambda execution role ARN — not the entire domain account. |
| `SMUS-AccountPoolFactory-StackSetAdmin` IAM role | Trusted by the CloudFormation service to deploy StackSet instances into project accounts |
| `accountpoolfactory-templates-{account-id}` S3 bucket | Stores approved StackSet templates. Versioned. Domain account has no direct access — templates are only reachable via the assumed AccountCreation role. |
| Per-pool SSM parameters | OU ID, email settings, account tags, StackSet list per pool — read by ProvisionAccount Lambda at runtime |
| StackSet definitions | One per template in `org-config.yaml` pools[].stacksets — created/updated by the deploy script |

No Lambdas, no application code, no DynamoDB — just IAM, S3, SSM, and StackSet definitions.

---

## org-config.yaml Reference

The file has three top-level sections:

`region` — AWS region for the CF stack, StackSet control plane, S3 template bucket, and where StackSet instances are deployed into project accounts. Must match the domain account's region.

`stackset_prefix` — naming prefix for all StackSet definitions. The deploy script derives StackSet names as `{prefix}-{TitleCasedTemplateStem}` (e.g. `SMUS-AccountPoolFactory-VpcSetup`). This prefix is baked into IAM policy conditions — don't change it after initial deploy.

`pools[]` — one entry per logical pool:

| Field | Purpose |
|-------|---------|
| `name` | Logical pool name, referenced by `domain-config.yaml` |
| `ou_name` | Human-readable OU path (e.g. `RetailBanking/CustomerAnalytics`) — resolved to OU ID automatically |
| `ou_id` | Optional override to skip the OU name lookup |
| `email_prefix` / `email_domain` | Root email pattern for new accounts: `{prefix}+{uid}@{domain}` |
| `account_tags` | Tags applied to every account created in this pool. `ManagedBy: AccountPoolFactory` is always added automatically. |
| `stacksets[]` | Ordered list of approved StackSet templates to deploy into each project account, with wave assignments |

**Wave semantics**: templates in the same wave deploy in parallel; waves execute in ascending order. `domain-access.yaml` must always be wave 1 — all other stacks depend on the cross-account role it creates.

---

## Approved StackSet Templates

These templates live in `templates/cloudformation/stacksets/idc/` (uploaded to S3 by the org admin deploy script) and are deployed into every project account by the SetupOrchestrator:

| Template | StackSet Name | Wave | What it deploys |
|----------|--------------|:----:|-----------------|
| `01-domain-access.yaml` | `SMUS-AccountPoolFactory-DomainAccess` | 1 | `SMUS-AccountPoolFactory-DomainAccess` IAM role with ExternalId protection — allows the domain account's SetupOrchestrator to assume into this account. Required before anything else. |
| `02-vpc-setup.yaml` | `SMUS-AccountPoolFactory-VpcSetup` | 2 | VPC (`10.0.0.0/16`) with 3 private subnets across 3 AZs and a shared route table. Exports VPC ID and subnet IDs consumed by the blueprints stack. |
| `03-iam-roles.yaml` | `SMUS-AccountPoolFactory-IamRoles` | 2 | `DataZoneManageAccessRole` (Glue/LakeFormation access management) and `DataZoneProvisioningRole` (environment provisioning). Both trust the DataZone service scoped to the domain account. |
| `04-eventbridge-rules.yaml` | `SMUS-AccountPoolFactory-EventbridgeRules` | 2 | EventBridge rule that forwards all `DataZone-*` CloudFormation stack status change events to the domain account's central event bus. This is how PoolManager detects project assignment and deletion. |
| `05-project-role.yaml` | `SMUS-AccountPoolFactory-ProjectRole` | 2 | `AmazonSageMakerProjectRole` — execution role assumed by SageMaker, DataZone, Glue, Bedrock, and other services when running project workloads. Uses `SageMakerStudioAdminIAMPermissiveExecutionPolicy`. Optional — remove from `stacksets` if not needed. |

IAM-domain-only templates live in `templates/cloudformation/stacksets/iam/` and are not currently used.

The deploy script reads the `TemplateVersion` output from each deployed stack — bumping that value in a template forces SetupOrchestrator to update already-deployed stacks on the next reconcile cycle.

---

## Security Model

- `AccountCreationRole` trusts only `LambdaExecutionRole` from the domain account (single principal, scoped with ExternalId)
- StackSet create/update is denied unless `TemplateURL` points to `s3://{org-bucket}/stacksets/*`
- Domain account has no `s3:GetObject` on the org bucket — templates are only reachable via the assumed role

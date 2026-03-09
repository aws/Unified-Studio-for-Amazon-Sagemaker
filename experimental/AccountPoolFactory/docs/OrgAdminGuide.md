# Account Pool Factory - Org Admin Guide

Audience: the person who has access to the AWS Organizations management account.

**Deployment order**: Domain admin deploys first, then hands you `ProvisionAccountRoleArn`. You deploy second.

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
      - template: domain-access.yaml
        wave: 1
```

---

## Deployment

```bash
eval $(isengardcli credentials amirbo+1@amazon.com)
./scripts/01-org-mgmt-account/deploy/01-deploy.sh \
  <domain-account-id> \
  <domain-id> \
  <provision-account-role-arn>
```

Example:
```bash
./scripts/01-org-mgmt-account/deploy/01-deploy.sh \
  994753223772 \
  dzd-4h7jbz76qckoh5 \
  arn:aws:iam::994753223772:role/SMUS-AccountPoolFactory-ProvisionAccount-Role
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

## Adding a New Pool

1. Add a new entry to `pools:` in `org-config.yaml`
2. Re-run the deploy script — no CF stack changes needed
3. The deploy script writes new SSM params and creates new StackSet definitions

---

## Adding a New StackSet Template

1. Add the template file to `templates/cloudformation/03-project-account/deploy/` (common) or `templates/cloudformation/03-project-account/deploy/pools/{pool-name}/` (pool-specific)
2. Add an entry to the pool's `stacksets:` list in `org-config.yaml`
3. Re-run the deploy script — it uploads the template to S3 and creates the StackSet definition

The `AccountCreationRole` IAM condition (`EnforceS3TemplateSource`) ensures StackSets can only be created/updated using templates from the org S3 bucket. The domain account cannot supply arbitrary template bodies.

---

## Security Model

- `AccountCreationRole` trusts only the specific `ProvisionAccountRoleArn` (not the entire domain account root)
- `AccountCreationRole` + `LambdaExecutionRole` (for Reconciler read-only org access) are the only principals that can assume the role
- StackSet create/update is denied unless `TemplateURL` points to `s3://{org-bucket}/stacksets/*`
- Domain account has no `s3:GetObject` on the org bucket — templates are only reachable via the assumed role

---

## How to Uninstall

```bash
eval $(isengardcli credentials amirbo+1@amazon.com)
./scripts/01-org-mgmt-account/cleanup/cleanup.sh
```

This deletes StackSet instances from all pool accounts, then deletes the StackSet definitions and the CF stack.

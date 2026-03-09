# Account Pool Factory - Org Admin Guide

Audience: the person who has access to the AWS Organizations management account.

You only need to do this once. After deploying, hand the outputs to the domain admin and you're done.

---

## What This Installs

One CloudFormation stack (`AccountPoolFactory-OrgAdmin`) containing:

| Resource | Purpose |
|----------|---------|
| `SMUS-AccountPoolFactory-AccountCreation` IAM role | Trusted by the domain account's ProvisionAccount Lambda to call Organizations and StackSet APIs |
| `SMUS-AccountPoolFactory-StackSetAdmin` IAM role | Trusted by the CloudFormation service to deploy StackSet instances into project accounts |
| `SMUS-AccountPoolFactory-DomainAccess` StackSet | Deploys a role into each project account that allows the domain account to configure it |

No Lambdas, no application code, no DynamoDB — just IAM roles and a StackSet definition.

---

## Prerequisites

- Access to the AWS Organizations management account
- CloudFormation, IAM, and StackSet permissions
- `org-config.yaml` filled in (copy from `org-config.yaml.template`):
  ```yaml
  region: us-east-2
  target_ou_name: "YourOU/SubOU"   # human-readable OU path — ID resolved automatically
  ```

---

## Deployment

You need the domain account ID and domain ID as one-time arguments (the domain admin provides these):

```bash
eval $(isengardcli credentials amirbo+1@amazon.com)
./scripts/01-org-mgmt-account/deploy/deploy-org-admin.sh <domain-account-id> <domain-id>
```

Example:
```bash
./scripts/01-org-mgmt-account/deploy/deploy-org-admin.sh 994753223772 dzd-4h7jbz76qckoh5
```

The script deploys the CF stack and prints the outputs. The domain admin's `deploy-infrastructure.sh` reads these automatically from the `AccountPoolFactory-OrgAdmin` stack — no manual copy needed.

---

## What Permissions Are Granted

### AccountCreation role (trusted by domain account)

The domain account's ProvisionAccount Lambda assumes this role to:

- Create AWS accounts via Organizations API
- Move accounts to the target OU
- Deploy the DomainAccess StackSet into new accounts
- Assume `OrganizationAccountAccessRole` in new accounts to bootstrap the StackSet execution role

Permissions are scoped to `SMUS-AccountPoolFactory-*` StackSets only — it cannot manage unrelated StackSets.

### StackSetAdmin role (trusted by CloudFormation service)

Used internally by CloudFormation to deploy StackSet instances. It can only assume `SMUS-AccountPoolFactory-StackSetExecution` roles in project accounts.

---

## How to Add a New Approved StackSet

The `Metadata.ApprovedStackSets` section in `SMUS-AccountPoolFactory-OrgAdmin.yaml` documents all StackSets managed by this system. To add a new one:

1. Add an entry to `Metadata.ApprovedStackSets` (documentation only)
2. Add the StackSet create/update logic to `deploy-org-admin.sh` (same pattern as `SMUS-AccountPoolFactory-DomainAccess`)
3. Add the new StackSet name to the `AccountCreationRole` `StackSetAccess` policy in the CF template
4. Run `deploy-org-admin.sh` again

---

## How to Uninstall

1. Delete all StackSet instances first (the StackSet has instances in project accounts):
   ```bash
   eval $(isengardcli credentials amirbo+1@amazon.com)
   # List instances
   aws cloudformation list-stack-instances \
     --stack-set-name SMUS-AccountPoolFactory-DomainAccess \
     --region us-east-2 \
     --query 'Summaries[*].Account' --output text
   # Delete instances (replace ACCOUNT_IDS with space-separated list)
   aws cloudformation delete-stack-instances \
     --stack-set-name SMUS-AccountPoolFactory-DomainAccess \
     --accounts ACCOUNT_IDS \
     --regions us-east-2 \
     --no-retain-stacks \
     --region us-east-2
   ```

2. Delete the StackSet:
   ```bash
   aws cloudformation delete-stack-set \
     --stack-set-name SMUS-AccountPoolFactory-DomainAccess \
     --region us-east-2
   ```

3. Delete the CF stack:
   ```bash
   aws cloudformation delete-stack \
     --stack-name AccountPoolFactory-OrgAdmin \
     --region us-east-2
   ```

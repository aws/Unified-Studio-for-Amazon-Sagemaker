# Account Pool Factory - Security Guide

[← Back to README](../README.md) | [Org Admin Guide](OrgAdminGuide.md) | [Domain Admin Guide](DomainAdminGuide.md) | [Architecture](Architecture.md) | [Testing Guide](TestingGuide.md)

---

## Security Architecture

The Account Pool Factory implements three security controls:

1. **Separation of Duties**: Organizations API access isolated in Org Admin account
2. **Confused Deputy Protection**: ExternalId required for cross-account role assumptions
3. **Simplified IAM**: Single shared execution role for all domain account Lambdas

## Confused Deputy Protection

### The Problem

Without ExternalId, an attacker could trick Pool Manager into provisioning accounts:

```
Attacker → Invokes Pool Manager → Pool Manager assumes role in Org Admin → Creates accounts ✗
```

### The Solution - ExternalId in Trust Policies

Setup Orchestrator uses ExternalId when assuming SMUS-AccountPoolFactory-DomainAccess role in project accounts:

```python
# From setup-orchestrator/lambda_function.py
def get_cross_account_client(service: str, account_id: str, config: Dict[str, Any] = None):
    role_arn = f"arn:aws:iam::{account_id}:role/SMUS-AccountPoolFactory-DomainAccess"
    domain_id = config.get('DomainId', DOMAIN_ID)
    
    assumed_role = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName=f'SetupOrchestrator-{service}',
        ExternalId=domain_id,  # ← ExternalId prevents confused deputy
        DurationSeconds=3600
    )
```

Trust policy in project accounts requires matching ExternalId:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "AWS": "arn:aws:iam::DOMAIN_ACCOUNT:root"
    },
    "Action": "sts:AssumeRole",
    "Condition": {
      "StringEquals": {
        "sts:ExternalId": "DOMAIN_ID"
      }
    }
  }]
}
```

**ExternalId Value**: DataZone Domain ID (stored in environment variable)

**Where ExternalId is Used**:
- Setup Orchestrator → SMUS-AccountPoolFactory-DomainAccess role (project accounts)

**Where ExternalId is NOT Used**:
- ProvisionAccount Lambda → OrganizationAccountAccessRole (same account)
- Pool Manager → ProvisionAccount Lambda (resource-based policy instead)

## IAM Roles by Account

### Organization Admin Account

**AccountCreationRole** (`SMUS-AccountPoolFactory-AccountCreation`)

Assumed cross-account by the domain account's `LambdaExecutionRole`. Protected by ExternalId.

Key permissions:
- `organizations:CreateAccount`, `MoveAccount`, `CloseAccount` — account lifecycle
- `organizations:TagResource`, `ListTagsForResource`, `ListAccountsForParent` — tag-based identification
- `cloudformation:CreateStackInstances`, `UpdateStackInstances` — deploy StackSets to project accounts
- `ssm:GetParameter` — read pool config from org admin SSM

Trust policy: single principal — `LambdaExecutionRole` ARN from the domain account, scoped with ExternalId.

### Domain Account

**LambdaExecutionRole** (`SMUS-AccountPoolFactory-LambdaExecution-Role`)

Single shared execution role for all AccountPoolFactory Lambdas (PoolManager, SetupOrchestrator, ProvisionAccount, DeprovisionAccount, AccountReconciler, AccountRecycler, AccountProvider).

Key permissions:
- `dynamodb:Query|PutItem|UpdateItem|DeleteItem|GetItem` — account state table
- `lambda:InvokeFunction` — invoke sibling Lambdas within the domain account
- `sts:AssumeRole` on `AccountCreationRole` (org admin), `DomainAccess` (project accounts), `OrganizationAccountAccessRole` (new accounts)
- `ssm:GetParameter*` — read pool and orchestrator config
- `ram:*` — domain sharing
- `datazone:*` — domain operations
- `sns:Publish`, `cloudwatch:PutMetricData` — observability

Why one role: all Lambdas run in the same account and trust boundary. Separate roles per Lambda provide no meaningful security isolation — a compromised Lambda can invoke any other Lambda in the account regardless of its execution role.

**AccountResolutionRole** (`SMUS-AccountPoolFactory-AccountResolution-Role`)

Separate role trusted by `datazone.amazonaws.com` only. Allows DataZone to invoke the AccountProvider Lambda. Not used by any of our own Lambdas.

### Project Account

**SMUS-AccountPoolFactory-DomainAccess Role**

Created by ProvisionAccount Lambda via StackSet during provisioning.

Trust policy with ExternalId:
```json
{
  "Principal": {
    "AWS": "arn:aws:iam::DOMAIN_ACCOUNT:root"
  },
  "Action": "sts:AssumeRole",
  "Condition": {
    "StringEquals": {
      "sts:ExternalId": "DOMAIN_ID"
    }
  }
}
```

Key permissions:
- `cloudformation:CreateStack|DescribeStacks|DeleteStack` — deploy DataZone stacks
- `datazone:*` — configure DataZone domain access
- `ec2:*` — create VPC for DataZone environments
- `s3:CreateBucket` — create blueprint artifact bucket
- `ram:CreateResourceShare` — share domain with project account
- `iam:CreateRole|PassRole` — create DataZone service roles

Why ExternalId: prevents confused deputy — SetupOrchestrator must supply the correct DataZone Domain ID to assume this role.

## Related Documentation

- [Architecture Guide](Architecture.md) - System architecture and component interactions

## Tag-Based Account Identification

Pool accounts are identified using a two-tier approach:

1. **Primary**: AWS Organizations tags `ManagedBy: AccountPoolFactory` + `PoolName: {pool name}`
2. **Fallback**: Account name prefix matching (for legacy accounts created before tagging was added)

The ProvisionAccount Lambda tags new accounts immediately after creation. The AccountReconciler backfills tags on legacy accounts identified by name prefix only, ensuring all pool accounts converge to tag-based identification over time.

Multi-pool isolation: each Reconciler instance only processes accounts with a matching `PoolName` tag. Accounts tagged with a different `PoolName` are skipped even if they have the `ManagedBy` tag.

## Updated IAM Roles

### AccountCreationRole Trust (Org Admin Account)

Single trust statement — `LambdaExecutionRole` from the domain account with ExternalId. All domain account Lambdas share this role, so all cross-account org operations flow through one trusted principal.

Permissions include:
- `organizations:ListTagsForResource`, `TagResource`, `ListAccountsForParent` — tag-based account identification
- `organizations:CreateAccount`, `MoveAccount`, `CloseAccount` — account lifecycle
- CloudFormation StackSet create/update/delete — scoped to `s3://{org-bucket}/stacksets/*` templates only

## Org-Wide RAM Share

Instead of per-account RAM shares (which caused resource policy bloat), the system uses a single org-wide RAM share in the domain account:

- **Principal**: OU ARN — all accounts in the target OU automatically receive domain access
- **No per-account shares**: SetupOrchestrator no longer creates RAM shares; it only verifies domain visibility
- **Single point of management**: One share to monitor, one share to audit

The org-wide share was enabled via `enable_sharing_with_aws_organization` from the Org Admin account.

## Blueprint Policy Grants via CloudFormation

`AWS::DataZone::PolicyGrant` resources for `ENVIRONMENT_BLUEPRINT_CONFIGURATION` entity type cannot be created by the Admin IAM role directly — DataZone requires the caller to be a domain owner identity. These grants must be deployed via CloudFormation, which uses the domain's service role internally.

The `blueprint-enablement-iam.yaml` template includes 17 `PolicyGrant` resources (one per blueprint). Each grant:
- `EntityType: ENVIRONMENT_BLUEPRINT_CONFIGURATION`
- `EntityIdentifier: {AWS::AccountId}:{BlueprintId}` — auto-resolves to the project account
- `PolicyType: CREATE_ENVIRONMENT_FROM_BLUEPRINT`
- `Principal: CONTRIBUTOR projects in root domain unit, IncludeChildDomainUnits: true`

This means grants are automatically applied when SetupOrchestrator deploys the blueprint stack — no separate grant step per account.

## CREATE_PROJECT_FROM_PROJECT_PROFILE Grant

The domain unit grant allowing users to create projects from the "All Capabilities - Account Pool" profile is managed via the `tests/setup/deploy-policy-grants-cf.sh` script. This calls `AddPolicyGrant` directly via the Admin role (which IS permitted for `DOMAIN_UNIT` entity type, unlike `ENVIRONMENT_BLUEPRINT_CONFIGURATION`).

This is a one-time domain-level grant — not per-account.

# Account Pool Factory - Security Guide

## Security Architecture

The Account Pool Factory implements three security controls:

1. **Separation of Duties**: Organizations API access isolated in Org Admin account
2. **Confused Deputy Protection**: ExternalId required for cross-account role assumptions
3. **Least Privilege**: Each Lambda has minimum permissions for its function

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

**ProvisionAccount Lambda Role**

Why: Only Lambda with Organizations API access. Isolated to prevent Setup Orchestrator from creating accounts.

Key permissions:
- `organizations:CreateAccount` - Create new AWS accounts
- `organizations:MoveAccount` - Move accounts to target OU
- `sts:AssumeRole` - Assume OrganizationAccountAccessRole in new accounts
- `cloudformation:CreateStackInstances` - Deploy StackSets to new accounts

Invocation control:
```json
{
  "Principal": {
    "AWS": "arn:aws:iam::DOMAIN_ACCOUNT:role/SMUS-AccountPoolFactory-PoolManager-Role"
  },
  "Action": "lambda:InvokeFunction"
}
```

Why no ExternalId: Lambda runs in same account as Organizations API, no cross-account risk.

### Domain Account

**Pool Manager Lambda Role**

Why: Orchestrates pool operations, delegates account creation to ProvisionAccount.

Key permissions:
- `lambda:InvokeFunction` - Invoke ProvisionAccount and SetupOrchestrator
- `dynamodb:Query|PutItem|UpdateItem|DeleteItem` - Manage account state
- `sts:AssumeRole` - Assume OrganizationAccountAccessRole for stack verification only

Why no Organizations API: Delegates to ProvisionAccount Lambda for separation of duties.

**Setup Orchestrator Lambda Role**

Why: Configures project accounts with DataZone resources.

Key permissions:
- `sts:AssumeRole` - Assume SMUS-AccountPoolFactory-DomainAccess with ExternalId
- `dynamodb:Query|PutItem|UpdateItem` - Track setup progress

Why ExternalId required: All project account operations go through SMUS-AccountPoolFactory-DomainAccess role.

**Account Provider Lambda Role**

Why: Returns available accounts to SMUS API.

Key permissions:
- `dynamodb:Query` - Read-only access to account state

Why most restrictive: No cross-account access, no write operations.

### Project Account

**SMUS-AccountPoolFactory-DomainAccess Role**

Created by: ProvisionAccount Lambda via StackSet during provisioning.

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
- `cloudformation:CreateStack|DescribeStacks|DeleteStack` - Deploy DataZone stacks
- `datazone:*` - Configure DataZone domain access
- `ec2:*` - Create VPC for DataZone environments
- `s3:CreateBucket` - Create blueprint artifact bucket
- `ram:CreateResourceShare` - Share domain with project account
- `iam:CreateRole|PassRole` - Create DataZone service roles

Why ExternalId: Prevents confused deputy - Setup Orchestrator must know secret ExternalId to assume role.

## Related Documentation

- [Architecture Guide](Architecture.md) - System architecture and component interactions

## Tag-Based Account Identification

Pool accounts are identified using a two-tier approach:

1. **Primary**: AWS Organizations tags `ManagedBy: AccountPoolFactory` + `PoolName: {pool name}`
2. **Fallback**: Account name prefix matching (for legacy accounts created before tagging was added)

The ProvisionAccount Lambda tags new accounts immediately after creation. The AccountReconciler backfills tags on legacy accounts identified by name prefix only, ensuring all pool accounts converge to tag-based identification over time.

Multi-pool isolation: each Reconciler instance only processes accounts with a matching `PoolName` tag. Accounts tagged with a different `PoolName` are skipped even if they have the `ManagedBy` tag.

## Updated IAM Roles

### AccountCreationRole Trust Update (Org Admin Account)

The existing `SMUS-AccountPoolFactory-AccountCreation` role trust policy was updated to allow the AccountReconciler Lambda role as an additional trusted principal (alongside the existing Pool Manager role). No new role was created in the Org Admin account.

Additional permissions added:
- `organizations:ListTagsForResource` — read tags on org accounts
- `organizations:TagResource` — backfill tags on legacy accounts
- `organizations:ListAccountsForParent` — OU-scoped account listing

### ProvisionAccountRole Update (Org Admin Account)

Additional permissions added:
- `organizations:TagResource` — tag newly created accounts
- `organizations:ListTagsForResource` — verify tags

### AccountReconcilerRole (Domain Account)

New role: `SMUS-AccountPoolFactory-AccountReconciler-Role`

Permissions:
- DynamoDB: Query, PutItem, UpdateItem, GetItem on AccountState table + indexes
- STS: AssumeRole on `SMUS-AccountPoolFactory-AccountCreation` (Org Admin) and `SMUS-AccountPoolFactory-DomainAccess` (project accounts)
- SSM: GetParameter on `/AccountPoolFactory/PoolManager/*`
- CloudWatch: PutMetricData
- SNS: Publish to AlertTopic
- Lambda: InvokeFunction on AccountRecycler and PoolManager

### AccountRecyclerRole (Domain Account)

New role: `SMUS-AccountPoolFactory-AccountRecycler-Role`

Permissions:
- DynamoDB: Query, PutItem, UpdateItem, GetItem on AccountState table + indexes
- Lambda: InvokeFunction on DeprovisionAccount, SetupOrchestrator, ProvisionAccount (cross-account)
- STS: AssumeRole on `SMUS-AccountPoolFactory-DomainAccess` (project accounts)
- SSM: GetParameter on `/AccountPoolFactory/PoolManager/*`
- CloudWatch: PutMetricData
- SNS: Publish to AlertTopic

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

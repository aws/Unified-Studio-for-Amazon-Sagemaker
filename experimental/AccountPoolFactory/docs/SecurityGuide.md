# Account Pool Factory - Security Guide

[← Back to Index](README.md) | [Getting Started](GettingStarted.md) | [Org Admin Guide](OrgAdminGuide.md) | [Domain Admin Guide](DomainAdminGuide.md) | [Architecture](Architecture.md) | [Testing Guide](TestingGuide.md) | [Test Setup Guide](TestSetupGuide.md) | [Project Structure](ProjectStructure.md)

---

## Multi-Account Security Architecture

Every cross-account action flows through an explicit role assumption chain. Arrows point from the assuming role to the assumed role.

```
DOMAIN ACCOUNT
─────────────────────────────────────────────────────────────────────────────
LambdaExecutionRole
  │
  ├──[1]──► SMUS-AccountPoolFactory-AccountCreation  (ORG ADMIN ACCOUNT)
  │           ExternalId: "AccountPoolFactory-<domain-account-id>"
  │           Used by: ProvisionAccount Lambda, AccountReconciler Lambda
  │
  ├──[2]──► SMUS-AccountPoolFactory-DomainAccess  (PROJECT ACCOUNT)
  │           ExternalId: "<datazone-domain-id>"
  │           Used by: SetupOrchestrator Lambda, DeprovisionAccount Lambda
  │
  └──[3]──► OrganizationAccountAccessRole  (NEW PROJECT ACCOUNT)
              No ExternalId — bootstrap only, before DomainAccess role exists
              Used by: ProvisionAccount Lambda (one-time per account)

ORG ADMIN ACCOUNT
─────────────────────────────────────────────────────────────────────────────
SMUS-AccountPoolFactory-AccountCreation
  │
  └──[4]──► OrganizationAccountAccessRole  (NEW PROJECT ACCOUNT)
              Deploys StackSetExecution role via CloudFormation

SMUS-AccountPoolFactory-StackSetAdmin
  │
  └──[5]──► SMUS-AccountPoolFactory-StackSetExecution  (PROJECT ACCOUNT)
              Assumed by CloudFormation service (not a Lambda)
              Deploys all StackSet instances into project accounts

AWS SERVICES
─────────────────────────────────────────────────────────────────────────────
datazone.amazonaws.com
  │
  ├──[6]──► SMUS-AccountPoolFactory-AccountResolution-Role  (DOMAIN ACCOUNT)
  │           Invokes AccountProvider Lambda
  │
  ├──[7]──► DataZoneManageAccessRole  (PROJECT ACCOUNT)
  │           SourceAccount + SourceArn conditions
  │           Glue/LakeFormation access management
  │
  └──[8]──► DataZoneProvisioningRole  (PROJECT ACCOUNT)
              SourceAccount + SourceArn conditions
              Environment provisioning

sagemaker.amazonaws.com + 9 other services
  │
  └──[9]──► AmazonSageMakerProjectRole  (PROJECT ACCOUNT)
              SourceAccount condition
              Project workload execution
```

Each numbered assumption is described in detail below.

---

## [1] LambdaExecutionRole → AccountCreation (Org Admin)

**When**: ProvisionAccount Lambda creates a new account. AccountReconciler scans the org OU.

**Assumed role** (`SMUS-AccountPoolFactory-AccountCreation` in org admin account)

Trust policy — scoped to the exact Lambda execution role ARN, not the account root:
```json
{
  "Principal": {
    "AWS": "arn:aws:iam::<domain-account-id>:role/SMUS-AccountPoolFactory-LambdaExecution-Role"
  },
  "Action": "sts:AssumeRole",
  "Condition": {
    "StringEquals": {
      "sts:ExternalId": "AccountPoolFactory-<domain-account-id>"
    }
  }
}
```

ExternalId format `AccountPoolFactory-{DomainAccountId}` prevents confused-deputy: an attacker who can invoke a domain Lambda cannot trigger account creation without knowing the ExternalId.

Permissions of the assumed role:

| Scope | Actions | Resource |
|-------|---------|----------|
| Organizations | `CreateAccount`, `DescribeCreateAccountStatus`, `DescribeAccount`, `ListParents`, `MoveAccount`, `CloseAccount`, `DescribeOrganization`, `ListRoots`, `ListOrganizationalUnitsForParent`, `ListAccountsForParent`, `ListAccounts`, `TagResource`, `ListTagsForResource` | `*` (Organizations API requires it) |
| CloudFormation StackSets | `CreateStackSet`, `UpdateStackSet`, `CreateStackInstances`, `DescribeStackSet`, `DescribeStackSetOperation`, `ListStackInstances`, `DescribeStackInstance`, `ListStackSetOperations` | `arn:aws:cloudformation:*:*:stackset/SMUS-AccountPoolFactory-*:*` |
| S3 | `s3:GetObject` | `accountpoolfactory-templates-{org-account-id}/stacksets/*` |
| SSM | `GetParameter`, `GetParameters`, `GetParametersByPath` | `/AccountPoolFactory/*` |
| STS | `AssumeRole` | `arn:aws:iam::*:role/OrganizationAccountAccessRole` (bootstrap only, see [4]) |

Template injection protection — explicit Deny on `CreateStackSet`/`UpdateStackSet` unless `TemplateUrl` points to the org-owned S3 bucket:
```json
{
  "Effect": "Deny",
  "Action": ["cloudformation:CreateStackSet", "cloudformation:UpdateStackSet"],
  "Resource": "arn:aws:cloudformation:*:*:stackset/SMUS-AccountPoolFactory-*:*",
  "Condition": {
    "StringNotLike": {
      "cloudformation:TemplateUrl": [
        "https://s3.*.amazonaws.com/accountpoolfactory-templates-<org-account-id>/stacksets/*",
        "https://accountpoolfactory-templates-<org-account-id>.s3.*.amazonaws.com/stacksets/*"
      ]
    }
  }
}
```

Even a compromised domain Lambda cannot inject arbitrary CloudFormation templates — it can only use pre-approved templates uploaded by the org admin.

---

## [2] LambdaExecutionRole → DomainAccess (Project Account)

**When**: SetupOrchestrator configures a new pool account (VPC, IAM, blueprints). DeprovisionAccount cleans a recycled account.

**Assumed role** (`SMUS-AccountPoolFactory-DomainAccess` in each project account, deployed by StackSet wave 1)

Trust policy:
```json
{
  "Principal": {
    "AWS": "arn:aws:iam::<domain-account-id>:root"
  },
  "Action": "sts:AssumeRole",
  "Condition": {
    "StringEquals": {
      "sts:ExternalId": "<datazone-domain-id>"
    }
  }
}
```

ExternalId = DataZone Domain ID (e.g. `dzd-4h7jbz76qckoh5`). SetupOrchestrator reads this from its environment variable and passes it on every `assume_role` call. An attacker who can invoke SetupOrchestrator but doesn't know the Domain ID cannot assume this role in any project account.

The principal is `<domain-account-id>:root` (not a specific role ARN) because the ExternalId already provides the necessary scoping — any principal in the domain account must still supply the correct ExternalId.

Permissions: `AdministratorAccess` (AWS managed policy), `MaxSessionDuration: 3600`.

AdministratorAccess is intentional — SetupOrchestrator needs to create VPCs, IAM roles, S3 buckets, EventBridge rules, and DataZone blueprint configurations. Scoping to individual services would require a large custom policy that changes as DataZone adds new resource types. The ExternalId and 1-hour session limit are the primary controls.

---

## [3] LambdaExecutionRole → OrganizationAccountAccessRole (New Account, Bootstrap)

**When**: ProvisionAccount Lambda bootstraps the `StackSetExecution` role into a brand-new account before any StackSets can run. One-time per account.

`OrganizationAccountAccessRole` is created automatically by AWS Organizations when an account is created. Its trust policy trusts the org management account root and cannot be modified to require ExternalId. This is acceptable because:
1. It only happens once per account, immediately after creation
2. The Lambda is already protected by the ExternalId on the `AccountCreation` role ([1])
3. The session is used only to deploy the `StackSetExecution` role, then discarded

---

## [4] AccountCreation → OrganizationAccountAccessRole (New Account)

**When**: Same bootstrap flow as [3]. The `AccountCreation` role (assumed in [1]) then assumes `OrganizationAccountAccessRole` in the new account to deploy the `StackSetExecution` role via CloudFormation.

This is a two-hop assumption: `LambdaExecutionRole` → `AccountCreation` → `OrganizationAccountAccessRole`.

---

## [5] StackSetAdmin → StackSetExecution (Project Account)

**When**: CloudFormation service deploys StackSet instances into project accounts (DomainAccess role, VPC, IAM roles, EventBridge, blueprints).

**Assuming role** (`SMUS-AccountPoolFactory-StackSetAdmin` in org admin account)

Trust policy:
```json
{
  "Principal": { "Service": "cloudformation.amazonaws.com" },
  "Action": "sts:AssumeRole"
}
```

Permissions: can only assume `arn:aws:iam::*:role/SMUS-AccountPoolFactory-StackSetExecution`.

**Assumed role** (`SMUS-AccountPoolFactory-StackSetExecution` in project account, bootstrapped via [3]/[4])

Trust policy — scoped to the exact StackSetAdmin role ARN:
```json
{
  "Principal": {
    "AWS": "arn:aws:iam::<org-admin-account-id>:role/SMUS-AccountPoolFactory-StackSetAdmin"
  },
  "Action": "sts:AssumeRole"
}
```

Permissions: `AdministratorAccess` — required for CloudFormation to create arbitrary resources during StackSet deployment.

---

## [6] datazone.amazonaws.com → AccountResolutionRole (Domain Account)

**When**: DataZone calls the AccountProvider Lambda to list available pool accounts or validate an account assignment.

**Assumed role** (`SMUS-AccountPoolFactory-AccountResolution-Role` in domain account)

Trust policy:
```json
{
  "Principal": { "Service": "datazone.amazonaws.com" },
  "Action": "sts:AssumeRole"
}
```

Permissions: `lambda:InvokeFunction` on `AccountProvider` only. This role is not used by any AccountPoolFactory Lambda — it exists solely for DataZone to invoke the Lambda.

---

## [7] datazone.amazonaws.com → DataZoneManageAccessRole (Project Account)

**When**: DataZone manages Glue/LakeFormation access for data environments in the project account.

**Assumed role** (`DataZoneManageAccessRole` in project account, deployed by StackSet wave 2)

Trust policy — scoped to the specific domain via `SourceAccount` + `SourceArn`:
```json
{
  "Principal": { "Service": "datazone.amazonaws.com" },
  "Action": "sts:AssumeRole",
  "Condition": {
    "StringEquals": { "aws:SourceAccount": "<domain-account-id>" },
    "ArnLike": {
      "aws:SourceArn": "arn:aws:datazone:<region>:<domain-account-id>:domain/<domain-id>"
    }
  }
}
```

Both conditions are required — `SourceAccount` prevents cross-account DataZone domains from assuming this role; `SourceArn` scopes it to the specific domain.

Permissions: `AmazonDataZoneGlueManageAccessRolePolicy` (AWS managed) + `lakeformation:*`, `glue:*`, `s3:GetObject/PutObject/ListBucket`, `iam:PassRole`.

---

## [8] datazone.amazonaws.com → DataZoneProvisioningRole (Project Account)

**When**: DataZone provisions environments (deploys CloudFormation stacks for data environments) in the project account.

**Assumed role** (`DataZoneProvisioningRole` in project account, deployed by StackSet wave 2)

Trust policy: same as [7] — `datazone.amazonaws.com` with `SourceAccount` + `SourceArn` conditions scoped to the specific domain.

Permissions: `AdministratorAccess` — DataZone needs broad permissions to provision arbitrary environment types.

---

## [9] AWS Services → AmazonSageMakerProjectRole (Project Account)

**When**: SageMaker, DataZone, Glue, Bedrock, Athena, Redshift, and other services run project workloads.

**Assumed role** (`AmazonSageMakerProjectRole` in project account, deployed by StackSet wave 2, optional)

Trust policy — multi-service trust scoped to the project account:
```json
{
  "Principal": {
    "Service": [
      "datazone.amazonaws.com", "sagemaker.amazonaws.com", "glue.amazonaws.com",
      "lakeformation.amazonaws.com", "athena.amazonaws.com", "bedrock.amazonaws.com",
      "redshift.amazonaws.com", "airflow-serverless.amazonaws.com",
      "scheduler.amazonaws.com", "emr-serverless.amazonaws.com"
    ]
  },
  "Action": ["sts:AssumeRole", "sts:TagSession", "sts:SetContext", "sts:SetSourceIdentity"],
  "Condition": {
    "StringEquals": { "aws:SourceAccount": "<project-account-id>" }
  }
}
```

`SourceAccount` condition ensures only services running in the project account can assume this role — not services from other accounts.

Permissions: `SageMakerStudioAdminIAMPermissiveExecutionPolicy` (AWS managed, configurable via `02-domain-account/config.yaml`).

---

## Domain Account: LambdaExecutionRole Full Permissions

All seven AccountPoolFactory Lambdas share `SMUS-AccountPoolFactory-LambdaExecution-Role`. Trust policy:
```json
{
  "Principal": { "Service": "lambda.amazonaws.com" },
  "Action": "sts:AssumeRole"
}
```

Full permissions (from `01-infrastructure.yaml`):

| Scope | Actions | Resource |
|-------|---------|----------|
| DynamoDB | `Query`, `PutItem`, `UpdateItem`, `DeleteItem`, `GetItem` | `AccountPoolFactory-AccountState` table + all indexes |
| Lambda | `InvokeFunction` | `ProvisionAccount`, `PoolManager`, `SetupOrchestrator`, `DeprovisionAccount`, `AccountReconciler`, `AccountRecycler` — same account only |
| STS | `AssumeRole` | `SMUS-AccountPoolFactory-AccountCreation` (org admin), `SMUS-AccountPoolFactory-DomainAccess` (any project account), `OrganizationAccountAccessRole` (any account) |
| SNS | `Publish` | `AccountPoolFactory-Alerts` topic only |
| CloudWatch | `PutMetricData` | `*` |
| SSM | `GetParameter`, `GetParameters`, `GetParametersByPath` | `/AccountPoolFactory/*` |
| RAM | `CreateResourceShare`, `DeleteResourceShare`, `AssociateResourceShare`, `DisassociateResourceShare`, `GetResourceShares`, `GetResourceShareAssociations`, `ListResources`, `TagResource` | `*` |
| DataZone | `PutDomainSharingPolicy`, `GetDomain`, `ListEnvironments`, `GetEnvironment`, `GetProject` | Domain ARN only |
| SQS | `SendMessage`, `ReceiveMessage`, `DeleteMessage`, `GetQueueUrl`, `GetQueueAttributes`, `ChangeMessageVisibility` | `AccountPoolFactory-SetupQueue` + DLQ |
| KMS | `Decrypt` | `*` (for SSM SecureString) |

Why one shared role: all Lambdas run in the same account and trust boundary. A separate role per Lambda would not provide meaningful isolation — any Lambda can invoke any other Lambda in the account regardless of its execution role. The shared role makes the full permission surface explicit and auditable in one place.

---

## Org Admin S3 Template Bucket

`accountpoolfactory-templates-{org-account-id}` stores approved StackSet templates. Bucket policy:

- Org admin account: full access (`s3:*`)
- CloudFormation service: `s3:GetObject` on `stacksets/*` only
- Everyone else: explicit Deny via `StringNotEquals aws:PrincipalAccount` + `StringNotLike aws:PrincipalServiceName`

The domain account has no `s3:GetObject` on this bucket. Templates are only reachable via the assumed `AccountCreation` role session. Combined with the `EnforceS3TemplateSource` Deny in [1], this ensures StackSet templates can only come from org-admin-approved sources.

---

## RAM Share Security

The system uses a single org-wide RAM share instead of per-account shares:

```
Domain Account
└── RAM Share: DataZone-Domain-Share-OrgWide
      Principal: OU ARN (arn:aws:organizations::<org-id>:ou/<org>/<ou-id>)
      Resource:  DataZone Domain ARN
```

All accounts in the target OU automatically receive domain visibility. SetupOrchestrator only verifies domain visibility — it does not create shares.

Why org-wide: per-account RAM shares add a statement to the DataZone domain's resource policy per account. At 200+ pool accounts this hit AWS resource policy size limits (`LimitExceededException`). The org-wide share uses a single OU principal, covering all current and future pool accounts with one policy statement.

Security properties:
- The OU principal is scoped to the specific target OU — accounts outside the OU do not receive domain access
- RAM sharing with AWS Organizations requires `enable_sharing_with_aws_organization` from the Org Admin account — a one-time org-level operation that cannot be done from the domain account alone
- The share is managed by `LambdaExecutionRole` via `ram:CreateResourceShare`, `ram:AssociateResourceShare`
- Project accounts receive the shared resource but cannot modify or delete the share

---

## EventBridge Cross-Account Policy

Project accounts forward CloudFormation stack events to the domain account's central event bus. The bus policy restricts this to accounts within the AWS Organization:

```json
{
  "Action": "events:PutEvents",
  "Principal": "*",
  "Condition": {
    "StringEquals": { "aws:PrincipalOrgID": "<org-id>" }
  }
}
```

Only accounts that are members of the organization can put events on the bus — external accounts cannot inject events even if they know the bus ARN.

---

## Tag-Based Account Identification

Pool accounts carry two AWS Organizations tags applied at creation time:

- `ManagedBy: AccountPoolFactory`
- `PoolName: <pool-name>`

The AccountReconciler scopes its OU scan to only pool-managed accounts using these tags. Accounts with a different `PoolName` tag are skipped even if they have the `ManagedBy` tag — this provides multi-pool isolation when multiple pools share the same OU.

---

## Blueprint Policy Grants

`AWS::DataZone::PolicyGrant` resources for `ENVIRONMENT_BLUEPRINT_CONFIGURATION` cannot be created by the Admin IAM role directly — DataZone requires the caller to be a domain owner identity. These grants are deployed via CloudFormation (using the domain's service role internally) in the `06-blueprint-enablement.yaml` StackSet template.

Each grant:
- `EntityType: ENVIRONMENT_BLUEPRINT_CONFIGURATION`
- `EntityIdentifier: {AWS::AccountId}:{BlueprintId}` — auto-resolves to the project account
- `PolicyType: CREATE_ENVIRONMENT_FROM_BLUEPRINT`
- `Principal: CONTRIBUTOR projects in root domain unit, IncludeChildDomainUnits: true`

The `CREATE_PROJECT_FROM_PROJECT_PROFILE` domain unit grant is a one-time domain-level operation managed via `tests/setup/deploy-policy-grants-cf.sh`. This grant type IS permitted for the Admin IAM role (unlike `ENVIRONMENT_BLUEPRINT_CONFIGURATION`).

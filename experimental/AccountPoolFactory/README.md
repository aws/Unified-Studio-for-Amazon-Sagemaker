# Account Pool Factory for SageMaker Unified Studio

## Why

SageMaker Unified Studio projects often need security isolation — one project should not be able to delete, modify, or even see another project's resources until results are explicitly published to the data catalog.

In IDC domains today, this isolation is achieved through complex IAM policies with resource-tag conditions scoped to each project. For example, the [SageMakerStudioProjectUserRolePolicy](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/SageMakerStudioProjectUserRolePolicy.html) uses `Project` tag conditions on every action. This approach is fragile: it depends on every AWS service supporting tag-based permissions, the policies are hard to audit, and a single misconfigured condition can leak access across projects.

A dedicated AWS account per project provides much stronger isolation. The IAM boundary is the account itself — no tag conditions needed, no cross-project leakage possible, and the policies are simple and auditable.

The challenge: provisioning and configuring a new account (VPC, IAM roles, Lake Formation, EventBridge, blueprints) takes 10-20 minutes. Users can't wait that long when they click "Create Project."

## What

Account Pool Factory solves this by maintaining a pool of pre-configured accounts ready for instant assignment. When a user creates a project, an account is assigned in under 5 seconds. In the background, the pool replenishes itself by provisioning new accounts in parallel. When a project is deleted, the account is reclaimed — either cleaned and returned to the pool, or decommissioned. When new infrastructure is required (e.g. a new StackSet), the pool rolls out updates to all existing accounts automatically.

Key capabilities: configurable pool size per OU, self-healing reconciliation, automatic reclaim/recycle, rolling StackSet updates, IDC domain support.

## Personas

The system is operated by two personas with separate AWS accounts and distinct responsibilities:

**Org Admin** — owns the AWS Organizations management account. Responsible for governance: which StackSet templates are approved for deployment into project accounts, which OUs accounts are created in, and what tags/email conventions are used. The org admin does not know about pools or pool sizing — they define what's allowed, not how many.

**Domain Admin** — owns the SageMaker Unified Studio / DataZone domain account. Responsible for pool operations: how many accounts to keep ready, which subset of org-approved StackSets to deploy per pool, reclaim strategy, project profiles, and day-to-day monitoring. The domain admin picks from the org-approved menu and decides the pool shape.

This separation means the org admin can approve a new StackSet template without touching pool config, and the domain admin can resize a pool or change reclaim strategy without touching governance.

## Getting Started

Deployment involves two roles — domain admin deploys first, then hands off to org admin.

1. **Domain admin** deploys infrastructure + Lambdas — see [DomainAdminGuide.md](docs/DomainAdminGuide.md)
2. **Org admin** deploys governance stack + StackSets — see [OrgAdminGuide.md](docs/OrgAdminGuide.md)
3. **Domain admin** completes setup (project profile, seed pool) — back to [DomainAdminGuide.md](docs/DomainAdminGuide.md)

## Documentation

| Doc | What it covers |
|-----|---------------|
| [OrgAdminGuide.md](docs/OrgAdminGuide.md) | Governance stack, IAM roles, StackSets |
| [DomainAdminGuide.md](docs/DomainAdminGuide.md) | Deployment, pool config, monitoring, operations, UI |
| [Architecture.md](docs/Architecture.md) | How the system works, component details |
| [SecurityGuide.md](docs/SecurityGuide.md) | IAM roles, ExternalId, policy grants |
| [TestingGuide.md](docs/TestingGuide.md) | End-to-end testing, troubleshooting |

## Project Structure

```
01-org-account/                    # Org admin governance (pool-agnostic)
  config.yaml                      # Approved stacksets, OU definitions
  scripts/{deploy,cleanup}/        # Deploy/cleanup scripts
  templates/cloudformation/        # OrgAdmin CF template

02-domain-account/                 # Domain admin pool management
  config.yaml                      # Pool definitions (sizing, stacksets, OU mapping)
  scripts/{deploy,cleanup}/        # Deploy/cleanup scripts
  scripts/utils/                   # Operational utilities (domain admin)
  templates/cloudformation/        # Infrastructure CF template

approved-stacksets/                # StackSet templates (org-approved)
  cloudformation/{idc,iam}/        # CloudFormation stacksets
  cdk/                             # CDK stacksets (future)
  terraform/                       # Terraform stacksets (future)

src/                               # Lambda function source code
docs/                              # Documentation
tests/                             # Integration and setup tests
```

## Architecture (3 accounts)

```
Org Admin Account
  └── ProvisionAccount Lambda — creates accounts, deploys StackSets

Domain Account
  ├── AccountProvider Lambda   — returns available accounts to DataZone
  ├── PoolManager Lambda       — monitors pool, triggers replenishment
  ├── SetupOrchestrator Lambda — configures project accounts (VPC, IAM, blueprints)
  ├── AccountReconciler Lambda — hourly: detects drift, marks FAILED
  ├── AccountRecycler Lambda   — fixes FAILED accounts, self-triggers until done
  └── DynamoDB                 — account state tracking

Project Accounts (pool)
  └── Pre-configured: VPC, IAM roles, blueprints, EventBridge
```

## Requirements

- AWS Organizations enabled
- SageMaker Unified Studio / DataZone domain (IDC mode)
- Python 3.12+, AWS CLI, isengardcli

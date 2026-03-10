# Account Pool Factory for SageMaker Unified Studio

Maintains a pool of pre-configured AWS accounts ready for instant project assignment in SageMaker Unified Studio (SMUS/DataZone). When a user creates a project, an account is assigned in < 5 seconds instead of waiting 5-6 minutes for provisioning.

**Key capabilities**: configurable pool size, self-healing reconciliation, IDC domain support, rolling blueprint updates.

## Getting Started

Deployment involves two roles — domain admin deploys first, then hands off to org admin.

1. **Domain admin** — see [DomainAdminGuide.md](docs/DomainAdminGuide.md)
2. **Org admin** — see [OrgAdminGuide.md](docs/OrgAdminGuide.md)
3. **Domain admin** completes setup and seeds the pool — back to [DomainAdminGuide.md](docs/DomainAdminGuide.md)

## Documentation

| Doc | What it covers |
|-----|---------------|
| [OrgAdminGuide.md](docs/OrgAdminGuide.md) | Governance stack, IAM roles, StackSets |
| [DomainAdminGuide.md](docs/DomainAdminGuide.md) | Deployment, pool config, monitoring, operations, UI |
| [Architecture.md](docs/Architecture.md) | How the system works, component details |
| [SecurityGuide.md](docs/SecurityGuide.md) | IAM roles, ExternalId, policy grants |
| [TestingGuide.md](docs/TestingGuide.md) | End-to-end testing, troubleshooting |

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

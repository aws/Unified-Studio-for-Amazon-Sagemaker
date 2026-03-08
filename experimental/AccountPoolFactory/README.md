# Account Pool Factory for SageMaker Unified Studio

An automated account provisioning and management system for SageMaker Unified Studio (SMUS/DataZone) that maintains a pool of pre-configured AWS accounts ready for instant project assignment.

## Overview

When a user creates a project in SageMaker Unified Studio, that project needs a dedicated AWS account. Setting one up takes 5-6 minutes. The Account Pool Factory eliminates that wait by maintaining a pool of pre-configured accounts that are ready before users need them.

**Key capabilities**:
- Pre-configured account pool (configurable size, default 10 accounts)
- Instant project creation — account assigned in < 5 seconds
- Self-healing: hourly reconciliation detects drift, recycler fixes it automatically
- Supports IDC (Identity Center) domains — no IAM role configs needed at project creation
- Rolling updates: push blueprint/config changes to all pool accounts without downtime

## Quick Start

```bash
cd experimental/AccountPoolFactory
cp config.yaml.template config.yaml
# Edit config.yaml with your account IDs, domain ID, region, default_project_owner
```

Then follow the [User Guide](docs/UserGuide.md).

## Documentation

| Doc | What it covers |
|-----|---------------|
| [UserGuide.md](docs/UserGuide.md) | Setup, deployment, day-to-day operations |
| [Architecture.md](docs/Architecture.md) | How the system works, component details |
| [TestingGuide.md](docs/TestingGuide.md) | End-to-end testing procedures |
| [SecurityGuide.md](docs/SecurityGuide.md) | IAM roles, ExternalId, policy grants |
| [ProjectStructure.md](docs/ProjectStructure.md) | Directory layout, scripts reference |

## Architecture (3 accounts)

```
Org Admin Account (495869084367)
  └── ProvisionAccount Lambda — creates accounts, deploys StackSets

Domain Account (994753223772)
  ├── AccountProvider Lambda  — returns available accounts to DataZone
  ├── PoolManager Lambda      — monitors pool, triggers replenishment
  ├── SetupOrchestrator Lambda — configures project accounts (VPC, IAM, blueprints)
  ├── AccountReconciler Lambda — hourly: detects drift, marks FAILED
  ├── AccountRecycler Lambda  — fixes FAILED accounts, self-triggers until done
  └── DynamoDB                — account state tracking

Project Accounts (pool)
  └── Pre-configured: VPC, IAM roles, 17 blueprints + policy grants, EventBridge
```

## Self-Healing Loop

```
EventBridge (hourly)
  → AccountReconciler (detect-only: validates all AVAILABLE accounts)
    → marks unhealthy accounts FAILED with reason (NEEDS_STACKSET / NEEDS_SETUP)
  → AccountRecycler (fixes FAILED accounts in parallel)
    → self-triggers near 900s timeout until all accounts are healthy
```

## Project Structure

```
AccountPoolFactory/
├── config.yaml                          # Your environment config
├── src/
│   ├── account-provider/                # DataZone custom pool handler
│   ├── pool-manager/                    # Pool monitoring + replenishment
│   ├── setup-orchestrator/              # Account setup (VPC, IAM, blueprints)
│   ├── deprovision-account/             # Account cleanup (REUSE strategy)
│   ├── provision-account/               # Account creation (Org Admin)
│   ├── account-reconciler/              # Drift detection
│   └── account-recycler/               # Self-healing fixer
├── templates/cloudformation/
│   ├── 01-org-mgmt-account/deploy/      # Org Admin infra
│   ├── 02-domain-account/deploy/        # Domain infra + Lambda config
│   └── 03-project-account/deploy/       # Per-account stacks (VPC, IAM, blueprints)
├── scripts/
│   ├── 01-org-mgmt-account/deploy/      # Org Admin deploy scripts
│   ├── 02-domain-account/deploy/        # Domain deploy scripts
│   └── utils/                           # invoke-reconciler, invoke-recycler, check-pool-status, etc.
└── tests/
    ├── .test-create-from-pool-IDC.py    # End-to-end test (IDC domain)
    └── setup/                           # Setup scripts
```

## Requirements

- AWS Organizations enabled
- SageMaker Unified Studio / DataZone domain (IDC or IAM mode)
- Python 3.12+
- AWS CLI
- isengardcli (for credential switching between accounts)

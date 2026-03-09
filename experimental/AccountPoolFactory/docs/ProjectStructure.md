# Account Pool Factory - Project Structure

## Directory Tree

```
experimental/AccountPoolFactory/
├── README.md
├── org-config.yaml                      # Org Admin account config (copy from .template)
├── org-config.yaml.template
├── domain-config.yaml                   # Domain account config (copy from .template)
├── domain-config.yaml.template
│
├── src/                                 # Lambda source code
│   ├── account-provider/
│   │   └── lambda_function_prod.py      # DataZone custom pool handler
│   ├── pool-manager/
│   │   └── lambda_function.py           # Pool monitoring + replenishment
│   ├── setup-orchestrator/
│   │   └── lambda_function.py           # Account setup (VPC, IAM, blueprints, grants)
│   ├── deprovision-account/
│   │   └── lambda_function.py           # Account cleanup (REUSE strategy)
│   ├── provision-account/
│   │   └── lambda_function.py           # Account creation + StackSet deployment
│   ├── account-reconciler/
│   │   └── lambda_function.py           # Hourly drift detection
│   └── account-recycler/
│       └── lambda_function.py           # Self-healing fixer (FAILED → AVAILABLE)
│
├── templates/cloudformation/
│   ├── 01-org-mgmt-account/deploy/
│   │   ├── SMUS-AccountPoolFactory-OrgAdmin.yaml  # IAM roles CF stack
│   │   └── 03-domain-access-stackset.yaml         # StackSet template body (not standalone)
│   ├── 02-domain-account/deploy/
│   │   └── 01-infrastructure.yaml       # All domain infra: DynamoDB, Lambdas, EventBridge, SNS, SSM
│   └── 03-project-account/deploy/
│       ├── 01-stackset-execution-role.yaml
│       ├── 02-vpc-setup.yaml
│       ├── 03-iam-roles.yaml
│       ├── 04-eventbridge-rules.yaml
│       ├── 04-project-role.yaml
│       └── blueprint-enablement-iam.yaml
│
├── scripts/
│   ├── deploy-all.sh                    # Full deploy orchestrator (both accounts)
│   ├── 01-org-mgmt-account/
│   │   ├── deploy/
│   │   │   ├── 01-deploy.sh             # Deploy governance stack + StackSet
│   │   │   └── 02-verify.sh             # Verify org admin resources
│   │   └── cleanup/
│   │       └── cleanup.sh               # Remove all org admin resources
│   ├── 02-domain-account/
│   │   ├── deploy/
│   │   │   ├── 01-deploy.sh             # Deploy infrastructure stack + all Lambdas
│   │   │   ├── 02-deploy-project-profile.sh  # Create/update DataZone project profile
│   │   │   └── 03-verify.sh             # Verify domain account resources
│   │   └── cleanup/
│   │       └── cleanup.sh               # Remove infrastructure stack
│   └── utils/
│       ├── resolve-config.sh            # Sourced by all scripts — resolves IDs from config
│       ├── validate-config.sh           # Validate org-config.yaml + domain-config.yaml
│       ├── check-pool-status.sh         # Pool state counts + recent Lambda logs
│       ├── check-account-state.sh       # Single account: DynamoDB state + CF stacks
│       ├── invoke-reconciler.sh         # --dry-run, --auto-recycle, --account ID
│       ├── invoke-recycler.sh           # --all, --account, --force, --async, --update-blueprints
│       ├── cleanup-failed-accounts.sh   # Remove FAILED accounts from DynamoDB
│       ├── clear-dynamodb-table.sh      # ⚠️ Wipe all pool state
│       └── test-provision-account.sh    # Test ProvisionAccount Lambda directly
│
├── tests/
│   ├── integration/
│   │   └── test-e2e-pool-lifecycle.py   # Full lifecycle: create project → assign → delete → reclaim
│   └── setup/
│       └── deploy-policy-grants-cf.sh   # Add CREATE_PROJECT_FROM_PROJECT_PROFILE grant
│
└── docs/
    ├── GettingStarted.md
    ├── OrgAdminGuide.md
    ├── DomainAdminGuide.md
    ├── Architecture.md
    ├── TestingGuide.md
    ├── SecurityGuide.md
    └── ProjectStructure.md              # This file
```

## Scripts Reference

### Deploy Scripts

| Script | Account | What it does |
|--------|---------|-------------|
| `scripts/deploy-all.sh` | Both | Interactive full deploy — prompts for credential switch between phases |
| `scripts/01-org-mgmt-account/deploy/01-deploy.sh <domain-account-id> <domain-id>` | Org Admin | Deploys `AccountPoolFactory-OrgAdmin` CF stack + `SMUS-AccountPoolFactory-DomainAccess` StackSet |
| `scripts/01-org-mgmt-account/deploy/02-verify.sh` | Org Admin | Verifies CF stack, IAM roles, StackSet, target OU |
| `scripts/02-domain-account/deploy/01-deploy.sh [--lambdas-only]` | Domain | Deploys infrastructure CF stack + all 7 Lambdas. `--lambdas-only` skips CF stack. |
| `scripts/02-domain-account/deploy/02-deploy-project-profile.sh [source-profile]` | Domain | Creates/updates DataZone project profile with account pool |
| `scripts/02-domain-account/deploy/03-verify.sh` | Domain | Verifies stack, Lambdas, IAM roles, DynamoDB, domain, pool, profile |

### Cleanup Scripts

| Script | Account | What it does |
|--------|---------|-------------|
| `scripts/02-domain-account/cleanup/cleanup.sh` | Domain | Deletes `AccountPoolFactory-Infrastructure` stack (does NOT close pool accounts) |
| `scripts/01-org-mgmt-account/cleanup/cleanup.sh` | Org Admin | Deletes StackSet instances + StackSet + `AccountPoolFactory-OrgAdmin` stack |

### Utility Scripts

| Script | Account | What it does |
|--------|---------|-------------|
| `utils/validate-config.sh` | Either | Validates `org-config.yaml` and `domain-config.yaml` |
| `utils/check-pool-status.sh` | Domain | Shows account counts by state + recent PoolManager/AccountProvider logs |
| `utils/check-account-state.sh <account-id>` | Domain or Org | DynamoDB record + CF stacks for a single account |
| `utils/invoke-reconciler.sh` | Domain | Invokes AccountReconciler. Options: `--dry-run`, `--auto-recycle`, `--auto-replenish`, `--account ID` |
| `utils/invoke-recycler.sh` | Domain | Invokes AccountRecycler. Options: `--all`, `--account ID`, `--accounts IDs`, `--force`, `--async`, `--update-blueprints` |
| `utils/cleanup-failed-accounts.sh` | Domain | Removes FAILED accounts from DynamoDB to unblock replenishment |
| `utils/clear-dynamodb-table.sh [--force]` | Domain | ⚠️ Deletes all items from DynamoDB (use for full reset) |
| `utils/test-provision-account.sh` | Domain | Invokes ProvisionAccount Lambda directly for testing |

## Account States

| State | Meaning |
|-------|---------|
| `AVAILABLE` | Ready for project assignment |
| `ASSIGNED` | In use by a project |
| `SETTING_UP` | Being provisioned by SetupOrchestrator |
| `CLEANING` | Being deprovisioned (REUSE strategy) |
| `FAILED` | Setup or cleanup failed — recycler fixes automatically |
| `ORPHANED` | Found in org but not in DynamoDB — recycler fixes automatically |

## Lambda Deployment Packaging

`SetupOrchestrator` zip must include both the Python source and all CF templates flat:

```
setup-orchestrator.zip
├── lambda_function.py
├── 02-vpc-setup.yaml
├── 03-iam-roles.yaml
├── 04-eventbridge-rules.yaml
├── 04-project-role.yaml
└── blueprint-enablement-iam.yaml
```

The deploy script handles this automatically via `zip -j` (junk paths).

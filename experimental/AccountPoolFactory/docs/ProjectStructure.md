# Account Pool Factory - Project Structure

## Directory Tree

```
experimental/AccountPoolFactory/
├── README.md
├── config.yaml                          # Environment config (copy from config.yaml.template)
├── config.yaml.template
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
│   │   └── lambda_function.py           # Account creation + StackSet deployment (Org Admin)
│   ├── account-reconciler/
│   │   └── lambda_function.py           # Drift detection (detect-only, no fixes)
│   └── account-recycler/
│       └── lambda_function.py           # Self-healing fixer (FAILED → AVAILABLE)
│
├── templates/cloudformation/
│   ├── 01-org-mgmt-account/deploy/
│   │   ├── 01-stackset-roles.yaml       # StackSet admin/execution roles
│   │   ├── 02-provision-account.yaml    # ProvisionAccount Lambda + AccountCreation role
│   │   └── 03-domain-access-stackset.yaml  # StackSet template body (not standalone stack)
│   ├── 02-domain-account/deploy/
│   │   ├── 01-infrastructure.yaml       # All domain infra: DynamoDB, Lambdas, EventBridge, SNS, SSM
│   │   └── 02-project-profile-with-pool.yaml  # DataZone project profile
│   └── 03-project-account/deploy/
│       ├── 02-vpc-setup.yaml            # VPC + 3 private subnets
│       ├── 03-iam-roles.yaml            # ManageAccessRole + ProvisioningRole
│       ├── 04-eventbridge-rules.yaml    # Event forwarding to domain account
│       ├── 04-project-role.yaml         # AmazonSageMakerProjectRole
│       └── blueprint-enablement-iam.yaml  # 17 blueprints + 17 PolicyGrant resources
│
├── scripts/
│   ├── 01-org-mgmt-account/
│   │   ├── deploy/
│   │   │   ├── 01-deploy-stackset-roles.sh
│   │   │   └── 02-deploy-provision-account.sh  # --lambdas-only flag supported
│   │   └── cleanup/
│   ├── 02-domain-account/
│   │   ├── deploy/
│   │   │   ├── 01-deploy-infrastructure.sh  # --lambdas-only flag supported
│   │   │   └── 02-deploy-project-profile.sh
│   │   └── cleanup/
│   └── utils/
│       ├── check-pool-status.sh         # Pool state counts + recent Lambda logs
│       ├── check-account-state.sh       # Single account: DynamoDB state + CF stacks
│       ├── invoke-reconciler.sh         # --dry-run, --auto-recycle, --account ID
│       ├── invoke-recycler.sh           # --all, --account, --force, --async, --update-blueprints
│       ├── cleanup-per-account-ram-shares.sh  # Migration: delete old per-account RAM shares
│       ├── invoke-reconciler.sh
│       └── validate-config.sh
│
├── tests/
│   ├── .test-create-from-pool-IDC.py    # End-to-end test: IDC domain, pool account
│   ├── .test-create-domain-account.py   # Test: domain account as env account (no pool)
│   ├── .test-create-from-pool-IAM-DOMAIN.py  # Legacy: IAM domain test (not current)
│   └── setup/
│       ├── deploy-policy-grants-cf.sh   # Add CREATE_PROJECT_FROM_PROJECT_PROFILE grant
│       ├── 04-create-account-pool.sh
│       └── templates/
│           └── policy-grants.yaml       # CF template for blueprint grants (reference)
│
├── docs/
│   ├── Architecture.md
│   ├── UserGuide.md
│   ├── TestingGuide.md
│   ├── SecurityGuide.md
│   └── ProjectStructure.md              # This file
│
└── .kiro/
    ├── steering/
    │   └── ai-rules.md                  # AI assistant rules for this project
    └── specs/
        └── account-reconciliation-recycling/
            └── tasks.md                 # Implementation progress log
```

## Key Scripts Reference

### Deploy Scripts

| Script | Account | What it does |
|--------|---------|-------------|
| `scripts/01-org-mgmt-account/deploy/02-deploy-provision-account.sh` | Org Admin | Deploys ProvisionAccount Lambda + DomainAccess StackSet. `--lambdas-only` skips CF stack. |
| `scripts/02-domain-account/deploy/01-deploy-infrastructure.sh` | Domain | Deploys all domain infra + all 6 Lambdas. `--lambdas-only` skips CF stack. |
| `scripts/02-domain-account/deploy/02-deploy-project-profile.sh` | Domain | Creates DataZone project profile with account pool. |

### Utility Scripts

| Script | What it does |
|--------|-------------|
| `scripts/utils/check-pool-status.sh` | Shows account counts by state + recent Lambda logs |
| `scripts/utils/check-account-state.sh <account-id>` | DynamoDB state + CF stacks for one account |
| `scripts/utils/invoke-reconciler.sh [--dry-run] [--auto-recycle] [--account ID]` | Run reconciler |
| `scripts/utils/invoke-recycler.sh [--all] [--account ID] [--force] [--async] [--update-blueprints]` | Run recycler |

### Test Scripts

| Script | What it does |
|--------|-------------|
| `.test-create-from-pool-IDC.py` | Full end-to-end: get account from pool, create project (IDC domain) |
| `.test-create-domain-account.py` | Create project using domain account as env account (no pool) |

## Lambda Deployment Packaging

The `SetupOrchestrator` Lambda zip must include both the Python source and all CF templates flat (no subdirectory):

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

## Account States

| State | Meaning |
|-------|---------|
| `AVAILABLE` | Ready for project assignment |
| `ASSIGNED` | In use by a project |
| `CLEANING` | Being deprovisioned (REUSE strategy) |
| `FAILED` | Setup or cleanup failed — recycler will fix |
| `ORPHANED` | Found in org but not in DynamoDB — recycler will set up |
| `SUSPENDED` | In DynamoDB but not found in org |

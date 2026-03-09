# Scripts

Scripts are organized by account. Run them from the project root (`experimental/AccountPoolFactory/`).

## Structure

```
scripts/
├── deploy-all.sh                          # Full deploy (both accounts, interactive)
├── 01-org-mgmt-account/
│   ├── deploy/
│   │   ├── 01-deploy.sh                   # Deploy governance stack + StackSet
│   │   └── 02-verify.sh                   # Verify org admin resources
│   └── cleanup/
│       └── cleanup.sh                     # Remove all org admin resources
├── 02-domain-account/
│   ├── deploy/
│   │   ├── 01-deploy.sh                   # Deploy infrastructure stack + all Lambdas
│   │   ├── 02-deploy-project-profile.sh   # Create/update DataZone project profile
│   │   └── 03-verify.sh                   # Verify domain account resources
│   └── cleanup/
│       └── cleanup.sh                     # Remove infrastructure stack
└── utils/
    ├── resolve-config.sh                  # Sourced by all scripts — resolves IDs from config
    ├── validate-config.sh                 # Validate org-config.yaml + domain-config.yaml
    ├── check-pool-status.sh               # Pool state counts + recent Lambda logs
    ├── check-account-state.sh             # Single account: DynamoDB state + CF stacks
    ├── invoke-reconciler.sh               # Invoke AccountReconciler Lambda
    ├── invoke-recycler.sh                 # Invoke AccountRecycler Lambda
    ├── cleanup-failed-accounts.sh         # Remove FAILED accounts from DynamoDB
    ├── clear-dynamodb-table.sh            # Wipe all DynamoDB records (destructive)
    └── test-provision-account.sh          # Invoke ProvisionAccount Lambda directly
```

## Deploy Order

**Phase 1 — Org Admin account** (run once):
```bash
eval $(isengardcli credentials amirbo+1@amazon.com)
./scripts/01-org-mgmt-account/deploy/01-deploy.sh <domain-account-id> <domain-id>
./scripts/01-org-mgmt-account/deploy/02-verify.sh
```

**Phase 2 — Domain account:**
```bash
eval $(isengardcli credentials amirbo+3@amazon.com)
./scripts/02-domain-account/deploy/01-deploy.sh
./scripts/02-domain-account/deploy/02-deploy-project-profile.sh
./scripts/02-domain-account/deploy/03-verify.sh
```

Or run both phases interactively:
```bash
./scripts/deploy-all.sh
```

## Cleanup Order

```bash
# Domain account first
eval $(isengardcli credentials amirbo+3@amazon.com)
./scripts/02-domain-account/cleanup/cleanup.sh

# Then org admin account
eval $(isengardcli credentials amirbo+1@amazon.com)
./scripts/01-org-mgmt-account/cleanup/cleanup.sh
```

## Utility Scripts

| Script | Account | Usage |
|--------|---------|-------|
| `validate-config.sh` | Either | Check config files before deploying |
| `check-pool-status.sh` | Domain | Pool counts by state + recent logs |
| `check-account-state.sh <id>` | Domain or Org | DynamoDB state + CF stacks for one account |
| `invoke-reconciler.sh [--dry-run] [--auto-recycle] [--account ID]` | Domain | Run reconciler |
| `invoke-recycler.sh [--all] [--account ID] [--force] [--async] [--update-blueprints]` | Domain | Run recycler |
| `cleanup-failed-accounts.sh` | Domain | Remove FAILED accounts from DynamoDB |
| `clear-dynamodb-table.sh [--force]` | Domain | ⚠️ Wipe all pool state |
| `test-provision-account.sh` | Domain | Test ProvisionAccount Lambda directly |

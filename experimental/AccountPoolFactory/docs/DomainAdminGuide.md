# Account Pool Factory - Domain Admin Guide

[← Back to README](../README.md) | [Org Admin Guide](OrgAdminGuide.md) | [Architecture](Architecture.md) | [Security Guide](SecurityGuide.md) | [Testing Guide](TestingGuide.md)

---

Audience: the person who manages the DataZone / SageMaker Unified Studio domain and runs the account pool.

**Deployment order**: Deploy Account Pool Factory infrastructure for the domain account first, then hand `ProvisionAccountRoleArn` to the org admin.

---

## Prerequisites

- DataZone domain already created
- `02-domain-account/config.yaml` filled in (copy from `02-domain-account/config.yaml.template`):

```yaml
region: us-east-2
domain_name: "your-domain-name"

project_role:
  enabled: true
  role_name: AmazonSageMakerProjectRole
  managed_policy_arn: arn:aws:iam::aws:policy/AmazonSageMakerFullAccess

pools:
  - name: default
    min_size: 2
    target_size: 5
    reclaim_strategy: REUSE       # REUSE or DELETE
    default_project_owner: "your-sso-username"
    project_profile_name: "All Capabilities - Account Pool"
```

---

## Deployment

**Step 1 — Deploy Account Pool Factory infrastructure (domain account):**
```bash
# Switch to Domain account credentials
./02-domain-account/scripts/deploy/01-deploy.sh
```

This prints `ProvisionAccountRoleArn` — hand this to the org admin.

**Step 2 — Org admin deploys** (see OrgAdminGuide.md)

**Step 3 — Deploy project profile:**
```bash
./02-domain-account/scripts/deploy/02-deploy-project-profile.sh
```

**Step 4 — Verify:**
```bash
./02-domain-account/scripts/deploy/03-verify.sh
```

**Step 5 — Seed the pool:**
```bash
./02-domain-account/scripts/deploy/04-seed-pool.sh
```

Each account takes ~6-8 minutes. Monitor progress:
```bash
python3 02-domain-account/scripts/utils/monitor-pool.py 30
```

---

## Uninstall

```bash
# Switch to Domain account credentials
./02-domain-account/scripts/cleanup/cleanup.sh
```

---

## Web UI

Two browser apps for monitoring and operations:

- Pool Console — pool health, account states, replenishment, reconciliation
- Project Creator — create projects from the pool interactively

**Mock mode** (no AWS needed, fake data):
```bash
./02-domain-account/scripts/deploy/05-start-ui.sh
```

**Live mode** (real AWS, domain account credentials required):
```bash
eval $(isengardcli credentials amirbo+3@amazon.com)
./02-domain-account/scripts/deploy/05-start-ui.sh --live
```

Then open:
- http://localhost:8080/pool-console/
- http://localhost:8080/project-creator/

The server hot-reloads on file changes. Press Ctrl+C to stop.

---

## Creating a Test Project

The correct way to create a project from the pool (see Architecture.md Step 1 for why `userParameters` is required):

```bash
# Domain account credentials required
python3 tests/create-test-project.py           # create, keep
python3 tests/create-test-project.py --delete  # create + delete
```

---

## Monitoring

```bash
# Pool status
python3 02-domain-account/scripts/utils/monitor-pool.py

# Check pool status by state
./02-domain-account/scripts/utils/check-pool-status.sh

# CloudWatch logs
aws logs tail /aws/lambda/PoolManager --follow --region us-east-2
aws logs tail /aws/lambda/SetupOrchestrator --follow --region us-east-2
aws logs tail /aws/lambda/AccountReconciler --follow --region us-east-2

# Subscribe to alerts
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-2:<domain-account-id>:AccountPoolFactory-Alerts \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --region us-east-2
```

---

## Day-to-Day Operations

The system is self-healing. The AccountReconciler runs hourly to detect drift and mark broken accounts as FAILED. The AccountRecycler automatically picks up FAILED accounts and re-provisions them. The PoolManager monitors pool size and triggers replenishment when it drops below the minimum.

You should rarely need to intervene manually. The operations below are for exception cases only.

### Check pool health

```bash
# Quick status — account counts by state + recent Lambda activity
./02-domain-account/scripts/utils/check-pool-status.sh

# Continuous monitoring (refreshes every 30s)
python3 02-domain-account/scripts/utils/monitor-pool.py 30

# Inspect a specific account
./02-domain-account/scripts/utils/check-account-state.sh <account-id>
```

### Force replenishment (pool below target)

Use when: the pool is below target size and the hourly PoolManager hasn't caught up yet (e.g. after a burst of project creations).

```bash
./02-domain-account/scripts/deploy/04-seed-pool.sh           # all pools
./02-domain-account/scripts/deploy/04-seed-pool.sh default    # specific pool
```

### Handle failed accounts

Use when: the recycler hasn't auto-fixed a FAILED account after 2-3 cycles (check logs for root cause first).

```bash
# Recycle all FAILED accounts (recycler normally does this automatically)
./02-domain-account/scripts/utils/invoke-recycler.sh --all

# Force-recycle a specific account (works on any state)
./02-domain-account/scripts/utils/invoke-recycler.sh --account <account-id> --force

# Nuclear option: remove FAILED accounts from DynamoDB so replenishment creates fresh ones
./02-domain-account/scripts/utils/cleanup-failed-accounts.sh
```

### Run reconciler manually

Use when: you suspect drift (e.g. after a StackSet update) and don't want to wait for the hourly run.

```bash
# Dry run — shows what would change without modifying anything
./02-domain-account/scripts/utils/invoke-reconciler.sh --dry-run

# Full self-healing — marks drifted accounts as FAILED and triggers recycler
./02-domain-account/scripts/utils/invoke-reconciler.sh --auto-recycle
```

### Update StackSets fleet-wide

Use when: you've added or modified a StackSet template and need to roll it out to all existing pool accounts.

```bash
# Update blueprints on all AVAILABLE accounts
./02-domain-account/scripts/utils/invoke-recycler.sh --update-blueprints

# Verify pool health after rollout
./02-domain-account/scripts/utils/verify-pool-health.sh
```

---

## Configuration

Per-pool config lives in SSM under `/AccountPoolFactory/Pools/{pool-name}/`. Changes take effect on the next Lambda invocation.

### Pool sizing (per pool)
```bash
aws ssm put-parameter --name /AccountPoolFactory/Pools/default/MinimumPoolSize \
  --value "2" --type String --overwrite --region us-east-2

aws ssm put-parameter --name /AccountPoolFactory/Pools/default/TargetPoolSize \
  --value "5" --type String --overwrite --region us-east-2
```

### Reclaim strategy (per pool)
```bash
# REUSE: clean and return accounts to pool (preserves account quota)
aws ssm put-parameter --name /AccountPoolFactory/Pools/default/ReclaimStrategy \
  --value "REUSE" --type String --overwrite --region us-east-2

# DELETE: remove accounts from pool after project deletion
aws ssm put-parameter --name /AccountPoolFactory/Pools/default/ReclaimStrategy \
  --value "DELETE" --type String --overwrite --region us-east-2
```

---

## Account States Reference

| State | Meaning | Next action |
|-------|---------|-------------|
| `AVAILABLE` | Ready for assignment | None |
| `ASSIGNED` | In use by a project | None (reclaimed on project deletion) |
| `SETTING_UP` | Being provisioned | Wait (~6-8 min) |
| `CLEANING` | Being deprovisioned (REUSE) | Wait (~10-15 min) |
| `FAILED` | Setup/cleanup failed | Recycler fixes automatically (hourly) |
| `ORPHANED` | In org OU but not in DynamoDB | Recycler fixes automatically (hourly) |

**Stuck ASSIGNED account** (no real project): force-recycle with `{"accountId":"...","force":true}`.

---

## What This Installs

One CloudFormation stack (`AccountPoolFactory-Infrastructure`) in the domain account:

| Resource | Purpose |
|----------|---------|
| ProvisionAccount Lambda | Creates AWS accounts via cross-account role in Org Admin. Reads pool config (OU, email, StackSets) from org SSM at runtime. |
| PoolManager Lambda | Monitors pool size per pool, triggers replenishment, handles assignment/reclaim via DataZone events |
| SetupOrchestrator Lambda | Configures new accounts (VPC, IAM, blueprints, EventBridge) |
| DeprovisionAccount Lambda | Cleans accounts for REUSE strategy. Uses per-account `deployedStackSets` to protect infrastructure. |
| AccountProvider Lambda | Handles DataZone account pool requests. Routes by project profile → pool via SSM mapping. |
| AccountReconciler Lambda | Hourly health check — scans all pool OUs, validates per-account stack lists, triggers recycler |
| AccountRecycler Lambda | Fixes FAILED/ORPHANED/CLEANING/ASSIGNED(force) accounts |
| DynamoDB table | Tracks account states. Has `PoolIndex` GSI (poolName + state) for efficient per-pool queries. |
| EventBridge central bus | Receives events from project accounts |
| SNS topic | Alerts for failures and pool depletion |
| SSM parameters | Per-pool config under `/AccountPoolFactory/Pools/{name}/` |

---

## Additional Info

### Update Lambda code only (no CF stack change)

If you've only changed Lambda source code and don't need to update the CF stack:

```bash
./02-domain-account/scripts/deploy/01-deploy.sh --lambdas-only
```

### Seed a specific pool only

```bash
./02-domain-account/scripts/deploy/04-seed-pool.sh default
```

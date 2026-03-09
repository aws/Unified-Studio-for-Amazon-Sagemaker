# Account Pool Factory - Domain Admin Guide

Audience: the person who manages the DataZone / SageMaker Unified Studio domain and runs the account pool.

**Deployment order**: Deploy domain infrastructure first, then hand `ProvisionAccountRoleArn` to the org admin.

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

## Prerequisites

- DataZone domain already created
- `domain-config.yaml` filled in (copy from `domain-config.yaml.template`):

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

**Step 1 — Deploy domain infrastructure first:**
```bash
eval $(isengardcli credentials amirbo+3@amazon.com)
./scripts/02-domain-account/deploy/01-deploy.sh
```

This prints `ProvisionAccountRoleArn` — hand this to the org admin.

**Step 2 — Org admin deploys** (see OrgAdminGuide.md)

**Step 3 — Deploy project profile:**
```bash
./scripts/02-domain-account/deploy/02-deploy-project-profile.sh
```

**Step 4 — Verify:**
```bash
./scripts/02-domain-account/deploy/03-verify.sh
```

To update Lambda code only (no CF stack change):
```bash
./scripts/02-domain-account/deploy/01-deploy.sh --lambdas-only
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

## Seeding the Pool

```bash
aws lambda invoke \
  --function-name PoolManager \
  --payload '{"action":"force_replenishment"}' \
  --cli-binary-format raw-in-base64-out \
  --region us-east-2 /tmp/response.json

# Monitor
python3 scripts/utils/monitor-pool.py 30
```

Each account takes ~6-8 minutes. The pool fills to `TargetPoolSize` automatically.

To seed a specific pool only:
```bash
aws lambda invoke \
  --function-name PoolManager \
  --payload '{"action":"force_replenishment","poolName":"default"}' \
  --cli-binary-format raw-in-base64-out \
  --region us-east-2 /tmp/response.json
```

---

## Creating a Test Project

The correct way to create a project from the pool (see Architecture.md Step 1 for why `userParameters` is required):

```bash
eval $(isengardcli credentials amirbo+3@amazon.com)
python3 scripts/03-project-account/deploy/01-create-test-project.py           # create, keep
python3 scripts/03-project-account/deploy/01-create-test-project.py --delete  # create + delete
```

---

## Monitoring

```bash
# Pool status
python3 scripts/utils/monitor-pool.py

# Check pool status by state
./scripts/utils/check-pool-status.sh

# CloudWatch logs
aws logs tail /aws/lambda/PoolManager --follow --region us-east-2
aws logs tail /aws/lambda/SetupOrchestrator --follow --region us-east-2
aws logs tail /aws/lambda/AccountReconciler --follow --region us-east-2

# Subscribe to alerts
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-2:994753223772:AccountPoolFactory-Alerts \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --region us-east-2
```

---

## Day-to-Day Operations

### Trigger manual replenishment
```bash
aws lambda invoke --function-name PoolManager \
  --payload '{"action":"force_replenishment"}' \
  --cli-binary-format raw-in-base64-out --region us-east-2 /tmp/r.json
```

### Handle failed accounts
```bash
# Recycler fixes FAILED/ORPHANED automatically
aws lambda invoke --function-name AccountRecycler \
  --payload '{"recycleAll":true}' \
  --cli-binary-format raw-in-base64-out --region us-east-2 /tmp/r.json

# Force-recycle a specific account (works on AVAILABLE, ASSIGNED, CLEANING, FAILED, ORPHANED)
aws lambda invoke --function-name AccountRecycler \
  --payload '{"accountId":"123456789012","force":true}' \
  --cli-binary-format raw-in-base64-out --region us-east-2 /tmp/r.json
```

### Run reconciler manually
```bash
# Dry run
aws lambda invoke --function-name AccountReconciler \
  --payload '{"source":"manual","dryRun":true}' \
  --cli-binary-format raw-in-base64-out --region us-east-2 /tmp/r.json

# Full self-healing
aws lambda invoke --function-name AccountReconciler \
  --payload '{"source":"manual","dryRun":false,"autoRecycle":true,"autoReplenish":true}' \
  --cli-binary-format raw-in-base64-out --region us-east-2 /tmp/r.json
```

### Update blueprints fleet-wide
```bash
aws lambda invoke --function-name AccountRecycler \
  --payload '{"updateBlueprints":true}' \
  --cli-binary-format raw-in-base64-out --region us-east-2 /tmp/r.json
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

## Uninstall

```bash
eval $(isengardcli credentials amirbo+3@amazon.com)
./scripts/02-domain-account/cleanup/cleanup.sh
```

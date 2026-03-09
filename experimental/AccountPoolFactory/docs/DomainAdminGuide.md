# Account Pool Factory - Domain Admin Guide

Audience: the person who manages the DataZone / SageMaker Unified Studio domain and runs the account pool.

---

## What This Installs

One CloudFormation stack (`AccountPoolFactory-Infrastructure`) in the domain account containing all application logic:

| Resource | Purpose |
|----------|---------|
| ProvisionAccount Lambda | Creates AWS accounts via cross-account role in Org Admin |
| PoolManager Lambda | Monitors pool size, triggers replenishment, handles assignment/reclaim via DataZone events |
| SetupOrchestrator Lambda | Configures new accounts (VPC, IAM, blueprints, EventBridge) |
| DeprovisionAccount Lambda | Cleans accounts for REUSE strategy |
| AccountProvider Lambda | Handles DataZone account pool requests (list + validate) |
| AccountReconciler Lambda | Hourly health check — detects drift, triggers recycler |
| AccountRecycler Lambda | Fixes FAILED/ORPHANED/CLEANING accounts |
| DynamoDB table | Tracks account states |
| EventBridge central bus | Receives events from project accounts |
| SNS topic | Alerts for failures and pool depletion |
| SSM parameters | All configuration (pool size, email, strategy, etc.) |

---

## Prerequisites

- Org Admin has deployed `AccountPoolFactory-OrgAdmin` (the domain deploy script reads its outputs automatically)
- DataZone domain already created
- `domain-config.yaml` filled in (copy from `domain-config.yaml.template`):
  ```yaml
  region: us-east-2
  domain_name: "your-domain-name"          # ID resolved automatically
  default_project_owner: "your-sso-username"
  project_profile_name: "All Capabilities - Account Pool"
  email_prefix: "accountpool"
  email_domain: "example.com"
  ```

---

## Deployment

```bash
eval $(isengardcli credentials amirbo+3@amazon.com)
./scripts/02-domain-account/deploy/01-deploy-infrastructure.sh
```

The script resolves all IDs automatically (domain ID from name, org admin role ARN from the `AccountPoolFactory-OrgAdmin` stack, organization ID from the Organizations API). No manual ID copying needed.

Then deploy the project profile:

```bash
./scripts/02-domain-account/deploy/02-deploy-project-profile.sh
```

To update Lambda code only (no CF stack change):

```bash
./scripts/02-domain-account/deploy/01-deploy-infrastructure.sh --lambdas-only
```

---

## Configuration

All configuration lives in SSM Parameter Store under `/AccountPoolFactory/PoolManager/`. Changes take effect on the next Lambda invocation — no restart needed.

### Pool Size

```bash
# Minimum accounts to keep ready (default: 5)
aws ssm put-parameter --name /AccountPoolFactory/PoolManager/MinimumPoolSize \
  --value "5" --type String --overwrite --region us-east-2

# Target size after replenishment (default: 10)
aws ssm put-parameter --name /AccountPoolFactory/PoolManager/TargetPoolSize \
  --value "10" --type String --overwrite --region us-east-2
```

### Reclaim Strategy

```bash
# DELETE: close accounts when projects are deleted (default, saves quota)
aws ssm put-parameter --name /AccountPoolFactory/PoolManager/ReclaimStrategy \
  --value "DELETE" --type String --overwrite --region us-east-2

# REUSE: clean and return accounts to pool (preserves account quota)
aws ssm put-parameter --name /AccountPoolFactory/PoolManager/ReclaimStrategy \
  --value "REUSE" --type String --overwrite --region us-east-2
```

### Email and Naming

```bash
aws ssm put-parameter --name /AccountPoolFactory/PoolManager/EmailPrefix \
  --value "accountpool" --type String --overwrite --region us-east-2

aws ssm put-parameter --name /AccountPoolFactory/PoolManager/EmailDomain \
  --value "example.com" --type String --overwrite --region us-east-2
```

### Target OU

```bash
# Move accounts to a specific OU after creation
aws ssm put-parameter --name /AccountPoolFactory/PoolManager/TargetOUId \
  --value "ou-xxxx-xxxxxxxx" --type String --overwrite --region us-east-2
```

---

## Seeding the Pool

Trigger initial pool creation:

```bash
aws lambda invoke \
  --function-name PoolManager \
  --payload '{"action":"force_replenishment"}' \
  --cli-binary-format raw-in-base64-out \
  --region us-east-2 /tmp/response.json
```

Monitor progress:

```bash
aws logs tail /aws/lambda/SetupOrchestrator --follow --region us-east-2
```

Each account takes ~6-8 minutes to set up. The pool will fill to `TargetPoolSize` automatically.

---

## Monitoring

### Check Pool Status

```bash
# Count by state
for state in AVAILABLE ASSIGNED SETTING_UP FAILED CLEANING ORPHANED; do
  count=$(aws dynamodb query \
    --table-name AccountPoolFactory-AccountState \
    --index-name StateIndex \
    --key-condition-expression '#s = :s' \
    --expression-attribute-names '{"#s":"state"}' \
    --expression-attribute-values "{\":s\":{\"S\":\"$state\"}}" \
    --select COUNT --region us-east-2 \
    --query 'Count' --output text 2>/dev/null)
  echo "$state: $count"
done
```

### CloudWatch Logs

```bash
aws logs tail /aws/lambda/PoolManager --follow --region us-east-2
aws logs tail /aws/lambda/SetupOrchestrator --follow --region us-east-2
aws logs tail /aws/lambda/AccountReconciler --follow --region us-east-2
```

### Subscribe to Alerts

```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-2:994753223772:AccountPoolFactory-Alerts \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --region us-east-2
```

---

## Day-to-Day Operations

### Trigger Manual Replenishment

```bash
aws lambda invoke \
  --function-name PoolManager \
  --payload '{"action":"force_replenishment"}' \
  --cli-binary-format raw-in-base64-out \
  --region us-east-2 /tmp/response.json
```

### Handle Failed Accounts

```bash
# See failed accounts
aws dynamodb query \
  --table-name AccountPoolFactory-AccountState \
  --index-name StateIndex \
  --key-condition-expression '#s = :s' \
  --expression-attribute-names '{"#s":"state"}' \
  --expression-attribute-values '{":s":{"S":"FAILED"}}' \
  --region us-east-2

# Trigger recycler to fix them
aws lambda invoke \
  --function-name AccountRecycler \
  --payload '{"recycleAll":true}' \
  --cli-binary-format raw-in-base64-out \
  --region us-east-2 /tmp/response.json

# Remove a specific failed account from pool (manual cleanup)
aws lambda invoke \
  --function-name PoolManager \
  --payload '{"action":"delete_failed_account","accountId":"123456789012"}' \
  --cli-binary-format raw-in-base64-out \
  --region us-east-2 /tmp/response.json
```

### Run Reconciler Manually

```bash
# Dry run — see what would change
aws lambda invoke \
  --function-name AccountReconciler \
  --payload '{"source":"manual","dryRun":true}' \
  --cli-binary-format raw-in-base64-out \
  --region us-east-2 /tmp/response.json

# Full self-healing run
aws lambda invoke \
  --function-name AccountReconciler \
  --payload '{"source":"manual","dryRun":false,"autoRecycle":true,"autoReplenish":true}' \
  --cli-binary-format raw-in-base64-out \
  --region us-east-2 /tmp/response.json
```

### Push Blueprint Template Updates to All Accounts

When `blueprint-enablement-iam.yaml` is updated (version bumped), trigger a fleet-wide update:

```bash
aws lambda invoke \
  --function-name AccountRecycler \
  --payload '{"updateBlueprints":true}' \
  --cli-binary-format raw-in-base64-out \
  --region us-east-2 /tmp/response.json
```

The hourly reconciler also checks the blueprint version automatically and triggers this if needed.

---

## Account States Reference

| State | Meaning | Action |
|-------|---------|--------|
| `AVAILABLE` | Ready for assignment | None |
| `ASSIGNED` | In use by a project | None |
| `SETTING_UP` | Being provisioned | Wait |
| `CLEANING` | Being deprovisioned (REUSE) | Wait |
| `FAILED` | Setup/cleanup failed | Recycler fixes automatically |
| `ORPHANED` | In org but not in DynamoDB | Recycler fixes automatically |
| `DELETING` | Being closed | Wait |

---

## Uninstall

```bash
# Delete the infrastructure stack (Lambdas, DynamoDB, EventBridge, SNS, SSM)
aws cloudformation delete-stack \
  --stack-name AccountPoolFactory-Infrastructure \
  --region us-east-2

# Then ask the Org Admin to uninstall their stack (see OrgAdminGuide.md)
```
